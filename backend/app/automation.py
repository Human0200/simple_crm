"""Планировщик и исполнение правил автоматизации."""

import asyncio
import json
from datetime import datetime, date, timedelta
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from . import models
from . import email_service
from .database import SessionLocal
from .timeline import add_event, add_client_event, client_last_activity_at
from .stages import default_stage, get_stage


def _parse_ids(raw: str) -> list[int]:
    try:
        data = json.loads(raw or "[]")
        return [int(x) for x in data]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _render(template: str, context: dict) -> str:
    result = template or ""
    for key, value in context.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def _stage_name(stage: Optional[models.Stage], fallback: str = "") -> str:
    return stage.name if stage else fallback


def _rule_context(
    rule: models.AutomationRule,
    *,
    source_task: Optional[models.Task] = None,
    source_client: Optional[models.Client] = None,
    source_mail: Optional[models.MailMessage] = None,
) -> dict:
    source_stage = source_task.stage if source_task else None
    client = source_client
    if client is None and source_task is not None:
        client = source_task.client
    return {
        "rule": rule.name,
        "date": date.today().isoformat(),
        "source_title": source_task.title if source_task else "",
        "source_id": source_task.id if source_task else "",
        "source_status": _stage_name(
            source_stage, getattr(source_task, "status", "") if source_task else ""
        ),
        "source_stage": _stage_name(source_stage),
        "client_name": client.name if client else "",
        "client_company": client.company if client else "",
        "client_id": client.id if client else "",
        "client_email": client.email if client else "",
        "client_phone": client.phone if client else "",
        "notes": client.notes if client else "",
        "mail_subject": source_mail.subject if source_mail else "",
        "mail_from": source_mail.from_addr if source_mail else "",
        "mail_body": (source_mail.body or "")[:2000] if source_mail else "",
    }


def _resolve_client(
    source_task: Optional[models.Task],
    source_client: Optional[models.Client],
) -> Optional[models.Client]:
    if source_client is not None:
        return source_client
    if source_task is not None:
        return source_task.client
    return None


def create_task_from_rule(
    db: Session,
    rule: models.AutomationRule,
    *,
    source_task: Optional[models.Task] = None,
    source_client: Optional[models.Client] = None,
    source_mail: Optional[models.MailMessage] = None,
) -> models.Task:
    context = _rule_context(
        rule,
        source_task=source_task,
        source_client=source_client,
        source_mail=source_mail,
    )
    title = _render(rule.title_template, context).strip() or rule.name
    description = _render(rule.description_template, context)

    assignee_ids = _parse_ids(rule.assignee_ids_json)
    observer_ids = _parse_ids(rule.observer_ids_json)
    assignees = (
        db.query(models.User).filter(models.User.id.in_(assignee_ids)).all()
        if assignee_ids
        else []
    )
    observers = (
        db.query(models.User).filter(models.User.id.in_(observer_ids)).all()
        if observer_ids
        else []
    )

    due_date = None
    if rule.due_offset_days is not None:
        due_date = date.today() + timedelta(days=rule.due_offset_days)

    client = _resolve_client(source_task, source_client)
    client_id = client.id if client else None

    stage = None
    if rule.target_stage_id:
        stage = get_stage(db, rule.target_stage_id)
    if stage is None and rule.condition_stage_id:
        stage = get_stage(db, rule.condition_stage_id)
    if stage is None:
        stage = default_stage(db)

    task = models.Task(
        title=title,
        description=description,
        due_date=due_date,
        creator_id=rule.creator_id,
        client_id=client_id,
        stage_id=stage.id,
        status=stage.key,
        assignees=assignees,
        observers=observers,
    )
    db.add(task)
    db.flush()

    detail = f"Правило «{rule.name}»"
    if source_task:
        detail += f" (по задаче #{source_task.id})"
    if client:
        detail += f" (по клиенту «{client.name}»)"
    add_event(
        db,
        task.id,
        models.TimelineEventType.AUTOMATION,
        "Задача создана автоматически",
        detail=detail,
        meta={
            "rule_id": rule.id,
            "source_task_id": source_task.id if source_task else None,
            "source_client_id": client.id if client else None,
        },
        mirror_to_client=False,
    )
    add_event(
        db,
        task.id,
        models.TimelineEventType.CREATED,
        "Задача создана",
        detail=title,
        meta={"via": "automation", "rule_id": rule.id},
        mirror_to_client=bool(client_id),
    )

    if client:
        add_client_event(
            db,
            client.id,
            models.ClientEventType.AUTOMATION,
            f"Автозадача: {title}",
            detail=detail,
            meta={"rule_id": rule.id, "task_id": task.id},
        )
    return task


