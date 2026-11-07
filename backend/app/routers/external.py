"""Внешнее API для интеграций. Auth: Bearer / X-API-Key (API-токен из админки)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_api_actor
from ..database import get_db
from ..stages import default_stage, get_stage
from ..task_ops import purge_task
from ..timeline import add_client_event, add_event

router = APIRouter(prefix="/api/v1", tags=["external-api"])


def _task_query(db: Session):
    return db.query(models.Task).options(
        joinedload(models.Task.assignees),
        joinedload(models.Task.observers),
        joinedload(models.Task.client),
        joinedload(models.Task.stage),
    )


def _client_query(db: Session):
    return db.query(models.Client).options(joinedload(models.Client.tasks))


def _task_out(task: models.Task) -> schemas.ExtTaskOut:
    return schemas.ExtTaskOut(
        id=task.id,
        title=task.title,
        description=task.description or "",
        status=task.status,
        stage_id=task.stage_id,
        due_date=task.due_date,
        creator_id=task.creator_id,
        client_id=task.client_id,
        assignee_ids=[u.id for u in task.assignees],
        observer_ids=[u.id for u in task.observers],
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _client_out(client: models.Client) -> schemas.ExtClientOut:
    return schemas.ExtClientOut(
        id=client.id,
        name=client.name,
        company=client.company or "",
        email=client.email or "",
        phone=client.phone or "",
        notes=client.notes or "",
        created_at=client.created_at,
        updated_at=client.updated_at,
        tasks_count=len(client.tasks) if client.tasks is not None else 0,
    )


def _resolve_client(db: Session, client_id: int | None) -> models.Client | None:
    if client_id is None:
        return None
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    return client


def _users_by_ids(db: Session, ids: list[int]) -> list[models.User]:
    if not ids:
        return []
    users = db.query(models.User).filter(models.User.id.in_(ids)).all()
    found = {u.id for u in users}
    missing = [i for i in ids if i not in found]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Пользователи не найдены: {missing}",
        )
    return users


# --- Tasks ---


@router.get("/tasks", response_model=list[schemas.ExtTaskOut])
def search_tasks(
    q: str | None = Query(None, description="Поиск по названию и описанию"),
    client_id: int | None = None,
    stage_id: int | None = None,
    status_key: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _actor: models.User = Depends(get_api_actor),
):
    query = _task_query(db)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(models.Task.title.ilike(like), models.Task.description.ilike(like))
        )
    if client_id is not None:
        query = query.filter(models.Task.client_id == client_id)
    if stage_id is not None:
        query = query.filter(models.Task.stage_id == stage_id)
    if status_key:
        query = query.filter(models.Task.status == status_key)
    tasks = query.order_by(models.Task.id.desc()).limit(limit).all()
    return [_task_out(t) for t in tasks]


@router.get("/tasks/{task_id}", response_model=schemas.ExtTaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    _actor: models.User = Depends(get_api_actor),
):
    task = _task_query(db).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
    return _task_out(task)


@router.post("/tasks", response_model=schemas.ExtTaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: schemas.ExtTaskIn,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_api_actor),
):
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название обязательно")

    creator_id = actor.id
    if payload.creator_id is not None:
        creator = db.query(models.User).filter(models.User.id == payload.creator_id).first()
        if creator is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Постановщик не найден")
        creator_id = creator.id

    client = _resolve_client(db, payload.client_id)
    if payload.stage_id is not None:
        stage = get_stage(db, payload.stage_id)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Стадия не найдена")
    else:
        stage = default_stage(db)

    assignees = _users_by_ids(db, payload.assignee_ids)
    observers = _users_by_ids(db, payload.observer_ids)

    task = models.Task(
        title=title,
        description=payload.description or "",
        due_date=payload.due_date,
        creator_id=creator_id,
        client_id=client.id if client else None,
        stage_id=stage.id,
        status=stage.key,
        assignees=assignees,
        observers=observers,
    )
    db.add(task)
    db.flush()
    add_event(
        db,
        task.id,
        models.TimelineEventType.CREATED,
        "Задача создана через API",
        actor_id=actor.id,
        detail=task.title,
        meta={"via": "external_api"},
        mirror_to_client=False,
    )
    if client:
        add_client_event(
            db,
            client.id,
            models.ClientEventType.TASK_LINKED,
            f"Задача: {task.title}",
            actor_id=actor.id,
            detail=task.title,
            meta={"task_id": task.id, "via": "external_api"},
        )
    db.commit()
    return _task_out(_task_query(db).filter(models.Task.id == task.id).one())


@router.put("/tasks/{task_id}", response_model=schemas.ExtTaskOut)
def update_task(
    task_id: int,
    payload: schemas.ExtTaskUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_api_actor),
):
    task = _task_query(db).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")

    changes = []
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название обязательно")
        if title != task.title:
            changes.append(f"название → {title}")
        task.title = title
    if payload.description is not None:
        task.description = payload.description
        changes.append("описание")
    if payload.due_date is not None or (
        payload.model_fields_set and "due_date" in payload.model_fields_set
    ):
        # allow explicit null via due_date: null only if field was set
        if "due_date" in payload.model_fields_set:
            task.due_date = payload.due_date
            changes.append("срок")
    if payload.assignee_ids is not None:
        task.assignees = _users_by_ids(db, payload.assignee_ids)
        changes.append("исполнители")
    if payload.observer_ids is not None:
        task.observers = _users_by_ids(db, payload.observer_ids)
        changes.append("наблюдатели")
    if "client_id" in payload.model_fields_set:
        client = _resolve_client(db, payload.client_id)
        task.client_id = client.id if client else None
        changes.append("клиент")
    if payload.stage_id is not None:
        stage = get_stage(db, payload.stage_id)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Стадия не найдена")
        if task.stage_id != stage.id:
            changes.append(f"стадия → {stage.name}")
        task.stage_id = stage.id
        task.status = stage.key

    if changes:
        add_event(
            db,
            task.id,
            models.TimelineEventType.UPDATED,
            "Задача обновлена через API",
            actor_id=actor.id,
            detail=", ".join(changes),
            meta={"via": "external_api"},
        )
    db.commit()
    return _task_out(_task_query(db).filter(models.Task.id == task_id).one())


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    _actor: models.User = Depends(get_api_actor),
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
    purge_task(db, task)
    db.commit()


# --- Clients ---


@router.get("/clients", response_model=list[schemas.ExtClientOut])
def search_clients(
    q: str | None = Query(None, description="Поиск по имени, компании, email, телефону"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _actor: models.User = Depends(get_api_actor),
):
    query = _client_query(db)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Client.name.ilike(like),
                models.Client.company.ilike(like),
                models.Client.email.ilike(like),
                models.Client.phone.ilike(like),
            )
        )
    clients = query.order_by(models.Client.name).limit(limit).all()
    return [_client_out(c) for c in clients]


@router.get("/clients/{client_id}", response_model=schemas.ExtClientOut)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    _actor: models.User = Depends(get_api_actor),
):
    client = _client_query(db).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    return _client_out(client)


@router.post(
    "/clients", response_model=schemas.ExtClientOut, status_code=status.HTTP_201_CREATED
)
def create_client(
    payload: schemas.ExtClientIn,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_api_actor),
):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название клиента обязательно")
    client = models.Client(
        name=name,
        company=(payload.company or "").strip(),
        email=(payload.email or "").strip(),
        phone=(payload.phone or "").strip(),
        notes=(payload.notes or "").strip(),
    )
    db.add(client)
    db.flush()
    add_client_event(
        db,
        client.id,
        models.ClientEventType.CREATED,
        "Клиент создан через API",
        actor_id=actor.id,
        detail=name,
        meta={"via": "external_api"},
    )
    db.commit()
    return _client_out(_client_query(db).filter(models.Client.id == client.id).one())


@router.put("/clients/{client_id}", response_model=schemas.ExtClientOut)
def update_client(
    client_id: int,
    payload: schemas.ExtClientUpdate,
    db: Session = Depends(get_db),
    actor: models.User = Depends(get_api_actor),
):
    client = _client_query(db).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название клиента обязательно")
        client.name = name
    if payload.company is not None:
        client.company = payload.company.strip()
    if payload.email is not None:
        client.email = payload.email.strip()
    if payload.phone is not None:
        client.phone = payload.phone.strip()
    if payload.notes is not None:
        client.notes = payload.notes.strip()

    add_client_event(
        db,
        client.id,
        models.ClientEventType.UPDATED,
        "Клиент обновлён через API",
        actor_id=actor.id,
        detail=client.name,
        meta={"via": "external_api"},
    )
    db.commit()
    return _client_out(_client_query(db).filter(models.Client.id == client_id).one())


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    _actor: models.User = Depends(get_api_actor),
):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    db.query(models.Task).filter(models.Task.client_id == client_id).update(
        {models.Task.client_id: None}, synchronize_session=False
    )
    db.query(models.AutomationFire).filter(
        models.AutomationFire.client_id == client_id
    ).delete(synchronize_session=False)
    db.query(models.ClientTimelineEvent).filter(
        models.ClientTimelineEvent.client_id == client_id
    ).delete(synchronize_session=False)
    db.delete(client)
    db.commit()
