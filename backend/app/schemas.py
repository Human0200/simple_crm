from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from .models import (
    UserRole,
    AutomationTrigger,
    AutomationAction,
    MoveScope,
    ScheduleInterval,
    TimelineEventType,
    ClientEventType,
)


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserCapabilities(BaseModel):
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_edit_any: bool = False
    can_delete_any: bool = False


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str = ""
    bio: str = ""
    avatar_url: Optional[str] = None
    is_admin: bool = False
    role: UserRole = UserRole.CREATOR
    teams: List[TeamOut] = []
    capabilities: Optional[UserCapabilities] = None


class TeamWithMembersOut(TeamOut):
    members: List[UserOut] = []


class TeamCreate(BaseModel):
    name: str


class TeamMemberIn(BaseModel):
    user_id: int


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_team: TeamOut
    to_team: TeamOut


class PermissionCreate(BaseModel):
    from_team_id: int
    to_team_id: int


class FunnelPermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    funnel_id: int
    team: TeamOut
    funnel: "FunnelBriefOut"


class FunnelBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    team_id: Optional[int] = None


class FunnelPermissionCreate(BaseModel):
    team_id: int
    funnel_id: int


class RolePermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: UserRole
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_edit_any: bool = False
    can_delete_any: bool = False


class RolePermissionUpdate(BaseModel):
    can_create: bool
    can_edit: bool
    can_delete: bool
    can_edit_any: bool = False
    can_delete_any: bool = False


class AdminUserCreate(BaseModel):
    username: str
    full_name: str
    password: str
    email: str = ""


class AdminUserRoleUpdate(BaseModel):
    role: UserRole


class ProfileUpdate(BaseModel):
    full_name: str
    bio: str = ""
    email: str = ""


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginIn(BaseModel):
    username: str
    password: str


class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    funnel_id: Optional[int] = None
    key: str
    name: str
    position: int
    assignee_can_set: bool = True
    requires_result: bool = False
    is_final: bool = False


class StageCreate(BaseModel):
    name: str
    funnel_id: Optional[int] = None
    assignee_can_set: bool = True
    requires_result: bool = False
    is_final: bool = False


class StageUpdate(BaseModel):
    name: Optional[str] = None
    assignee_can_set: Optional[bool] = None
    requires_result: Optional[bool] = None
    is_final: Optional[bool] = None
    position: Optional[int] = None


class StageReorderIn(BaseModel):
    stage_ids: List[int]
    funnel_id: Optional[int] = None


class FunnelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    position: int
    is_default: bool = False
    team_id: Optional[int] = None
    team: Optional[TeamOut] = None
    stages: List[StageOut] = []


class FunnelCreate(BaseModel):
    name: str
    team_id: Optional[int] = None
    is_default: bool = False
    with_default_stages: bool = True


class FunnelUpdate(BaseModel):
    name: Optional[str] = None
    team_id: Optional[int] = None
    is_default: Optional[bool] = None
    position: Optional[int] = None


class FunnelReorderIn(BaseModel):
    funnel_ids: List[int]


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    is_status_change: bool
    is_result: bool = False
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    created_at: datetime
    author: UserOut


class CommentIn(BaseModel):
    text: str
    is_result: bool = False


class CommentResultUpdate(BaseModel):
    is_result: bool


class ClientBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    company: str = ""
    email: str = ""
    phone: str = ""


class ClientCreate(BaseModel):
    name: str
    company: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""


class ClientUpdate(BaseModel):
    name: str
    company: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""


class ClientNoteIn(BaseModel):
    text: str


class ClientTimelineEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: ClientEventType
    title: str
    detail: str = ""
    meta_json: str = ""
    created_at: datetime
    actor: Optional[UserOut] = None


class ClientOut(ClientBriefOut):
    notes: str = ""
    created_at: datetime
    updated_at: datetime
    last_activity_at: Optional[datetime] = None
    tasks_count: int = 0


class ClientDetailOut(ClientOut):
    timeline: List[ClientTimelineEventOut] = []


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[date] = None
    assignee_ids: List[int] = []
    observer_ids: List[int] = []
    creator_id: Optional[int] = None
    client_id: Optional[int] = None
    funnel_id: Optional[int] = None
    stage_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[date] = None
    assignee_ids: List[int] = []
    observer_ids: List[int] = []
    client_id: Optional[int] = None


class TaskStatusChange(BaseModel):
    stage_id: Optional[int] = None
    status: Optional[str] = None  # legacy: stage key


class UnreadCounts(BaseModel):
    comments: int = 0
    results: int = 0
    timeline: int = 0
    email: int = 0
    total: int = 0


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    stage_id: Optional[int] = None
    stage: Optional[StageOut] = None
    due_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    creator: UserOut
    assignees: List[UserOut]
    observers: List[UserOut]
    client: Optional[ClientBriefOut] = None
    unread: UnreadCounts = UnreadCounts()


class TimelineEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: TimelineEventType
    title: str
    detail: str = ""
    meta_json: str = ""
    created_at: datetime
    actor: Optional[UserOut] = None


class TaskDetailOut(TaskOut):
    comments: List[CommentOut]
    timeline: List[TimelineEventOut] = []


class TaskReadIn(BaseModel):
    tabs: List[str]