def send_email_from_rule(
    db: Session,
    rule: models.AutomationRule,
    *,
    source_task: Optional[models.Task] = None,
    source_client: Optional[models.Client] = None,
    source_mail: Optional[models.MailMessage] = None,
) -> bool:
    """Отправить письмо по правилу. Возвращает True при успехе."""
    context = _rule_context(
        rule,
        source_task=source_task,
        source_client=source_client,
        source_mail=source_mail,
    )
    to_raw = _render(rule.email_to_template or "{client_email}", context).strip()
    subject = _render(rule.title_template, context).strip() or rule.name
    body = _render(rule.description_template, context)

    to_emails = [addr.strip() for addr in to_raw.replace(";", ",").split(",") if addr.strip()]
    if not to_emails:
        return False

    settings = email_service.get_settings(db)
    if settings is None or not email_service.is_configured(settings):
        return False

    try:
        email_service.send_email(
            settings,
            to_emails=to_emails,
            subject=subject,
            body=body,
        )
    except Exception:
        return False

    client = _resolve_client(source_task, source_client)
    detail = f"Правило «{rule.name}» · Кому: {', '.join(to_emails)}"
    meta = {
        "rule_id": rule.id,
        "to": to_emails,
        "subject": subject,
        "via": "automation",
    }

    if source_task is not None:
        add_event(
            db,
            source_task.id,
            models.TimelineEventType.EMAIL_SENT,
            f"Автописьмо: {subject}",
            actor_id=rule.creator_id,
            detail=f"{detail}\n\n{body[:500]}",
            meta=meta,
        )
    elif client is not None:
        add_client_event(
            db,
            client.id,
            models.ClientEventType.EMAIL_SENT,
            f"Автописьмо: {subject}",
            actor_id=rule.creator_id,
            detail=f"{detail}\n\n{body[:500]}",
            meta=meta,
        )
    return True


def _tasks_for_move(
    db: Session,
    rule: models.AutomationRule,
    *,
    source_task: Optional[models.Task],
    source_client: Optional[models.Client],
    from_id: int,
) -> list[models.Task]:
    scope = rule.move_scope or models.MoveScope.CLIENT_STAGE
    if isinstance(scope, str):
        try:
            scope = models.MoveScope(scope)
        except ValueError:
            scope = models.MoveScope.CLIENT_STAGE

    client = _resolve_client(source_task, source_client)

    if scope == models.MoveScope.TRIGGER_TASK:
        if source_task is None:
            return []
        if source_task.stage_id != from_id:
            return []
        return [source_task]

    query = db.query(models.Task).filter(models.Task.stage_id == from_id)
    if scope == models.MoveScope.CLIENT_STAGE:
        if client is not None:
            query = query.filter(models.Task.client_id == client.id)
        elif rule.condition_client_id:
            query = query.filter(models.Task.client_id == rule.condition_client_id)
        else:
            # без клиента нечего фильтровать — как all_stage
            pass
    # ALL_STAGE — без доп. фильтра
    return query.all()


