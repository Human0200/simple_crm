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
)
from sqlalchemy.orm import relationship

from .database import Base


class TaskStatus(str, enum.Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class UserRole(str, enum.Enum):
    CREATOR = "creator"  # может ставить задачи, быть исполнителем и наблюдателем
    EXECUTOR = "executor"  # может быть исполнителем и наблюдателем, но не ставит задачи
    OBSERVER = "observer"  # может быть только наблюдателем


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
    """Разрешение: участники from_team могут ставить задачи участникам to_team."""

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


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(Enum(TaskStatus), default=TaskStatus.BACKLOG, nullable=False)
    due_date = Column(Date, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    creator = relationship(
        "User", back_populates="created_tasks", foreign_keys=[creator_id]
    )
    assignees = relationship(
        "User", secondary=task_assignees, back_populates="assigned_tasks"
    )
    observers = relationship(
        "User", secondary=task_observers, back_populates="observed_tasks"
    )
    comments = relationship(
        "Comment", back_populates="task", cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    is_status_change = Column(Boolean, default=False)
    is_result = Column(Boolean, default=False)
    from_status = Column(Enum(TaskStatus), nullable=True)
    to_status = Column(Enum(TaskStatus), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="comments")
    author = relationship("User", back_populates="comments")
