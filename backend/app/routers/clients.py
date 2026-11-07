from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from .. import email_service
from ..auth import get_current_user
from ..database import get_db
from ..permissions import can_see_client, filter_visible_clients, user_team_ids
from ..timeline import add_client_event, client_last_activity_at

router = APIRouter(prefix="/api/clients", tags=["clients"])


def _client_query(db: Session):
    return db.query(models.Client).options(
        joinedload(models.Client.timeline_events).joinedload(
            models.ClientTimelineEvent.actor
        ),
        joinedload(models.Client.tasks),
    )


def _to_out(db: Session, client: models.Client) -> schemas.ClientOut:
    return schemas.ClientOut(
        id=client.id,
        name=client.name,
        company=client.company or "",
        email=client.email or "",
        phone=client.phone or "",
        notes=client.notes or "",
        created_at=client.created_at,
        updated_at=client.updated_at,
        last_activity_at=client_last_activity_at(db, client),
        tasks_count=len(client.tasks) if client.tasks is not None else 0,
    )


def _to_detail(db: Session, client: models.Client) -> schemas.ClientDetailOut:
    base = _to_out(db, client)
    return schemas.ClientDetailOut(
        **base.model_dump(),
        timeline=[
            schemas.ClientTimelineEventOut.model_validate(e)
            for e in client.timeline_events
        ],
    )


@router.get("", response_model=list[schemas.ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    clients = _client_query(db).order_by(models.Client.name).all()
    clients = filter_visible_clients(db, current_user, clients)
    return [_to_out(db, c) for c in clients]


@router.post("", response_model=schemas.ClientDetailOut)
def create_client(
    payload: schemas.ClientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название клиента обязательно")
    teams = user_team_ids(current_user)
    owner_team_id = next(iter(teams), None) if teams else None
    client = models.Client(
        name=name,
        company=(payload.company or "").strip(),
        email=(payload.email or "").strip(),
        phone=(payload.phone or "").strip(),
        notes=(payload.notes or "").strip(),
        owner_team_id=owner_team_id,
    )
    db.add(client)
    db.flush()
    add_client_event(
        db,
        client.id,
        models.ClientEventType.CREATED,
        "Клиент создан",
        actor_id=current_user.id,
        detail=name,
    )
    db.commit()
    return _to_detail(db, _client_query(db).filter(models.Client.id == client.id).one())


@router.get("/{client_id}", response_model=schemas.ClientDetailOut)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = _client_query(db).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    if not can_see_client(db, current_user, client):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к клиенту")
    return _to_detail(db, client)


@router.put("/{client_id}", response_model=schemas.ClientDetailOut)
def update_client(
    client_id: int,
    payload: schemas.ClientUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = _client_query(db).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    if not can_see_client(db, current_user, client):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к клиенту")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название клиента обязательно")
    client.name = name
    client.company = (payload.company or "").strip()
    client.email = (payload.email or "").strip()
    client.phone = (payload.phone or "").strip()
    client.notes = (payload.notes or "").strip()
    add_client_event(
        db,
        client.id,
        models.ClientEventType.UPDATED,
        "Карточка клиента обновлена",
        actor_id=current_user.id,
        detail=name,
    )
    db.commit()
    return _to_detail(db, _client_query(db).filter(models.Client.id == client_id).one())


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    if not can_see_client(db, current_user, client):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к клиенту")
    linked = (
        db.query(models.Task).filter(models.Task.client_id == client_id).count()
    )
    if linked:
        # отвязываем задачи, клиента удаляем
        db.query(models.Task).filter(models.Task.client_id == client_id).update(
            {models.Task.client_id: None}
        )
    db.query(models.AutomationFire).filter(
        models.AutomationFire.client_id == client_id
    ).delete()
    db.delete(client)
    db.commit()


@router.get("/{client_id}/emails", response_model=list[schemas.MailMessageOut])
def list_client_emails(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    if not can_see_client(db, current_user, client):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к клиенту")
    try:
        email_service.fetch_inbound_emails(db)
    except Exception:
        pass
    rows = (
        db.query(models.MailMessage)
        .options(joinedload(models.MailMessage.actor))
        .filter(models.MailMessage.client_id == client_id)
        .order_by(models.MailMessage.created_at.asc())
        .all()
    )
    return [
        schemas.MailMessageOut.model_validate(email_service.mail_to_dict(m))
        for m in rows
    ]


@router.post("/{client_id}/notes", response_model=schemas.ClientDetailOut)
def add_client_note(
    client_id: int,
    payload: schemas.ClientNoteIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client = _client_query(db).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    text = payload.text.strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Текст заметки пуст")
    add_client_event(
        db,
        client.id,
        models.ClientEventType.NOTE,
        "Заметка",
        actor_id=current_user.id,
        detail=text,
    )
    db.commit()
    return _to_detail(db, _client_query(db).filter(models.Client.id == client_id).one())
