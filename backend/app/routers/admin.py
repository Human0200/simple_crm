import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_admin, hash_password, generate_api_token, hash_api_token
from ..database import get_db
from .. import email_service
from ..automation import load_rules, rule_to_dict
from ..permissions import ensure_role_permissions

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _team_query(db: Session):
    return db.query(models.Team).options(joinedload(models.Team.members))


def _rule_out(rule: models.AutomationRule) -> schemas.AutomationRuleOut:
    return schemas.AutomationRuleOut.model_validate(rule_to_dict(rule))


def _email_out(settings: models.EmailSettings) -> schemas.EmailSettingsOut:
    return schemas.EmailSettingsOut(
        smtp_host=settings.smtp_host or "",
        smtp_port=settings.smtp_port or 587,
        smtp_user=settings.smtp_user or "",
        from_email=settings.from_email or "",
        from_name=settings.from_name or "Simple CRM",
        use_tls=bool(settings.use_tls),
        use_ssl=bool(settings.use_ssl),
        imap_host=getattr(settings, "imap_host", "") or "",
        imap_port=getattr(settings, "imap_port", None) or 993,
        imap_user=getattr(settings, "imap_user", "") or "",
        imap_use_ssl=bool(getattr(settings, "imap_use_ssl", True)),
        imap_folder=getattr(settings, "imap_folder", None) or "INBOX",
        configured=email_service.is_configured(settings),
        imap_configured=email_service.is_imap_configured(settings),
        has_password=bool(settings.smtp_password),
        has_imap_password=bool(getattr(settings, "imap_password", "")),
    )


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
        email=(payload.email or "").strip(),
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


