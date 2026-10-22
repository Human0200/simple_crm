from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_admin, hash_password
from ..database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _team_query(db: Session):
    return db.query(models.Team).options(joinedload(models.Team.members))


@router.get("/users", response_model=list[schemas.UserOut])
def list_all_users(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return db.query(models.User).options(joinedload(models.User.teams)).order_by(models.User.full_name).all()


@router.post("/users", response_model=schemas.UserOut)
def create_user(
    payload: schemas.AdminUserCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    username = payload.username.strip()
    full_name = payload.full_name.strip()
    if not username or not full_name or not payload.password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Заполните логин, имя и пароль")
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Такой логин уже занят")

    user = models.User(
        username=username,
        full_name=full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/role", response_model=schemas.UserOut)
def update_user_role(
    user_id: int,
    payload: schemas.AdminUserRoleUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя удалить свой собственный аккаунт")

    has_tasks = db.query(models.Task).filter(models.Task.creator_id == user_id).first()
    if has_tasks:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Нельзя удалить: пользователь является постановщиком задач",
        )
    has_comments = db.query(models.Comment).filter(models.Comment.author_id == user_id).first()
    if has_comments:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Нельзя удалить: у пользователя есть комментарии в задачах",
        )

    user.teams = []
    user.assigned_tasks = []
    user.observed_tasks = []
    db.commit()
    db.delete(user)
    db.commit()


@router.get("/teams", response_model=list[schemas.TeamWithMembersOut])
def list_teams(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return _team_query(db).order_by(models.Team.name).all()


@router.post("/teams", response_model=schemas.TeamWithMembersOut)
def create_team(
    payload: schemas.TeamCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название команды обязательно")
    if db.query(models.Team).filter(models.Team.name == name).first():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Команда с таким названием уже есть")

    team = models.Team(name=name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Команда не найдена")
    db.delete(team)
    db.commit()


def _get_team(team_id: int, db: Session) -> models.Team:
    team = _team_query(db).filter(models.Team.id == team_id).first()
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Команда не найдена")
    return team


@router.post("/teams/{team_id}/members", response_model=schemas.TeamWithMembersOut)
def add_team_member(
    team_id: int,
    payload: schemas.TeamMemberIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    team = _get_team(team_id, db)
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    if user not in team.members:
        team.members.append(user)
        db.commit()
    return _get_team(team_id, db)


@router.delete("/teams/{team_id}/members/{user_id}", response_model=schemas.TeamWithMembersOut)
def remove_team_member(
    team_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    team = _get_team(team_id, db)
    team.members = [u for u in team.members if u.id != user_id]
    db.commit()
    return _get_team(team_id, db)


@router.get("/permissions", response_model=list[schemas.PermissionOut])
def list_permissions(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return (
        db.query(models.TeamPermission)
        .options(
            joinedload(models.TeamPermission.from_team),
            joinedload(models.TeamPermission.to_team),
        )
        .all()
    )


@router.post("/permissions", response_model=schemas.PermissionOut)
def create_permission(
    payload: schemas.PermissionCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    existing = (
        db.query(models.TeamPermission)
        .filter(
            models.TeamPermission.from_team_id == payload.from_team_id,
            models.TeamPermission.to_team_id == payload.to_team_id,
        )
        .first()
    )
    if existing:
        return existing

    for team_id in (payload.from_team_id, payload.to_team_id):
        if not db.query(models.Team).filter(models.Team.id == team_id).first():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Команда не найдена")

    permission = models.TeamPermission(
        from_team_id=payload.from_team_id, to_team_id=payload.to_team_id
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


@router.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    permission = (
        db.query(models.TeamPermission)
        .filter(models.TeamPermission.id == permission_id)
        .first()
    )
    if permission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Право не найдено")
    db.delete(permission)
    db.commit()
