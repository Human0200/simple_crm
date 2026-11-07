"""Простые миграции SQLite: новые таблицы через create_all, недостающие колонки — ALTER."""

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .database import engine, Base, SessionLocal
from . import models  # noqa: F401
from .stages import ensure_default_stages
from .permissions import ensure_role_permissions


def _existing_columns(table: str) -> set[str]:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _add_column(table: str, column_sql: str):
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_sql}"))


def _fix_inbound_mail_utc():
    """
    Раньше Date из письма (+03:00) сохраняли как naive без перевода в UTC,
    фронт добавлял Z → +3 часа на экране. Сдвигаем старые inbound на -3 часа один раз.
    """
    with engine.begin() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            ).fetchall()
        }
        if "mail_messages" not in tables:
            return
        if "_meta_inbound_mail_utc_v1" in tables:
            return
        conn.execute(
            text(
                "UPDATE mail_messages "
                "SET created_at = datetime(created_at, '-3 hours') "
                "WHERE direction IN ('inbound', 'INBOUND')"
            )
        )
        conn.execute(text("CREATE TABLE _meta_inbound_mail_utc_v1 (ok INTEGER)"))


def _migrate_stage_key_uniqueness():
    """Снять глобальный UNIQUE на stages.key, добавить unique (funnel_id, key)."""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT name, sql FROM sqlite_master "
                "WHERE tbl_name = 'stages' AND type = 'index'"
            )
        ).fetchall()
        for name, sql in rows:
            sql_l = (sql or "").lower()
            if name == "ix_stages_key" and "unique" in sql_l:
                conn.execute(text("DROP INDEX IF EXISTS ix_stages_key"))
                conn.execute(
                    text('CREATE INDEX IF NOT EXISTS ix_stages_key ON stages ("key")')
                )
        exists = conn.execute(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'index' AND name = 'uq_stage_funnel_key'"
            )
        ).fetchone()
        if not exists:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_stage_funnel_key "
                    'ON stages (funnel_id, "key")'
                )
            )


def _migrate_task_stages(db: Session):
    stages = ensure_default_stages(db)
    by_key = {s.key: s for s in stages}
    tasks = db.query(models.Task).all()
    changed = False
    for task in tasks:
        if task.stage_id:
            # синхронизируем legacy status
            if task.stage and task.status != task.stage.key:
                task.status = task.stage.key
                changed = True
            continue
        key = task.status
        if hasattr(key, "value"):
            key = key.value
        key = str(key or "backlog")
        stage = by_key.get(key) or stages[0]
        task.stage_id = stage.id
        task.status = stage.key
        changed = True
    if changed:
        db.commit()


def _migrate_automation_stage_refs(db: Session):
    stages = {s.key: s for s in ensure_default_stages(db)}
    rules = db.query(models.AutomationRule).all()
    changed = False
    for rule in rules:
        if rule.watch_to_status and not rule.watch_to_stage_id:
            st = stages.get(str(rule.watch_to_status))
            if st:
                rule.watch_to_stage_id = st.id
                changed = True
        if rule.watch_from_status and not rule.watch_from_stage_id:
            st = stages.get(str(rule.watch_from_status))
            if st:
                rule.watch_from_stage_id = st.id
                changed = True
    if changed:
        db.commit()


