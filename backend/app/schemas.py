from datetime import datetime, date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from .models import TaskStatus, UserRole


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    bio: str = ""
    avatar_url: Optional[str] = None
    is_admin: bool = False
    role: UserRole = UserRole.CREATOR
    teams: List[TeamOut] = []


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


class AdminUserCreate(BaseModel):
    username: str
    full_name: str
    password: str


class AdminUserRoleUpdate(BaseModel):
    role: UserRole


class ProfileUpdate(BaseModel):
    full_name: str
    bio: str = ""


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginIn(BaseModel):
    username: str
    password: str


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    is_status_change: bool
    is_result: bool = False
    from_status: Optional[TaskStatus] = None
    to_status: Optional[TaskStatus] = None
    created_at: datetime
    author: UserOut


class CommentIn(BaseModel):
    text: str
    is_result: bool = False


class CommentResultUpdate(BaseModel):
    is_result: bool


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[date] = None
    assignee_ids: List[int] = []
    observer_ids: List[int] = []
    creator_id: Optional[int] = None


class TaskUpdate(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[date] = None
    assignee_ids: List[int] = []
    observer_ids: List[int] = []


class TaskStatusChange(BaseModel):
    status: TaskStatus


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TaskStatus
    due_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    creator: UserOut
    assignees: List[UserOut]
    observers: List[UserOut]


class TaskDetailOut(TaskOut):
    comments: List[CommentOut]
