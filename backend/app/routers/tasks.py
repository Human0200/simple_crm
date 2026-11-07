from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..permissions import (
    can_assign,
    can_observe,
    can_create_task,
    can_edit_task,
    can_delete_task,
)
from ..ws import manager
from ..timeline import add_event, add_client_event
from .. import email_service
from ..automation import run_status_change_rules
from ..unread import (
    attach_unread_to_tasks,
    compute_unread_for_task,
    mark_tabs_read,
    unread_summary_for_user,
)
from ..stages import (
    default_stage,
    get_stage,
    get_stage_by_key,
    get_funnel,
    preferred_funnel_for_user,
)
from ..task_ops import purge_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_query(db: Session):
    return db.query(models.Task).options(
        joinedload(models.Task.creator).joinedload(models.User.teams),
        joinedload(models.Task.assignees).joinedload(models.User.teams),
        joinedload(models.Task.observers).joinedload(models.User.teams),
        joinedload(models.Task.client),
        joinedload(models.Task.stage),
        joinedload(models.Task.comments).joinedload(models.Comment.author),
        joinedload(models.Task.timeline_events).joinedload(models.TimelineEvent.actor),
    )


def _resolve_client(db: Session, client_id: int | None) -> models.Client | None:
    if client_id is None:
        return None
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Клиент не найден")
    return client


def _to_out(task: models.Task, unread: dict | None = None) -> schemas.TaskOut:
    data = schemas.TaskOut.model_validate(task)
    if unread is not None:
        data.unread = schemas.UnreadCounts(**unread)
    return data


def _to_detail(
    task: models.Task, unread: dict | None = None
) -> schemas.TaskDetailOut:
    base = _to_out(task, unread)
    return schemas.TaskDetailOut(
        **base.model_dump(),
        comments=[schemas.CommentOut.model_validate(c) for c in task.comments],
        timeline=[
            schemas.TimelineEventOut.model_validate(e) for e in task.timeline_events
        ],
    )


def _unread_for(db: Session, task: models.Task, user_id: int) -> dict:
    state = (
        db.query(models.TaskReadState)
        .filter(
            models.TaskReadState.user_id == user_id,
            models.TaskReadState.task_id == task.id,
        )
        .first()
    )
    return compute_unread_for_task(task, user_id, state)


def _can_view(task: models.Task, user: models.User) -> bool:
    if user.is_admin:
        return True
    if task.creator_id == user.id:
        return True
    assignee_ids = {u.id for u in task.assignees}
    observer_ids = {u.id for u in task.observers}
    return user.id in assignee_ids or user.id in observer_ids


def _can_change_status(task: models.Task, user: models.User) -> bool:
    if task.creator_id == user.id:
        return True
    assignee_ids = {u.id for u in task.assignees}
    return user.id in assignee_ids


def _can_set_stage(task: models.Task, user: models.User, target: models.Stage) -> bool:
    if task.creator_id == user.id or user.is_admin:
        return True
    assignee_ids = {u.id for u in task.assignees}
    if user.id not in assignee_ids:
        return False
    return bool(target.assignee_can_set)


def _get_visible_task(task_id: int, db: Session, user: models.User) -> models.Task:
    task = _task_query(db).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
    if not _can_view(task, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к этой задаче")
    return task


@router.get("/unread", response_model=schemas.UnreadSummaryOut)
def unread_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    items = unread_summary_for_user(db, current_user)
    return schemas.UnreadSummaryOut(
        total=sum(i["total"] for i in items),
        items=[schemas.UnreadTaskItem(**i) for i in items],
    )


@router.get("", response_model=list[schemas.TaskOut])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = _task_query(db)
    if not current_user.is_admin:
        query = query.filter(
            or_(
                models.Task.creator_id == current_user.id,
                models.Task.assignees.any(models.User.id == current_user.id),
                models.Task.observers.any(models.User.id == current_user.id),
            )
        )
    tasks = query.order_by(models.Task.created_at.desc()).all()
    unread_map = attach_unread_to_tasks(db, tasks, current_user.id)
    return [_to_out(t, unread_map.get(t.id)) for t in tasks]


@router.post("", response_model=schemas.TaskDetailOut)
async def create_task(
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not can_create_task(db, current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Вам не разрешено ставить задачи — недостаточно прав",
        )
    if not payload.title.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название обязательно")

    creator_id = current_user.id
    if payload.creator_id is not None and current_user.is_admin:
        new_creator = db.query(models.User).filter(models.User.id == payload.creator_id).first()
        if new_creator is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Постановщик не найден")
        creator_id = new_creator.id

    assignees = (
        db.query(models.User).filter(models.User.id.in_(payload.assignee_ids)).all()
        if payload.assignee_ids
        else []
    )
    for assignee in assignees:
        if not can_assign(db, current_user, assignee):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Вам не разрешено ставить задачи пользователю {assignee.full_name}",
            )
    observers = (
        db.query(models.User).filter(models.User.id.in_(payload.observer_ids)).all()
        if payload.observer_ids
        else []
    )
    for observer in observers:
        if not can_observe(db, current_user, observer):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Вам не разрешено добавлять в наблюдатели пользователя {observer.full_name}",
            )

    client = _resolve_client(db, payload.client_id)

    stage = None
    if payload.stage_id is not None:
        stage = get_stage(db, payload.stage_id)
        if stage is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Стадия не найдена")
    else:
        funnel_id = payload.funnel_id
        if funnel_id is not None:
            if get_funnel(db, funnel_id) is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Воронка не найдена")
        else:
            funnel_id = preferred_funnel_for_user(db, current_user).id
        stage = default_stage(db, funnel_id=funnel_id)

    task = models.Task(
        title=payload.title.strip(),
        description=payload.description,
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
        "Задача создана",
        actor_id=current_user.id,
        detail=task.title,
        mirror_to_client=False,
    )
    if client:
        add_event(
            db,
            task.id,
            models.TimelineEventType.CLIENT_LINKED,
            f"Клиент: {client.name}",
            actor_id=current_user.id,
            detail=client.name,
            meta={"client_id": client.id},
            mirror_to_client=False,
        )
        add_client_event(
            db,
            client.id,
            models.ClientEventType.TASK_LINKED,
            f"Задача: {task.title}",
            actor_id=current_user.id,
            detail=task.title,
            meta={"task_id": task.id},
        )
    db.commit()
    # Автору задача уже «прочитана»
    mark_tabs_read(
        db,
        current_user.id,
        task.id,
        ["comments", "results", "timeline", "email"],
    )
    result = _get_visible_task(task.id, db, current_user)
    await manager.notify_task_event(db, result, "task_created", actor_id=current_user.id)
    return _to_detail(result, _unread_for(db, result, current_user.id))