def move_tasks_from_rule(
    db: Session,
    rule: models.AutomationRule,
    *,
    source_task: Optional[models.Task] = None,
    source_client: Optional[models.Client] = None,
) -> list[models.Task]:
    """Переместить задачи с move_from_stage на target_stage.

    Не запускает цепочку status_change-правил (чтобы избежать циклов).
    """
    from_id = rule.move_from_stage_id
    to_id = rule.target_stage_id
    if not from_id or not to_id or from_id == to_id:
        return []

    from_stage = get_stage(db, from_id)
    to_stage = get_stage(db, to_id)
    if from_stage is None or to_stage is None:
        return []

    tasks = _tasks_for_move(
        db,
        rule,
        source_task=source_task,
        source_client=source_client,
        from_id=from_id,
    )
    moved = []
    for task in tasks:
        old_key = from_stage.key
        task.stage_id = to_stage.id
        task.status = to_stage.key
        db.add(
            models.Comment(
                task_id=task.id,
                author_id=rule.creator_id,
                text="",
                is_status_change=True,
                from_status=old_key,
                to_status=to_stage.key,
            )
        )
        add_event(
            db,
            task.id,
            models.TimelineEventType.STATUS_CHANGED,
            "Стадия изменена автоматически",
            actor_id=rule.creator_id,
            detail=f"{from_stage.name} → {to_stage.name}",
            meta={
                "via": "automation",
                "rule_id": rule.id,
                "from_stage_id": from_stage.id,
                "to_stage_id": to_stage.id,
                "from_status": old_key,
                "to_status": to_stage.key,
            },
        )
        if task.client_id:
            add_client_event(
                db,
                task.client_id,
                models.ClientEventType.AUTOMATION,
                f"Задача перемещена: {task.title}",
                actor_id=rule.creator_id,
                detail=f"{from_stage.name} → {to_stage.name} · правило «{rule.name}»",
                meta={"rule_id": rule.id, "task_id": task.id},
            )
        moved.append(task)
    return moved


def execute_rule(
    db: Session,
    rule: models.AutomationRule,
    *,
    source_task: Optional[models.Task] = None,
    source_client: Optional[models.Client] = None,
    source_mail: Optional[models.MailMessage] = None,
) -> Optional[models.Task]:
    action = rule.action_type or models.AutomationAction.CREATE_TASK
    if isinstance(action, str):
        action = models.AutomationAction(action)

    if action == models.AutomationAction.SEND_EMAIL:
        send_email_from_rule(
            db,
            rule,
            source_task=source_task,
            source_client=source_client,
            source_mail=source_mail,
        )
        return None
    if action == models.AutomationAction.MOVE_TASKS:
        moved = move_tasks_from_rule(
            db, rule, source_task=source_task, source_client=source_client
        )
        return moved[0] if moved else None
    return create_task_from_rule(
        db,
        rule,
        source_task=source_task,
        source_client=source_client,
        source_mail=source_mail,
    )


def _wants_no_stage_task(rule: models.AutomationRule) -> bool:
    if getattr(rule, "condition_no_stage_task", False):
        return True
    # legacy trigger_type
    return rule.trigger_type == models.AutomationTrigger.CLIENT_NO_STAGE_TASK


def _client_has_task_on_stage(
    db: Session, client_id: int, stage_id: int
) -> bool:
    return (
        db.query(models.Task)
        .filter(
            models.Task.client_id == client_id,
            models.Task.stage_id == stage_id,
        )
        .first()
        is not None
    )


def _client_has_any_task(db: Session, client_id: int) -> bool:
    return (
        db.query(models.Task)
        .filter(models.Task.client_id == client_id)
        .first()
        is not None
    )


def client_passes_conditions(
    db: Session,
    rule: models.AutomationRule,
    client: Optional[models.Client],
) -> bool:
    """Проверить дополнительные условия правила для клиента."""
    if rule.condition_client_id is not None:
        if client is None or client.id != rule.condition_client_id:
            return False

    if getattr(rule, "condition_no_tasks", False):
        if client is None:
            return False
        if _client_has_any_task(db, client.id):
            return False

    if _wants_no_stage_task(rule):
        if not rule.condition_stage_id:
            return False
        if client is None:
            return False
        if _client_has_task_on_stage(db, client.id, rule.condition_stage_id):
            return False
    return True


