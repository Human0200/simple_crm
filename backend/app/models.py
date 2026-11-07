import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Date,
    ForeignKey,
    Enum,
    Table,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, enum.Enum):
    CREATOR = "creator"
    EXECUTOR = "executor"
    OBSERVER = "observer"


class AutomationTrigger(str, enum.Enum):
    SCHEDULE = "schedule"
    STATUS_CHANGE = "status_change"
    CLIENT_INACTIVE = "client_inactive"
    CLIENT_EMAIL = "client_email"
    # legacy: хранилось как триггер, теперь это условие condition_no_stage_task
    CLIENT_NO_STAGE_TASK = "client_no_stage_task"


class AutomationAction(str, enum.Enum):
    CREATE_TASK = "create_task"
    SEND_EMAIL = "send_email"
    MOVE_TASKS = "move_tasks"


class MoveScope(str, enum.Enum):
    """Какие задачи трогать в действии move_tasks."""

    TRIGGER_TASK = "trigger_task"  # задача из письма / смены стадии
    CLIENT_STAGE = "client_stage"  # все задачи клиента на исходной стадии
    ALL_STAGE = "all_stage"  # все задачи на исходной стадии


class ScheduleInterval(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class TimelineEventType(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    COMMENTED = "commented"
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    AUTOMATION = "automation"
    CLIENT_LINKED = "client_linked"


class ClientEventType(str, enum.Enum):
    CREATED = "created"
    UPDATED = "updated"
    NOTE = "note"
    TASK_LINKED = "task_linked"
    TASK_ACTIVITY = "task_activity"
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    AUTOMATION = "automation"


class MailDirection(str, enum.Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


# Устаревший enum — оставляем для чтения старых строк SQLite
class TaskStatus(str, enum.Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


task_assignees = Table(
    "task_assignees",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)

task_observers = Table(
    "task_observers",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("tasks.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)

team_members = Table(
    "team_members",
    Base.metadata,
    Column("team_id", Integer, ForeignKey("teams.id"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    email = Column(String, default="", nullable=False)
    bio = Column(Text, default="")
    avatar_url = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CREATOR, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    created_tasks = relationship(
        "Task", back_populates="creator", foreign_keys="Task.creator_id"
    )
    assigned_tasks = relationship(
        "Task", secondary=task_assignees, back_populates="assignees"
    )
    observed_tasks = relationship(
        "Task", secondary=task_observers, back_populates="observers"
    )
    comments = relationship("Comment", back_populates="author")
    teams = relationship("Team", secondary=team_members, back_populates="members")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("User", secondary=team_members, back_populates="teams")
    permissions_given = relationship(
        "TeamPermission",
        foreign_keys="TeamPermission.from_team_id",
        back_populates="from_team",
        cascade="all, delete-orphan",
    )
    permissions_received = relationship(
        "TeamPermission",
        foreign_keys="TeamPermission.to_team_id",
        back_populates="to_team",
        cascade="all, delete-orphan",
    )


class TeamPermission(Base):
    __tablename__ = "team_permissions"

    id = Column(Integer, primary_key=True, index=True)
    from_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    to_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    from_team = relationship(
        "Team", foreign_keys=[from_team_id], back_populates="permissions_given"
    )
    to_team = relationship(
        "Team", foreign_keys=[to_team_id], back_populates="permissions_received"
    )


class RolePermission(Base):
    """Действия с задачами по роли пользователя (вкладка «Права»)."""

    __tablename__ = "role_permissions"

    role = Column(Enum(UserRole), primary_key=True)
    can_create = Column(Boolean, default=False, nullable=False)
    can_edit = Column(Boolean, default=False, nullable=False)  # свои как постановщик
    can_delete = Column(Boolean, default=False, nullable=False)  # свои как постановщик
    can_edit_any = Column(Boolean, default=False, nullable=False)
    can_delete_any = Column(Boolean, default=False, nullable=False)


class Funnel(Base):
    """Воронка (отдельный канбан): у менеджеров / программистов — своя."""

    __tablename__ = "funnels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    # если задано — основная воронка этой команды (команда видит её всегда)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team")
    stages = relationship(
        "Stage",
        back_populates="funnel",
        cascade="all, delete-orphan",
        order_by="Stage.position",
    )
    visibility_grants = relationship(
        "FunnelPermission",
        back_populates="funnel",
        cascade="all, delete-orphan",
    )


class FunnelPermission(Base):
    """Право команды видеть чужую воронку (вкладка «Права»)."""

    __tablename__ = "funnel_permissions"
    __table_args__ = (
        UniqueConstraint("team_id", "funnel_id", name="uq_funnel_perm_team_funnel"),
    )

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    funnel_id = Column(Integer, ForeignKey("funnels.id"), nullable=False, index=True)

    team = relationship("Team")
    funnel = relationship("Funnel", back_populates="visibility_grants")


class Stage(Base):
    """Колонка канбана внутри воронки."""

    __tablename__ = "stages"
    __table_args__ = (UniqueConstraint("funnel_id", "key", name="uq_stage_funnel_key"),)

    id = Column(Integer, primary_key=True, index=True)
    funnel_id = Column(Integer, ForeignKey("funnels.id"), nullable=True, index=True)
    key = Column(String, nullable=False, index=True)  # unique вместе с funnel_id
    name = Column(String, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    assignee_can_set = Column(Boolean, default=True, nullable=False)
    requires_result = Column(Boolean, default=False, nullable=False)
    is_final = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    funnel = relationship("Funnel", back_populates="stages")
    tasks = relationship("Task", back_populates="stage")


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    company = Column(String, default="")
    email = Column(String, default="")
    phone = Column(String, default="")
    notes = Column(Text, default="")
    # команда-владелец: видит клиента «своя»; другие — только при доступе к воронке с задачей
    owner_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner_team = relationship("Team")
    tasks = relationship("Task", back_populates="client")
    timeline_events = relationship(
        "ClientTimelineEvent",
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="ClientTimelineEvent.created_at",
    )


class ClientTimelineEvent(Base):
    __tablename__ = "client_timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(Enum(ClientEventType), nullable=False)
    title = Column(String, nullable=False)
    detail = Column(Text, default="")
    meta_json = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    client = relationship("Client", back_populates="timeline_events")
    actor = relationship("User")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    # legacy column — читается при миграции; новые записи пишут stage.key
    status = Column(String, default="backlog", nullable=False)
    stage_id = Column(Integer, ForeignKey("stages.id"), nullable=True, index=True)
    due_date = Column(Date, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship(
        "User", back_populates="created_tasks", foreign_keys=[creator_id]
    )
    client = relationship("Client", back_populates="tasks")
    stage = relationship("Stage", back_populates="tasks")
    assignees = relationship(
        "User", secondary=task_assignees, back_populates="assigned_tasks"
    )
    observers = relationship(
        "User", secondary=task_observers, back_populates="observed_tasks"
    )
    comments = relationship(
        "Comment",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )
    timeline_events = relationship(
        "TimelineEvent",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TimelineEvent.created_at",
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    is_status_change = Column(Boolean, default=False)
    is_result = Column(Boolean, default=False)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="comments")
    author = relationship("User", back_populates="comments")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    event_type = Column(Enum(TimelineEventType), nullable=False)
    title = Column(String, nullable=False)
    detail = Column(Text, default="")
    meta_json = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    task = relationship("Task", back_populates="timeline_events")
    actor = relationship("User")


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    trigger_type = Column(Enum(AutomationTrigger), nullable=False)

    schedule_interval = Column(Enum(ScheduleInterval), nullable=True)
    schedule_time = Column(String, default="09:00")
    schedule_weekday = Column(Integer, nullable=True)
    last_run_at = Column(DateTime, nullable=True)

    # STATUS_CHANGE
    watch_from_stage_id = Column(Integer, ForeignKey("stages.id"), nullable=True)
    watch_to_stage_id = Column(Integer, ForeignKey("stages.id"), nullable=True)
    # legacy string keys (миграция)
    watch_from_status = Column(String, nullable=True)
    watch_to_status = Column(String, nullable=True)

    inactivity_days = Column(Integer, nullable=True)

    # Условия (фильтры после триггера)
    condition_no_stage_task = Column(Boolean, default=False, nullable=False)
    condition_stage_id = Column(Integer, ForeignKey("stages.id"), nullable=True)
    condition_client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    # у клиента нет ни одной задачи
    condition_no_tasks = Column(Boolean, default=False, nullable=False)

    # Стадия назначения: новая задача / куда перемещать
    target_stage_id = Column(Integer, ForeignKey("stages.id"), nullable=True)
    # MOVE_TASKS: откуда перемещать
    move_from_stage_id = Column(Integer, ForeignKey("stages.id"), nullable=True)
    # MOVE_TASKS: какую выборку задач перемещать
    move_scope = Column(
        Enum(MoveScope),
        default=MoveScope.CLIENT_STAGE,
        nullable=False,
    )

    # Действие при срабатывании условия
    action_type = Column(
        Enum(AutomationAction),
        default=AutomationAction.CREATE_TASK,
        nullable=False,
    )
    # SEND_EMAIL: кому (шаблон, напр. {client_email} или фиксированный адрес)
    email_to_template = Column(String, default="")

    title_template = Column(String, nullable=False, default="")
    description_template = Column(Text, default="")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_ids_json = Column(Text, default="[]")
    observer_ids_json = Column(Text, default="[]")
    due_offset_days = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User")
    watch_from_stage = relationship("Stage", foreign_keys=[watch_from_stage_id])
    watch_to_stage = relationship("Stage", foreign_keys=[watch_to_stage_id])
    condition_stage = relationship("Stage", foreign_keys=[condition_stage_id])
    condition_client = relationship("Client", foreign_keys=[condition_client_id])
    target_stage = relationship("Stage", foreign_keys=[target_stage_id])
    move_from_stage = relationship("Stage", foreign_keys=[move_from_stage_id])
    fires = relationship(
        "AutomationFire", back_populates="rule", cascade="all, delete-orphan"
    )


class AutomationFire(Base):
    __tablename__ = "automation_fires"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("automation_rules.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    fired_at = Column(DateTime, default=datetime.utcnow)

    rule = relationship("AutomationRule", back_populates="fires")
    client = relationship("Client")


class TaskReadState(Base):
    __tablename__ = "task_read_states"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)
    comments_seen_at = Column(DateTime, nullable=True)
    results_seen_at = Column(DateTime, nullable=True)
    timeline_seen_at = Column(DateTime, nullable=True)
    email_seen_at = Column(DateTime, nullable=True)


class EmailSettings(Base):
    __tablename__ = "email_settings"

    id = Column(Integer, primary_key=True)
    smtp_host = Column(String, default="")
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String, default="")
    smtp_password = Column(String, default="")
    from_email = Column(String, default="")
    from_name = Column(String, default="Simple CRM")
    use_tls = Column(Boolean, default=True)
    use_ssl = Column(Boolean, default=False)
    # IMAP — входящие ответы клиентов
    imap_host = Column(String, default="")
    imap_port = Column(Integer, default=993)
    imap_user = Column(String, default="")
    imap_password = Column(String, default="")
    imap_use_ssl = Column(Boolean, default=True)
    imap_folder = Column(String, default="INBOX")
    imap_last_uid = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MailMessage(Base):
    """Переписка с клиентом: исходящие и входящие письма."""

    __tablename__ = "mail_messages"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True, index=True)
    direction = Column(Enum(MailDirection), nullable=False)
    subject = Column(String, default="")
    body = Column(Text, default="")
    from_addr = Column(String, default="")
    to_addrs = Column(Text, default="")  # json list
    cc_addrs = Column(Text, default="")  # json list
    message_id = Column(String, default="", index=True)
    in_reply_to = Column(String, default="", index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    imap_uid = Column(String, default="", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    client = relationship("Client")
    task = relationship("Task")
    actor = relationship("User")


class ApiToken(Base):
    """Токен для внешнего API. Хранится только hash; сырой ключ показывают один раз."""

    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    token_prefix = Column(String, nullable=False)  # для отображения в UI
    token_hash = Column(String, nullable=False, unique=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # действия от имени этого пользователя
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)

    created_by = relationship("User", foreign_keys=[created_by_id])
    actor_user = relationship("User", foreign_keys=[actor_user_id])