@router.get("/{task_id}", response_model=schemas.TaskDetailOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    return _to_detail(task, _unread_for(db, task, current_user.id))


@router.post("/{task_id}/read", response_model=schemas.UnreadCounts)
def mark_task_read(
    task_id: int,
    payload: schemas.TaskReadIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    allowed = {"comments", "results", "timeline", "email"}
    tabs = [t for t in payload.tabs if t in allowed]
    if not tabs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Укажите вкладки для прочтения")
    mark_tabs_read(db, current_user.id, task.id, tabs)
    task = _get_visible_task(task_id, db, current_user)
    return schemas.UnreadCounts(**_unread_for(db, task, current_user.id))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    if not can_delete_task(db, current_user, task):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Недостаточно прав для удаления задачи",
        )
    await manager.notify_task_event(
        db, task, "task_deleted", actor_id=current_user.id
    )
    purge_task(db, task)
    db.commit()


@router.put("/{task_id}", response_model=schemas.TaskDetailOut)
async def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    if not can_edit_task(db, current_user, task):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Недостаточно прав для редактирования задачи",
        )
    if not payload.title.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название обязательно")

    new_assignees = (
        db.query(models.User).filter(models.User.id.in_(payload.assignee_ids)).all()
        if payload.assignee_ids
        else []
    )
    for assignee in new_assignees:
        if not can_assign(db, current_user, assignee):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Вам не разрешено ставить задачи пользователю {assignee.full_name}",
            )

    new_observers = (
        db.query(models.User).filter(models.User.id.in_(payload.observer_ids)).all()
        if payload.observer_ids
        else []
    )
    for observer in new_observers:
        if not can_observe(db, current_user, observer):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Вам не разрешено добавлять в наблюдатели пользователя {observer.full_name}",
            )

    old_client_id = task.client_id
    new_client = _resolve_client(db, payload.client_id)

    task.title = payload.title.strip()
    task.description = payload.description
    task.due_date = payload.due_date
    task.assignees = new_assignees
    task.observers = new_observers
    task.client_id = new_client.id if new_client else None
    add_event(
        db,
        task.id,
        models.TimelineEventType.UPDATED,
        "Задача обновлена",
        actor_id=current_user.id,
        detail=task.title,
    )
    if (new_client.id if new_client else None) != old_client_id:
        if new_client:
            add_event(
                db,
                task.id,
                models.TimelineEventType.CLIENT_LINKED,
                f"Клиент: {new_client.name}",
                actor_id=current_user.id,
                detail=new_client.name,
                meta={"client_id": new_client.id},
                mirror_to_client=False,
            )
            add_client_event(
                db,
                new_client.id,
                models.ClientEventType.TASK_LINKED,
                f"Задача: {task.title}",
                actor_id=current_user.id,
                detail=task.title,
                meta={"task_id": task.id},
            )
    db.commit()
    result = _get_visible_task(task_id, db, current_user)
    await manager.notify_task_event(db, result, "task_updated", actor_id=current_user.id)
    return _to_detail(result, _unread_for(db, result, current_user.id))


