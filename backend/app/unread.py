from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from . import models


EPOCH = datetime(1970, 1, 1)


def get_or_create_read_state(
    db: Session, user_id: int, task_id: int
) -> models.TaskReadState:
    state = (
        db.query(models.TaskReadState)
        .filter(
            models.TaskReadState.user_id == user_id,
            models.TaskReadState.task_id == task_id,
        )
        .first()
    )
    if state is None:
        state = models.TaskReadState(user_id=user_id, task_id=task_id)
        db.add(state)
        db.flush()
    return state


def _seen(value: Optional[datetime]) -> datetime:
    return value or EPOCH


# События таймлайна, которые дублируют другие вкладки (комментарии / почта).
# Таймлайн — история, бейдж на нём только для «самостоятельных» событий.
_TIMELINE_MIRROR_TYPES = {
    models.TimelineEventType.COMMENTED,
    models.TimelineEventType.EMAIL_SENT,
    models.TimelineEventType.EMAIL_RECEIVED,
}
_EMAIL_EVENT_TYPES = {
    models.TimelineEventType.EMAIL_SENT,
    models.TimelineEventType.EMAIL_RECEIVED,
}


def compute_unread_for_task(
    task: models.Task, user_id: int, state: Optional[models.TaskReadState]
) -> dict:
    comments_since = _seen(state.comments_seen_at if state else None)
    results_since = _seen(state.results_seen_at if state else None)
    timeline_since = _seen(state.timeline_seen_at if state else None)
    email_since = _seen(state.email_seen_at if state else None)

    comments = 0
    results = 0
    for c in task.comments:
        if c.author_id == user_id:
            continue
        if c.is_status_change:
            continue
        if c.created_at and c.created_at > comments_since:
            comments += 1
        if c.is_result and c.created_at and c.created_at > results_since:
            results += 1

    timeline = 0
    email = 0
    for e in task.timeline_events:
        if e.actor_id == user_id:
            continue
        if not e.created_at:
            continue
        if e.event_type in _EMAIL_EVENT_TYPES and e.created_at > email_since:
            # входящие без actor_id тоже считаем; исходящие своего автора пропускаем выше
            if (
                e.event_type == models.TimelineEventType.EMAIL_RECEIVED
                or e.actor_id != user_id
            ):
                email += 1
        # Не дублируем комментарии/письма в бейдже таймлайна
        if e.event_type in _TIMELINE_MIRROR_TYPES:
            continue
        if e.created_at > timeline_since:
            timeline += 1

    # results — подмножество comments для бейджа вкладки; в total не суммируем дважды
    total = comments + timeline + email
    return {
        "comments": comments,
        "results": results,
        "timeline": timeline,
        "email": email,
        "total": total,
    }


def unread_summary_for_user(db: Session, user: models.User) -> list[dict]:
    query = db.query(models.Task).options(
        joinedload(models.Task.comments),
        joinedload(models.Task.timeline_events),
        joinedload(models.Task.stage),
    )
    if not user.is_admin:
        from sqlalchemy import or_

        query = query.filter(
            or_(
                models.Task.creator_id == user.id,
                models.Task.assignees.any(models.User.id == user.id),
                models.Task.observers.any(models.User.id == user.id),
            )
        )
    tasks = query.all()
    states = {
        (s.task_id): s
        for s in db.query(models.TaskReadState)
        .filter(models.TaskReadState.user_id == user.id)
        .all()
    }

    items = []
    for task in tasks:
        counts = compute_unread_for_task(task, user.id, states.get(task.id))
        if counts["total"] <= 0:
            continue
        items.append(
            {
                "task_id": task.id,
                "title": task.title,
                "status": task.stage.key if task.stage else str(task.status or ""),
                **counts,
            }
        )
    items.sort(key=lambda x: x["total"], reverse=True)
    return items


def mark_tabs_read(
    db: Session,
    user_id: int,
    task_id: int,
    tabs: list[str],
    *,
    when: Optional[datetime] = None,
) -> models.TaskReadState:
    when = when or datetime.utcnow()
    state = get_or_create_read_state(db, user_id, task_id)
    mapping = {
        "comments": "comments_seen_at",
        "results": "results_seen_at",
        "timeline": "timeline_seen_at",
        "email": "email_seen_at",
    }
    for tab in tabs:
        field = mapping.get(tab)
        if field:
            setattr(state, field, when)
    db.commit()
    db.refresh(state)
    return state


def attach_unread_to_tasks(
    db: Session, tasks: list[models.Task], user_id: int
) -> dict[int, dict]:
    if not tasks:
        return {}
    task_ids = [t.id for t in tasks]
    states = {
        s.task_id: s
        for s in db.query(models.TaskReadState)
        .filter(
            models.TaskReadState.user_id == user_id,
            models.TaskReadState.task_id.in_(task_ids),
        )
        .all()
    }
    return {
        t.id: compute_unread_for_task(t, user_id, states.get(t.id)) for t in tasks
    }