def _clients_for_rule(db: Session, rule: models.AutomationRule) -> list[models.Client]:
    if rule.condition_client_id:
        return (
            db.query(models.Client)
            .filter(models.Client.id == rule.condition_client_id)
            .all()
        )
    return db.query(models.Client).all()


def _already_fired_since_activity(
    db: Session, rule_id: int, client_id: int, last_activity: datetime
) -> bool:
    fire = (
        db.query(models.AutomationFire)
        .filter(
            models.AutomationFire.rule_id == rule_id,
            models.AutomationFire.client_id == client_id,
            models.AutomationFire.fired_at >= last_activity,
        )
        .first()
    )
    return fire is not None


def _should_skip_client_fire(
    db: Session, rule: models.AutomationRule, client_id: int, now: datetime
) -> bool:
    """Антиспам: не повторять, пока жива связанная задача / чаще раза в сутки."""
    recent_fire = (
        db.query(models.AutomationFire)
        .filter(
            models.AutomationFire.rule_id == rule.id,
            models.AutomationFire.client_id == client_id,
        )
        .order_by(models.AutomationFire.fired_at.desc())
        .first()
    )
    if not recent_fire:
        return False
    if recent_fire.task_id:
        still = (
            db.query(models.Task).filter(models.Task.id == recent_fire.task_id).first()
        )
        if still:
            return True
        return False
    if recent_fire.fired_at and recent_fire.fired_at.date() == now.date():
        return True
    return False


def _fire_for_client(
    db: Session,
    rule: models.AutomationRule,
    client: models.Client,
    now: datetime,
    *,
    source_task: Optional[models.Task] = None,
    source_mail: Optional[models.MailMessage] = None,
) -> Optional[models.Task]:
    task = execute_rule(
        db,
        rule,
        source_task=source_task,
        source_client=client,
        source_mail=source_mail,
    )
    db.add(
        models.AutomationFire(
            rule_id=rule.id,
            client_id=client.id,
            task_id=task.id if task else None,
            fired_at=now,
        )
    )
    return task


def run_client_email_rules(
    db: Session,
    *,
    client: models.Client,
    source_mail: models.MailMessage,
    source_task: Optional[models.Task] = None,
) -> list[models.Task]:
    """Триггер: новое входящее письмо от клиента."""
    rules = (
        db.query(models.AutomationRule)
        .filter(
            models.AutomationRule.enabled.is_(True),
            models.AutomationRule.trigger_type
            == models.AutomationTrigger.CLIENT_EMAIL,
        )
        .all()
    )
    created: list[models.Task] = []
    now = datetime.utcnow()
    for rule in rules:
        if not client_passes_conditions(db, rule, client):
            continue
        task = _fire_for_client(
            db,
            rule,
            client,
            now,
            source_task=source_task,
            source_mail=source_mail,
        )
        if task is not None:
            created.append(task)
    return created


def run_status_change_rules(
    db: Session,
    source_task: models.Task,
    old_stage: Optional[models.Stage],
    new_stage: models.Stage,
) -> list[models.Task]:
    rules = (
        db.query(models.AutomationRule)
        .filter(
            models.AutomationRule.enabled.is_(True),
            models.AutomationRule.trigger_type == models.AutomationTrigger.STATUS_CHANGE,
            models.AutomationRule.watch_to_stage_id == new_stage.id,
        )
        .all()
    )
    created = []
    now = datetime.utcnow()
    for rule in rules:
        if rule.watch_from_stage_id is not None:
            if old_stage is None or rule.watch_from_stage_id != old_stage.id:
                continue
        client = source_task.client
        if not client_passes_conditions(db, rule, client):
            continue
        if client is not None:
            if _should_skip_client_fire(db, rule, client.id, now):
                continue
            task = _fire_for_client(
                db, rule, client, now, source_task=source_task
            )
        else:
            # условия без клиента не требуют client_id — просто действие
            if (
                _wants_no_stage_task(rule)
                or rule.condition_client_id
                or getattr(rule, "condition_no_tasks", False)
            ):
                continue
            task = execute_rule(db, rule, source_task=source_task)
        if task is not None:
            created.append(task)
    return created


