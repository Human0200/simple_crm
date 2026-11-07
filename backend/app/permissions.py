from typing import Optional

from sqlalchemy.orm import Session

from . import models

DEFAULT_ROLE_PERMISSIONS = {
    models.UserRole.CREATOR: {
        "can_create": True,
        "can_edit": True,
        "can_delete": True,
        "can_edit_any": False,
        "can_delete_any": False,
    },
    models.UserRole.EXECUTOR: {
        "can_create": False,
        "can_edit": False,
        "can_delete": False,
        "can_edit_any": False,
        "can_delete_any": False,
    },
    models.UserRole.OBSERVER: {
        "can_create": False,
        "can_edit": False,
        "can_delete": False,
        "can_edit_any": False,
        "can_delete_any": False,
    },
}


def ensure_role_permissions(db: Session) -> list[models.RolePermission]:
    rows = []
    for role, defaults in DEFAULT_ROLE_PERMISSIONS.items():
        row = (
            db.query(models.RolePermission)
            .filter(models.RolePermission.role == role)
            .first()
        )
        if row is None:
            row = models.RolePermission(role=role, **defaults)
            db.add(row)
        rows.append(row)
    db.commit()
    return (
        db.query(models.RolePermission)
        .order_by(models.RolePermission.role)
        .all()
    )


def get_role_permission(
    db: Session, role: models.UserRole
) -> models.RolePermission:
    row = (
        db.query(models.RolePermission)
        .filter(models.RolePermission.role == role)
        .first()
    )
    if row is None:
        ensure_role_permissions(db)
        row = (
            db.query(models.RolePermission)
            .filter(models.RolePermission.role == role)
            .first()
        )
    return row


def _team_connected(db: Session, viewer: models.User, other: models.User) -> bool:
    """Общая проверка видимости/связанности команд, без учёта роли.

    Пользователь без команды не ограничен (чтобы не ломать работу тех,
    кого ещё не включили в систему команд). Если у viewer есть команда(ы),
    связь есть, если other в той же команде, либо для команды(-д) viewer
    настроено явное право на команду(-ы) other.
    """
    if other.id == viewer.id:
        return True

    viewer_team_ids = {t.id for t in viewer.teams}
    if not viewer_team_ids:
        return True

    other_team_ids = {t.id for t in other.teams}
    if viewer_team_ids & other_team_ids:
        return True

    if not other_team_ids:
        return False

    allowed = (
        db.query(models.TeamPermission)
        .filter(
            models.TeamPermission.from_team_id.in_(viewer_team_ids),
            models.TeamPermission.to_team_id.in_(other_team_ids),
        )
        .first()
    )
    return allowed is not None


def can_assign(db: Session, creator: models.User, assignee: models.User) -> bool:
    """Может ли creator назначить assignee исполнителем задачи."""
    if creator.is_admin:
        return True
    if assignee.role == models.UserRole.OBSERVER:
        return False
    return _team_connected(db, creator, assignee)


def can_observe(db: Session, creator: models.User, observer: models.User) -> bool:
    """Может ли creator добавить observer наблюдателем задачи."""
    if creator.is_admin:
        return True
    return _team_connected(db, creator, observer)


def assignable_users(db: Session, creator: models.User) -> list[models.User]:
    all_users = db.query(models.User).all()
    if creator.is_admin:
        return all_users
    return [u for u in all_users if can_assign(db, creator, u)]


def observable_users(db: Session, creator: models.User) -> list[models.User]:
    all_users = db.query(models.User).all()
    if creator.is_admin:
        return all_users
    return [u for u in all_users if can_observe(db, creator, u)]


def can_create_task(db: Session, user: models.User) -> bool:
    if user.is_admin:
        return True
    perm = get_role_permission(db, user.role)
    return bool(perm and perm.can_create)


def can_edit_task(db: Session, user: models.User, task: models.Task) -> bool:
    if user.is_admin:
        return True
    perm = get_role_permission(db, user.role)
    if not perm:
        return False
    if perm.can_edit_any:
        return True
    if perm.can_edit and task.creator_id == user.id:
        return True
    return False


def can_delete_task(db: Session, user: models.User, task: models.Task) -> bool:
    if user.is_admin:
        return True
    perm = get_role_permission(db, user.role)
    if not perm:
        return False
    if perm.can_delete_any:
        return True
    if perm.can_delete and task.creator_id == user.id:
        return True
    return False


def capabilities_for_user(db: Session, user: models.User) -> dict:
    if user.is_admin:
        return {
            "can_create": True,
            "can_edit": True,
            "can_delete": True,
            "can_edit_any": True,
            "can_delete_any": True,
        }
    perm = get_role_permission(db, user.role)
    return {
        "can_create": bool(perm.can_create),
        "can_edit": bool(perm.can_edit),
        "can_delete": bool(perm.can_delete),
        "can_edit_any": bool(perm.can_edit_any),
        "can_delete_any": bool(perm.can_delete_any),
    }


def user_team_ids(user: models.User) -> set[int]:
    return {t.id for t in (user.teams or [])}


def can_see_funnel(
    db: Session, user: models.User, funnel: models.Funnel
) -> bool:
    """Видимость воронки: админ; владелец-команда; явное право; общая (без team_id) для всех."""
    if user.is_admin:
        return True
    teams = user_team_ids(user)
    if not teams:
        # без команды — только общие воронки (без привязки к команде)
        return funnel.team_id is None
    if funnel.team_id is None:
        return True
    if funnel.team_id in teams:
        return True
    grant = (
        db.query(models.FunnelPermission)
        .filter(
            models.FunnelPermission.team_id.in_(teams),
            models.FunnelPermission.funnel_id == funnel.id,
        )
        .first()
    )
    return grant is not None


def visible_funnel_ids(db: Session, user: models.User) -> Optional[set[int]]:
    """None = все воронки (админ). Иначе множество id."""
    if user.is_admin:
        return None
    from .stages import list_funnels

    return {f.id for f in list_funnels(db) if can_see_funnel(db, user, f)}


def list_visible_funnels(db: Session, user: models.User) -> list[models.Funnel]:
    from .stages import list_funnels

    funnels = list_funnels(db)
    if user.is_admin:
        return funnels
    return [f for f in funnels if can_see_funnel(db, user, f)]


def can_see_client(db: Session, user: models.User, client: models.Client) -> bool:
    if user.is_admin:
        return True
    teams = user_team_ids(user)
    if not teams:
        return True
    if client.owner_team_id and client.owner_team_id in teams:
        return True

    funnel_ids = visible_funnel_ids(db, user)
    if funnel_ids is not None and not funnel_ids:
        return False

    q = (
        db.query(models.Task.id)
        .join(models.Stage, models.Task.stage_id == models.Stage.id)
        .filter(models.Task.client_id == client.id)
    )
    if funnel_ids is not None:
        q = q.filter(models.Stage.funnel_id.in_(funnel_ids))
    if q.first():
        return True
    # клиент без задач и не своей команды — скрыт
    return False


def filter_visible_clients(
    db: Session, user: models.User, clients: list[models.Client]
) -> list[models.Client]:
    if user.is_admin or not user_team_ids(user):
        return clients
    return [c for c in clients if can_see_client(db, user, c)]