@router.get("/funnel-permissions", response_model=list[schemas.FunnelPermissionOut])
def list_funnel_permissions(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    rows = (
        db.query(models.FunnelPermission)
        .options(
            joinedload(models.FunnelPermission.team),
            joinedload(models.FunnelPermission.funnel),
        )
        .order_by(models.FunnelPermission.id)
        .all()
    )
    return [
        schemas.FunnelPermissionOut(
            id=r.id,
            team_id=r.team_id,
            funnel_id=r.funnel_id,
            team=schemas.TeamOut.model_validate(r.team),
            funnel=schemas.FunnelBriefOut.model_validate(r.funnel),
        )
        for r in rows
    ]


@router.post("/funnel-permissions", response_model=schemas.FunnelPermissionOut)
def create_funnel_permission(
    payload: schemas.FunnelPermissionCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    team = db.query(models.Team).filter(models.Team.id == payload.team_id).first()
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Команда не найдена")
    funnel = db.query(models.Funnel).filter(models.Funnel.id == payload.funnel_id).first()
    if funnel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Воронка не найдена")
    existing = (
        db.query(models.FunnelPermission)
        .filter(
            models.FunnelPermission.team_id == payload.team_id,
            models.FunnelPermission.funnel_id == payload.funnel_id,
        )
        .first()
    )
    if existing is None:
        existing = models.FunnelPermission(
            team_id=payload.team_id, funnel_id=payload.funnel_id
        )
        db.add(existing)
        db.commit()
    row = (
        db.query(models.FunnelPermission)
        .options(
            joinedload(models.FunnelPermission.team),
            joinedload(models.FunnelPermission.funnel),
        )
        .filter(
            models.FunnelPermission.team_id == payload.team_id,
            models.FunnelPermission.funnel_id == payload.funnel_id,
        )
        .one()
    )
    return schemas.FunnelPermissionOut(
        id=row.id,
        team_id=row.team_id,
        funnel_id=row.funnel_id,
        team=schemas.TeamOut.model_validate(row.team),
        funnel=schemas.FunnelBriefOut.model_validate(row.funnel),
    )


@router.delete(
    "/funnel-permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_funnel_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    row = (
        db.query(models.FunnelPermission)
        .filter(models.FunnelPermission.id == permission_id)
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Право не найдено")
    db.delete(row)
    db.commit()


@router.get("/role-permissions", response_model=list[schemas.RolePermissionOut])
def list_role_permissions(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return [
        schemas.RolePermissionOut.model_validate(r)
        for r in ensure_role_permissions(db)
    ]


@router.put("/role-permissions/{role}", response_model=schemas.RolePermissionOut)
def update_role_permission(
    role: models.UserRole,
    payload: schemas.RolePermissionUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    ensure_role_permissions(db)
    row = (
        db.query(models.RolePermission)
        .filter(models.RolePermission.role == role)
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Роль не найдена")
    row.can_create = payload.can_create
    row.can_edit = payload.can_edit
    row.can_delete = payload.can_delete
    row.can_edit_any = payload.can_edit_any
    row.can_delete_any = payload.can_delete_any
    db.commit()
    db.refresh(row)
    return schemas.RolePermissionOut.model_validate(row)


# --- Email integration ---


@router.get("/email", response_model=schemas.EmailSettingsOut)
def get_email_settings(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return _email_out(email_service.get_or_create_settings(db))


@router.put("/email", response_model=schemas.EmailSettingsOut)
def update_email_settings(
    payload: schemas.EmailSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    settings = email_service.get_or_create_settings(db)
    settings.smtp_host = payload.smtp_host.strip()
    settings.smtp_port = payload.smtp_port
    settings.smtp_user = payload.smtp_user.strip()
    if payload.smtp_password is not None and payload.smtp_password != "":
        settings.smtp_password = payload.smtp_password
    settings.from_email = payload.from_email.strip()
    settings.from_name = payload.from_name.strip() or "Simple CRM"
    settings.use_tls = payload.use_tls
    settings.use_ssl = payload.use_ssl
    settings.imap_host = (payload.imap_host or "").strip()
    settings.imap_port = payload.imap_port or 993
    settings.imap_user = (payload.imap_user or "").strip()
    if payload.imap_password is not None and payload.imap_password != "":
        settings.imap_password = payload.imap_password
    settings.imap_use_ssl = payload.imap_use_ssl
    settings.imap_folder = (payload.imap_folder or "INBOX").strip() or "INBOX"
    db.commit()
    db.refresh(settings)
    return _email_out(settings)


@router.post("/email/test")
def test_email(
    payload: schemas.EmailTestIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    settings = email_service.get_or_create_settings(db)
    if not email_service.is_configured(settings):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Сначала сохраните настройки SMTP")
    try:
        email_service.send_email(
            settings,
            to_emails=[payload.to_email.strip()],
            subject="Simple CRM — тестовое письмо",
            body="Почтовая интеграция настроена корректно.",
        )
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Не удалось отправить тестовое письмо: {e}",
        ) from e
    return {"ok": True}


# --- Automation ---


@router.get("/automation", response_model=list[schemas.AutomationRuleOut])
def list_automation_rules(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return [_rule_out(r) for r in load_rules(db)]


def _validate_rule_payload(payload: schemas.AutomationRuleIn, db: Session):
    if not payload.name.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название правила обязательно")
    creator = db.query(models.User).filter(models.User.id == payload.creator_id).first()
    if creator is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Постановщик не найден")

    if payload.action_type == models.AutomationAction.CREATE_TASK:
        if not (payload.title_template or "").strip():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Шаблон названия задачи обязателен"
            )
    elif payload.action_type == models.AutomationAction.SEND_EMAIL:
        if not (payload.email_to_template or "").strip():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Укажите получателя письма (email или {client_email})",
            )
        if not (payload.title_template or "").strip():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Укажите тему письма"
            )
    elif payload.action_type == models.AutomationAction.MOVE_TASKS:
        if payload.move_from_stage_id is None or payload.target_stage_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Укажите стадии «откуда» и «куда» для перемещения",
            )
        if payload.move_from_stage_id == payload.target_stage_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Стадии «откуда» и «куда» должны различаться",
            )
        for sid, label in (
            (payload.move_from_stage_id, "исходная стадия"),
            (payload.target_stage_id, "целевая стадия"),
        ):
            st = db.query(models.Stage).filter(models.Stage.id == sid).first()
            if st is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"Не найдена {label}"
                )
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестное действие")

    # legacy trigger больше не принимаем — это условие
    if payload.trigger_type == models.AutomationTrigger.CLIENT_NO_STAGE_TASK:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "«Нет задачи на стадии» — это условие, выберите триггер и включите условие",
        )

    if payload.trigger_type == models.AutomationTrigger.SCHEDULE:
        if payload.schedule_interval is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Укажите интервал расписания")
        if payload.schedule_interval == models.ScheduleInterval.WEEKLY:
            if payload.schedule_weekday is None or not (0 <= payload.schedule_weekday <= 6):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Укажите день недели (0–6)")
    elif payload.trigger_type == models.AutomationTrigger.STATUS_CHANGE:
        if payload.watch_to_stage_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Укажите стадию, при переходе в которую выполнять действие",
            )
    elif payload.trigger_type == models.AutomationTrigger.CLIENT_INACTIVE:
        days = payload.inactivity_days
        if days is None or days < 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Укажите число дней без активности клиента (минимум 1)",
            )
    elif payload.trigger_type == models.AutomationTrigger.CLIENT_EMAIL:
        pass  # доп. полей не требуется; фильтры — через условия
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Неизвестный триггер")

    if payload.condition_no_stage_task:
        if payload.condition_stage_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Для условия «нет задачи на стадии» укажите стадию",
            )