def _should_run_schedule(rule: models.AutomationRule, now: datetime) -> bool:
    try:
        hour, minute = [int(x) for x in (rule.schedule_time or "09:00").split(":")]
    except ValueError:
        hour, minute = 9, 0

    if now.hour != hour or now.minute != minute:
        return False

    if rule.schedule_interval == models.ScheduleInterval.WEEKLY:
        weekday = rule.schedule_weekday if rule.schedule_weekday is not None else 0
        if now.weekday() != weekday:
            return False

    if rule.last_run_at and rule.last_run_at.date() == now.date():
        if (
            rule.last_run_at.hour == now.hour
            and rule.last_run_at.minute == now.minute
        ):
            return False
        if rule.schedule_interval == models.ScheduleInterval.DAILY:
            return False
        if rule.schedule_interval == models.ScheduleInterval.WEEKLY:
            return False

    return True


def run_due_schedule_rules(db: Session, now: Optional[datetime] = None) -> list[models.Task]:
    now = now or datetime.utcnow()
    rules = (
        db.query(models.AutomationRule)
        .filter(
            models.AutomationRule.enabled.is_(True),
            models.AutomationRule.trigger_type == models.AutomationTrigger.SCHEDULE,
        )
        .all()
    )
    created = []
    for rule in rules:
        if not _should_run_schedule(rule, now):
            continue

        # С условиями по клиенту — проверяем каждого клиента
        if (
            _wants_no_stage_task(rule)
            or rule.condition_client_id
            or getattr(rule, "condition_no_tasks", False)
        ):
            for client in _clients_for_rule(db, rule):
                if not client_passes_conditions(db, rule, client):
                    continue
                if _should_skip_client_fire(db, rule, client.id, now):
                    continue
                task = _fire_for_client(db, rule, client, now)
                if task is not None:
                    created.append(task)
        else:
            task = execute_rule(db, rule)
            if task is not None:
                created.append(task)
        rule.last_run_at = now
    return created


def run_client_inactive_rules(
    db: Session, now: Optional[datetime] = None
) -> list[models.Task]:
    now = now or datetime.utcnow()
    rules = (
        db.query(models.AutomationRule)
        .filter(
            models.AutomationRule.enabled.is_(True),
            models.AutomationRule.trigger_type
            == models.AutomationTrigger.CLIENT_INACTIVE,
        )
        .all()
    )
    if not rules:
        return []

    created = []
    for rule in rules:
        days = rule.inactivity_days or 30
        threshold = now - timedelta(days=days)
        for client in _clients_for_rule(db, rule):
            last_activity = client_last_activity_at(db, client)
            if last_activity > threshold:
                continue
            if not client_passes_conditions(db, rule, client):
                continue
            if _already_fired_since_activity(db, rule.id, client.id, last_activity):
                continue
            if _should_skip_client_fire(db, rule, client.id, now):
                continue
            task = _fire_for_client(db, rule, client, now)
            if task is not None:
                created.append(task)
        rule.last_run_at = now
    return created


def run_scheduled_jobs(db: Session, now: Optional[datetime] = None) -> list[models.Task]:
    now = now or datetime.utcnow()
    created = []
    created.extend(run_due_schedule_rules(db, now))
    created.extend(run_client_inactive_rules(db, now))
    db.commit()
    return created


# Как часто фоном забирать входящую почту (секунды)
INBOUND_MAIL_POLL_SECONDS = 30