class UnreadTaskItem(BaseModel):
    task_id: int
    title: str
    status: str
    comments: int = 0
    results: int = 0
    timeline: int = 0
    email: int = 0
    total: int = 0


class UnreadSummaryOut(BaseModel):
    total: int = 0
    items: List[UnreadTaskItem] = []


class TaskEmailIn(BaseModel):
    to_emails: List[str]
    cc_emails: List[str] = []
    subject: str
    body: str

    @field_validator("to_emails")
    @classmethod
    def non_empty_to(cls, v: List[str]) -> List[str]:
        cleaned = [e.strip() for e in v if e and e.strip()]
        if not cleaned:
            raise ValueError("Укажите получателя")
        return cleaned


class EmailSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    from_email: str = ""
    from_name: str = "Simple CRM"
    use_tls: bool = True
    use_ssl: bool = False
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_use_ssl: bool = True
    imap_folder: str = "INBOX"
    configured: bool = False
    imap_configured: bool = False
    has_password: bool = False
    has_imap_password: bool = False


class EmailSettingsUpdate(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: Optional[str] = None
    from_email: str
    from_name: str = "Simple CRM"
    use_tls: bool = True
    use_ssl: bool = False
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: Optional[str] = None
    imap_use_ssl: bool = True
    imap_folder: str = "INBOX"


class EmailTestIn(BaseModel):
    to_email: str


class MailMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: Optional[int] = None
    task_id: Optional[int] = None
    direction: str
    subject: str = ""
    body: str = ""
    from_addr: str = ""
    to_addrs: List[str] = []
    cc_addrs: List[str] = []
    message_id: str = ""
    in_reply_to: str = ""
    actor_id: Optional[int] = None
    created_at: datetime
    actor: Optional[UserOut] = None


class AutomationRuleIn(BaseModel):
    name: str
    enabled: bool = True
    trigger_type: AutomationTrigger
    action_type: AutomationAction = AutomationAction.CREATE_TASK
    schedule_interval: Optional[ScheduleInterval] = None
    schedule_time: str = "09:00"
    schedule_weekday: Optional[int] = None
    watch_from_stage_id: Optional[int] = None
    watch_to_stage_id: Optional[int] = None
    inactivity_days: Optional[int] = None
    condition_no_stage_task: bool = False
    condition_stage_id: Optional[int] = None
    condition_client_id: Optional[int] = None
    condition_no_tasks: bool = False
    target_stage_id: Optional[int] = None
    move_from_stage_id: Optional[int] = None
    move_scope: MoveScope = MoveScope.CLIENT_STAGE
    email_to_template: str = ""
    title_template: str = ""
    description_template: str = ""
    creator_id: int
    assignee_ids: List[int] = []
    observer_ids: List[int] = []
    due_offset_days: Optional[int] = None


class AutomationRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    enabled: bool
    trigger_type: AutomationTrigger
    action_type: AutomationAction = AutomationAction.CREATE_TASK
    schedule_interval: Optional[ScheduleInterval] = None
    schedule_time: Optional[str] = None
    schedule_weekday: Optional[int] = None
    last_run_at: Optional[datetime] = None
    watch_from_stage_id: Optional[int] = None
    watch_to_stage_id: Optional[int] = None
    watch_from_status: Optional[str] = None
    watch_to_status: Optional[str] = None
    inactivity_days: Optional[int] = None
    condition_no_stage_task: bool = False
    condition_stage_id: Optional[int] = None
    condition_client_id: Optional[int] = None
    condition_no_tasks: bool = False
    target_stage_id: Optional[int] = None
    move_from_stage_id: Optional[int] = None
    move_scope: MoveScope = MoveScope.CLIENT_STAGE
    email_to_template: str = ""
    title_template: str
    description_template: str = ""
    creator_id: int
    assignee_ids: List[int] = []
    observer_ids: List[int] = []
    due_offset_days: Optional[int] = None
    created_at: datetime
    creator: UserOut


# --- API tokens / external API ---


class ApiTokenCreate(BaseModel):
    name: str
    actor_user_id: Optional[int] = None


class ApiTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    token_prefix: str
    enabled: bool
    created_by_id: int
    actor_user_id: int
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_by: Optional[UserOut] = None
    actor_user: Optional[UserOut] = None


class ApiTokenCreatedOut(ApiTokenOut):
    """Ответ при создании: сырой токен показывается один раз."""

    token: str


class ExtTaskIn(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[date] = None
    assignee_ids: List[int] = []
    observer_ids: List[int] = []
    creator_id: Optional[int] = None
    client_id: Optional[int] = None
    stage_id: Optional[int] = None


class ExtTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[date] = None
    assignee_ids: Optional[List[int]] = None
    observer_ids: Optional[List[int]] = None
    client_id: Optional[int] = None
    stage_id: Optional[int] = None


class ExtTaskOut(BaseModel):
    id: int
    title: str
    description: str = ""
    status: str
    stage_id: Optional[int] = None
    due_date: Optional[date] = None
    creator_id: int
    client_id: Optional[int] = None
    assignee_ids: List[int] = []
    observer_ids: List[int] = []
    created_at: datetime
    updated_at: datetime


class ExtClientIn(BaseModel):
    name: str
    company: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""


class ExtClientUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class ExtClientOut(BaseModel):
    id: int
    name: str
    company: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""
    created_at: datetime
    updated_at: datetime
    tasks_count: int = 0

