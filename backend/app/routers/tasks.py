from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..permissions import can_assign, can_observe
from ..ws import manager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _task_query(db: Session):
    return db.query(models.Task).options(
        joinedload(models.Task.creator),
        joinedload(models.Task.assignees),
        joinedload(models.Task.observers),
        joinedload(models.Task.comments).joinedload(models.Comment.author),
    )


def _can_view(task: models.Task, user: models.User) -> bool:
    if user.is_admin:
        return True
    if task.creator_id == user.id:
        return True
    assignee_ids = {u.id for u in task.assignees}
    observer_ids = {u.id for u in task.observers}
    return user.id in assignee_ids or user.id in observer_ids


ASSIGNEE_ALLOWED_STATUSES = {
    models.TaskStatus.BACKLOG,
    models.TaskStatus.IN_PROGRESS,
    models.TaskStatus.REVIEW,
}


def _can_change_status(task: models.Task, user: models.User) -> bool:
    if task.creator_id == user.id:
        return True
    assignee_ids = {u.id for u in task.assignees}
    return user.id in assignee_ids


def _can_set_status(task: models.Task, user: models.User, target: models.TaskStatus) -> bool:
    if task.creator_id == user.id:
        return True
    assignee_ids = {u.id for u in task.assignees}
    if user.id not in assignee_ids:
        return False
    return target in ASSIGNEE_ALLOWED_STATUSES


def _get_visible_task(task_id: int, db: Session, user: models.User) -> models.Task:
    task = _task_query(db).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Задача не найдена")
    if not _can_view(task, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к этой задаче")
    return task


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
    return query.order_by(models.Task.created_at.desc()).all()


@router.post("", response_model=schemas.TaskDetailOut)
async def create_task(
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.is_admin and current_user.role != models.UserRole.CREATOR:
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

    task = models.Task(
        title=payload.title.strip(),
        description=payload.description,
        due_date=payload.due_date,
        creator_id=creator_id,
        assignees=assignees,
        observers=observers,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    result = _get_visible_task(task.id, db, current_user)
    await manager.notify_task_event(db, result, "task_created", actor_id=current_user.id)
    return result


@router.get("/{task_id}", response_model=schemas.TaskDetailOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_visible_task(task_id, db, current_user)


@router.put("/{task_id}", response_model=schemas.TaskDetailOut)
async def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = _get_visible_task(task_id, db, current_user)
    if task.creator_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Редактировать задачу может только постановщик",
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

    task.title = payload.title.strip()
    task.description = payload.description
    task.due_date = payload.due_date
    task.assignees = new_assignees
    task.observers = new_observers
    db.commit()
    result = _get_visible_task(task_id, db, current_user)
    await manager.notify_task_event(db, result, "task_updated", actor_id=current_user.id)
    return result


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
    db.commit()
    result = _get_visible_task(task_id, db, current_user)
    await manager.notify_task_event(db, result, "task_commented", actor_id=current_user.id)
    return result


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
    return result


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
    if not _can_set_status(task, current_user, payload.status):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Исполнитель может переводить задачу только в статусы «К выполнению», «В работе» и «На проверку»",
        )
    REQUIRES_RESULT = {models.TaskStatus.REVIEW, models.TaskStatus.DONE}
    if payload.status in REQUIRES_RESULT:
        last_comment = task.comments[-1] if task.comments else None
        if not last_comment or not last_comment.is_result:
            label = "На проверку" if payload.status == models.TaskStatus.REVIEW else "Готово"
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Чтобы перевести задачу в «{label}», отметьте последний комментарий как результат",
            )

    old_status = task.status
    task.status = payload.status

    comment = models.Comment(
        task_id=task.id,
        author_id=current_user.id,
        text="",
        is_status_change=True,
        from_status=old_status,
        to_status=payload.status,
    )
    db.add(comment)
    db.commit()
    result = _get_visible_task(task_id, db, current_user)
    await manager.notify_task_event(db, result, "task_status_changed", actor_id=current_user.id)
    return result