async def _notify_inbound_mails(db: Session, mails: list) -> None:
    """Пушим в WebSocket, чтобы бейджи непрочитанного обновились без открытия задачи."""
    if not mails:
        return
    from sqlalchemy.orm import joinedload

    from .ws import manager

    notified_tasks: set[int] = set()
    for mail in mails:
        if mail.task_id and mail.task_id not in notified_tasks:
            task = (
                db.query(models.Task)
                .options(
                    joinedload(models.Task.assignees),
                    joinedload(models.Task.observers),
                )
                .filter(models.Task.id == mail.task_id)
                .first()
            )
            if task:
                await manager.notify_task_event(
                    db, task, "email_received", actor_id=None
                )
                notified_tasks.add(mail.task_id)
        elif not mail.task_id and mail.client_id:
            # письмо только к клиенту — уведомим админов
            admin_ids = [
                u.id
                for u in db.query(models.User).filter(models.User.is_admin.is_(True)).all()
            ]
            message = {
                "type": "email_received",
                "task_id": None,
                "client_id": mail.client_id,
            }
            for uid in admin_ids:
                await manager.send_to_user(uid, message)


async def automation_loop(stop_event: asyncio.Event):
    from . import email_service

    while not stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                run_scheduled_jobs(db)
                try:
                    saved = email_service.fetch_inbound_emails(db)
                    await _notify_inbound_mails(db, saved)
                except Exception:
                    pass
            finally:
                db.close()
        except Exception:
            pass
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=INBOUND_MAIL_POLL_SECONDS
            )
        except asyncio.TimeoutError:
            continue


def rule_to_dict(rule: models.AutomationRule) -> dict:
    action = rule.action_type or models.AutomationAction.CREATE_TASK
    if hasattr(action, "value"):
        action = action.value
    trigger = rule.trigger_type.value if rule.trigger_type else "schedule"
    no_stage = bool(getattr(rule, "condition_no_stage_task", False))
    # legacy: client_no_stage_task как триггер → отдаём как schedule + условие
    if trigger == models.AutomationTrigger.CLIENT_NO_STAGE_TASK.value:
        trigger = models.AutomationTrigger.SCHEDULE.value
        no_stage = True
    return {
        "id": rule.id,
        "name": rule.name,
        "enabled": rule.enabled,
        "trigger_type": trigger,
        "action_type": action,
        "schedule_interval": rule.schedule_interval.value if rule.schedule_interval else None,
        "schedule_time": rule.schedule_time,
        "schedule_weekday": rule.schedule_weekday,
        "last_run_at": rule.last_run_at,
        "watch_from_stage_id": rule.watch_from_stage_id,
        "watch_to_stage_id": rule.watch_to_stage_id,
        "watch_from_status": rule.watch_from_status,
        "watch_to_status": rule.watch_to_status,
        "inactivity_days": rule.inactivity_days,
        "condition_no_stage_task": no_stage,
        "condition_stage_id": rule.condition_stage_id,
        "condition_client_id": rule.condition_client_id,
        "condition_no_tasks": bool(getattr(rule, "condition_no_tasks", False)),
        "target_stage_id": rule.target_stage_id,
        "move_from_stage_id": rule.move_from_stage_id,
        "move_scope": (
            rule.move_scope.value
            if getattr(rule, "move_scope", None) and hasattr(rule.move_scope, "value")
            else (rule.move_scope or models.MoveScope.CLIENT_STAGE.value)
        ),
        "email_to_template": rule.email_to_template or "",
        "title_template": rule.title_template,
        "description_template": rule.description_template,
        "creator_id": rule.creator_id,
        "assignee_ids": _parse_ids(rule.assignee_ids_json),
        "observer_ids": _parse_ids(rule.observer_ids_json),
        "due_offset_days": rule.due_offset_days,
        "created_at": rule.created_at,
        "creator": rule.creator,
    }


def load_rules(db: Session) -> list[models.AutomationRule]:
    return (
        db.query(models.AutomationRule)
        .options(joinedload(models.AutomationRule.creator))
        .order_by(models.AutomationRule.id.desc())
        .all()
    )