def migrate():
    Base.metadata.create_all(bind=engine)

    user_cols = _existing_columns("users")
    if user_cols and "email" not in user_cols:
        _add_column("users", "email VARCHAR DEFAULT ''")

    task_cols = _existing_columns("tasks")
    if task_cols and "client_id" not in task_cols:
        _add_column("tasks", "client_id INTEGER")
    if task_cols and "stage_id" not in task_cols:
        _add_column("tasks", "stage_id INTEGER")

    rule_cols = _existing_columns("automation_rules")
    if rule_cols and "inactivity_days" not in rule_cols:
        _add_column("automation_rules", "inactivity_days INTEGER")
    if rule_cols and "watch_from_stage_id" not in rule_cols:
        _add_column("automation_rules", "watch_from_stage_id INTEGER")
    if rule_cols and "watch_to_stage_id" not in rule_cols:
        _add_column("automation_rules", "watch_to_stage_id INTEGER")
    if rule_cols and "condition_stage_id" not in rule_cols:
        _add_column("automation_rules", "condition_stage_id INTEGER")
    if rule_cols and "condition_client_id" not in rule_cols:
        _add_column("automation_rules", "condition_client_id INTEGER")
    if rule_cols and "target_stage_id" not in rule_cols:
        _add_column("automation_rules", "target_stage_id INTEGER")
    if rule_cols and "action_type" not in rule_cols:
        _add_column(
            "automation_rules",
            "action_type VARCHAR DEFAULT 'create_task'",
        )
    if rule_cols and "email_to_template" not in rule_cols:
        _add_column("automation_rules", "email_to_template VARCHAR DEFAULT ''")
    if rule_cols and "condition_no_stage_task" not in rule_cols:
        _add_column(
            "automation_rules",
            "condition_no_stage_task BOOLEAN DEFAULT 0",
        )
    if rule_cols and "condition_no_tasks" not in rule_cols:
        _add_column(
            "automation_rules",
            "condition_no_tasks BOOLEAN DEFAULT 0",
        )
    if rule_cols and "move_from_stage_id" not in rule_cols:
        _add_column("automation_rules", "move_from_stage_id INTEGER")
    if rule_cols and "move_scope" not in rule_cols:
        _add_column(
            "automation_rules",
            "move_scope VARCHAR DEFAULT 'client_stage'",
        )

    email_cols = _existing_columns("email_settings")
    for col, sql in (
        ("imap_host", "imap_host VARCHAR DEFAULT ''"),
        ("imap_port", "imap_port INTEGER DEFAULT 993"),
        ("imap_user", "imap_user VARCHAR DEFAULT ''"),
        ("imap_password", "imap_password VARCHAR DEFAULT ''"),
        ("imap_use_ssl", "imap_use_ssl BOOLEAN DEFAULT 1"),
        ("imap_folder", "imap_folder VARCHAR DEFAULT 'INBOX'"),
        ("imap_last_uid", "imap_last_uid INTEGER DEFAULT 0"),
    ):
        if email_cols and col not in email_cols:
            _add_column("email_settings", sql)

    stage_cols = _existing_columns("stages")
    if stage_cols and "funnel_id" not in stage_cols:
        _add_column("stages", "funnel_id INTEGER")

    client_cols = _existing_columns("clients")
    if client_cols and "owner_team_id" not in client_cols:
        _add_column("clients", "owner_team_id INTEGER")

    # раньше key был глобально уникален; для воронок нужен unique (funnel_id, key)
    _migrate_stage_key_uniqueness()
    _fix_inbound_mail_utc()

    db = SessionLocal()
    try:
        ensure_default_stages(db)
        ensure_role_permissions(db)
        _migrate_task_stages(db)
        _migrate_automation_stage_refs(db)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE automation_rules SET action_type = 'create_task' "
                    "WHERE action_type IS NULL OR action_type = ''"
                )
            )
            # «нет задачи на стадии» было триггером → условие + расписание
            conn.execute(
                text(
                    "UPDATE automation_rules SET "
                    "condition_no_stage_task = 1, "
                    "trigger_type = 'schedule', "
                    "schedule_interval = COALESCE(schedule_interval, 'daily'), "
                    "schedule_time = COALESCE(NULLIF(schedule_time, ''), '09:00') "
                    "WHERE trigger_type = 'client_no_stage_task'"
                )
            )
            conn.execute(
                text(
                    "UPDATE automation_rules SET condition_no_stage_task = 0 "
                    "WHERE condition_no_stage_task IS NULL"
                )
            )
    finally:
        db.close()
