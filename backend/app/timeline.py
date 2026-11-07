import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models


def add_event(
    db: Session,
    task_id: int,
    event_type: models.TimelineEventType,
    title: str,
    *,
    actor_id: Optional[int] = None,
    detail: str = "",
    meta: Optional[dict[str, Any]] = None,
    commit: bool = False,
    mirror_to_client: bool = True,
) -> models.TimelineEvent:
    event = models.TimelineEvent(
        task_id=task_id,
        actor_id=actor_id,
        event_type=event_type,
        title=title,
        detail=detail or "",
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(event)

    if mirror_to_client:
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if task and task.client_id:
            add_client_event(
                db,
                task.client_id,
                models.ClientEventType.TASK_ACTIVITY,
                title,
                actor_id=actor_id,
                detail=detail or "",
                meta={"task_id": task_id, "task_event": event_type.value, **(meta or {})},
            )

    if commit:
        db.commit()
        db.refresh(event)
    return event


def add_client_event(
    db: Session,
    client_id: int,
    event_type: models.ClientEventType,
    title: str,
    *,
    actor_id: Optional[int] = None,
    detail: str = "",
    meta: Optional[dict[str, Any]] = None,
    commit: bool = False,
) -> models.ClientTimelineEvent:
    event = models.ClientTimelineEvent(
        client_id=client_id,
        actor_id=actor_id,
        event_type=event_type,
        title=title,
        detail=detail or "",
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event


def client_last_activity_at(db: Session, client: models.Client) -> datetime:
    last = (
        db.query(func.max(models.ClientTimelineEvent.created_at))
        .filter(models.ClientTimelineEvent.client_id == client.id)
        .scalar()
    )
    return last or client.created_at or datetime.utcnow()