def _apply_rule_fields(rule: models.AutomationRule, payload: schemas.AutomationRuleIn):
    rule.name = payload.name.strip()
    rule.enabled = payload.enabled
    rule.trigger_type = payload.trigger_type
    rule.action_type = payload.action_type
    rule.schedule_interval = payload.schedule_interval
    rule.schedule_time = payload.schedule_time or "09:00"
    rule.schedule_weekday = payload.schedule_weekday
    rule.watch_from_stage_id = payload.watch_from_stage_id
    rule.watch_to_stage_id = payload.watch_to_stage_id
    rule.inactivity_days = payload.inactivity_days
    rule.condition_no_stage_task = bool(payload.condition_no_stage_task)
    rule.condition_stage_id = (
        payload.condition_stage_id if payload.condition_no_stage_task else None
    )
    rule.condition_client_id = payload.condition_client_id
    rule.condition_no_tasks = bool(payload.condition_no_tasks)
    if payload.action_type == models.AutomationAction.MOVE_TASKS:
        rule.move_from_stage_id = payload.move_from_stage_id
        rule.target_stage_id = payload.target_stage_id
        rule.move_scope = payload.move_scope or models.MoveScope.CLIENT_STAGE
    elif payload.action_type == models.AutomationAction.CREATE_TASK:
        rule.move_from_stage_id = None
        rule.target_stage_id = payload.target_stage_id
        rule.move_scope = models.MoveScope.CLIENT_STAGE
    else:
        rule.move_from_stage_id = None
        rule.target_stage_id = None
        rule.move_scope = models.MoveScope.CLIENT_STAGE
    rule.email_to_template = (payload.email_to_template or "").strip()
    rule.title_template = (payload.title_template or "").strip()
    rule.description_template = payload.description_template or ""
    rule.creator_id = payload.creator_id
    rule.assignee_ids_json = json.dumps(payload.assignee_ids)
    rule.observer_ids_json = json.dumps(payload.observer_ids)
    rule.due_offset_days = payload.due_offset_days


@router.post("/automation", response_model=schemas.AutomationRuleOut)
def create_automation_rule(
    payload: schemas.AutomationRuleIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    _validate_rule_payload(payload, db)
    rule = models.AutomationRule(
        name=payload.name.strip(),
        title_template=(payload.title_template or "").strip(),
        creator_id=payload.creator_id,
        trigger_type=payload.trigger_type,
        action_type=payload.action_type,
    )
    _apply_rule_fields(rule, payload)
    db.add(rule)
    db.commit()
    rules = load_rules(db)
    created = next(r for r in rules if r.id == rule.id)
    return _rule_out(created)


@router.put("/automation/{rule_id}", response_model=schemas.AutomationRuleOut)
def update_automation_rule(
    rule_id: int,
    payload: schemas.AutomationRuleIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    rule = db.query(models.AutomationRule).filter(models.AutomationRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Правило не найдено")
    _validate_rule_payload(payload, db)
    _apply_rule_fields(rule, payload)
    db.commit()
    rules = load_rules(db)
    updated = next(r for r in rules if r.id == rule_id)
    return _rule_out(updated)


@router.delete("/automation/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    rule = db.query(models.AutomationRule).filter(models.AutomationRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Правило не найдено")
    db.delete(rule)
    db.commit()


# --- API tokens ---


def _token_query(db: Session):
    return db.query(models.ApiToken).options(
        joinedload(models.ApiToken.created_by),
        joinedload(models.ApiToken.actor_user),
    )


@router.get("/api-tokens", response_model=list[schemas.ApiTokenOut])
def list_api_tokens(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    tokens = _token_query(db).order_by(models.ApiToken.id.desc()).all()
    return [schemas.ApiTokenOut.model_validate(t) for t in tokens]


@router.post("/api-tokens", response_model=schemas.ApiTokenCreatedOut)
def create_api_token(
    payload: schemas.ApiTokenCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Укажите название токена")

    actor_id = payload.actor_user_id or admin.id
    actor = db.query(models.User).filter(models.User.id == actor_id).first()
    if actor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь-актор не найден")

    raw = generate_api_token()
    token = models.ApiToken(
        name=name,
        token_prefix=raw[:12],
        token_hash=hash_api_token(raw),
        created_by_id=admin.id,
        actor_user_id=actor.id,
        enabled=True,
    )
    db.add(token)
    db.commit()
    saved = _token_query(db).filter(models.ApiToken.id == token.id).one()
    data = schemas.ApiTokenOut.model_validate(saved).model_dump()
    return schemas.ApiTokenCreatedOut(**data, token=raw)


@router.post("/api-tokens/{token_id}/revoke", response_model=schemas.ApiTokenOut)
def revoke_api_token(
    token_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    token = _token_query(db).filter(models.ApiToken.id == token_id).first()
    if token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Токен не найден")
    token.enabled = False
    token.revoked_at = datetime.utcnow()
    db.commit()
    return schemas.ApiTokenOut.model_validate(
        _token_query(db).filter(models.ApiToken.id == token_id).one()
    )


@router.delete("/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_token(
    token_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    token = db.query(models.ApiToken).filter(models.ApiToken.id == token_id).first()
    if token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Токен не найден")
    db.delete(token)
    db.commit()
