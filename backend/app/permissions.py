from sqlalchemy.orm import Session

from . import models


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