@router.post("/{task_id}/comments", response_model=schemas.TaskDetailOut)
async def add_comment(
    task_id: int,
    payload: schemas.CommentIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    if not payload.text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Комментарий не может быть пустым")

    comment = models.Comment(
        task_id=task.id,
        author_id=current_user.id,
        text=payload.text.strip(),
        is_result=payload.is_result,
    )
    db.add(comment)
    add_event(
        db,
        task.id,
        models.TimelineEventType.COMMENTED,
        "Добавлен комментарий",
        actor_id=current_user.id,
        detail=payload.text.strip()[:200],
        meta={"is_result": payload.is_result},
    )
    db.commit()
    result = _get_visible_task(task_id, db, current_user)
    await manager.notify_task_event(db, result, "task_commented", actor_id=current_user.id)
    return _to_detail(result, _unread_for(db, result, current_user.id))


@router.patch("/{task_id}/comments/{comment_id}", response_model=schemas.TaskDetailOut)
async def update_comment_result(
    task_id: int,
    comment_id: int,
    payload: schemas.CommentResultUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    comment = next((c for c in task.comments if c.id == comment_id), None)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Комментарий не найден")
    if comment.author_id != current_user.id and task.creator_id != current_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Отметить результатом может автор комментария или постановщик",
        )
    comment.is_result = payload.is_result
    db.commit()
    result = _get_visible_task(task_id, db, current_user)
    await manager.notify_task_event(db, result, "task_updated", actor_id=current_user.id)
    return _to_detail(result, _unread_for(db, result, current_user.id))


@router.patch("/{task_id}/status", response_model=schemas.TaskDetailOut)
async def change_status(
    task_id: int,
    payload: schemas.TaskStatusChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    if not _can_change_status(task, current_user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Менять статус может только постановщик или исполнитель",
        )

    new_stage = None
    if payload.stage_id is not None:
        new_stage = get_stage(db, payload.stage_id)
    elif payload.status:
        new_stage = get_stage_by_key(db, payload.status)
    if new_stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Стадия не найдена")

    if not _can_set_stage(task, current_user, new_stage):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Исполнитель не может переводить задачу в стадию «{new_stage.name}»",
        )

    if new_stage.requires_result:
        last_comment = task.comments[-1] if task.comments else None
        if not last_comment or not last_comment.is_result:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Чтобы перевести задачу в «{new_stage.name}», отметьте последний комментарий как результат",
            )

    old_stage = task.stage
    old_key = old_stage.key if old_stage else (task.status or "")
    task.stage_id = new_stage.id
    task.status = new_stage.key

    comment = models.Comment(
        task_id=task.id,
        author_id=current_user.id,
        text="",
        is_status_change=True,
        from_status=old_key,
        to_status=new_stage.key,
    )
    db.add(comment)
    add_event(
        db,
        task.id,
        models.TimelineEventType.STATUS_CHANGED,
        "Стадия изменена",
        actor_id=current_user.id,
        detail=f"{old_key} → {new_stage.key}",
        meta={
            "from_status": old_key,
            "to_status": new_stage.key,
            "from_stage_id": old_stage.id if old_stage else None,
            "to_stage_id": new_stage.id,
        },
    )

    auto_tasks = run_status_change_rules(db, task, old_stage, new_stage)
    db.commit()

    result = _get_visible_task(task_id, db, current_user)
    await manager.notify_task_event(db, result, "task_status_changed", actor_id=current_user.id)
    for auto_task in auto_tasks:
        loaded = _task_query(db).filter(models.Task.id == auto_task.id).first()
        if loaded:
            await manager.notify_task_event(
                db, loaded, "task_created", actor_id=current_user.id
            )
    return _to_detail(result, _unread_for(db, result, current_user.id))


@router.get("/{task_id}/emails", response_model=list[schemas.MailMessageOut])
def list_task_emails(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    # подтянуть входящие перед выдачей истории
    try:
        email_service.fetch_inbound_emails(db)
    except Exception:
        pass
    rows = (
        db.query(models.MailMessage)
        .options(joinedload(models.MailMessage.actor))
        .filter(models.MailMessage.task_id == task.id)
        .order_by(models.MailMessage.created_at.asc())
        .all()
    )
    return [
        schemas.MailMessageOut.model_validate(email_service.mail_to_dict(m))
        for m in rows
    ]


@router.post("/{task_id}/email", response_model=schemas.TaskDetailOut)
async def send_task_email(
    task_id: int,
    payload: schemas.TaskEmailIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    settings = email_service.get_settings(db)
    if settings is None or not email_service.is_configured(settings):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Почтовая интеграция не настроена. Обратитесь к администратору.",
        )

    try:
        message_id = email_service.send_email(
            settings,
            to_emails=payload.to_emails,
            cc_emails=payload.cc_emails,
            subject=payload.subject.strip(),
            body=payload.body,
        )
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Не удалось отправить письмо: {e}",
        ) from e

    email_service.store_outbound(
        db,
        task=task,
        actor_id=current_user.id,
        to_emails=payload.to_emails,
        cc_emails=payload.cc_emails or [],
        subject=payload.subject.strip(),
        body=payload.body,
        message_id=message_id,
    )
    db.commit()
    result = _get_visible_task(task_id, db, current_user)
    await manager.notify_task_event(db, result, "task_updated", actor_id=current_user.id)
    return _to_detail(result, _unread_for(db, result, current_user.id))
