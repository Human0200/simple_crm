import re
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from . import models

DEFAULT_STAGES = [
    {
        "key": "backlog",
        "name": "К выполнению",
        "position": 0,
        "assignee_can_set": True,
        "requires_result": False,
        "is_final": False,
    },
    {
        "key": "in_progress",
        "name": "В работе",
        "position": 1,
        "assignee_can_set": True,
        "requires_result": False,
        "is_final": False,
    },
    {
        "key": "review",
        "name": "На проверке",
        "position": 2,
        "assignee_can_set": True,
        "requires_result": True,
        "is_final": False,
    },
    {
        "key": "done",
        "name": "Готово",
        "position": 3,
        "assignee_can_set": False,
        "requires_result": True,
        "is_final": True,
    },
]


def slugify(name: str) -> str:
    raw = name.strip().lower()
    raw = re.sub(r"[^\w\s-]", "", raw, flags=re.UNICODE)
    raw = re.sub(r"[\s_-]+", "_", raw).strip("_")
    return raw or "stage"


def ensure_default_funnel(db: Session) -> models.Funnel:
    funnel = (
        db.query(models.Funnel)
        .filter(models.Funnel.is_default.is_(True))
        .order_by(models.Funnel.id)
        .first()
    )
    if funnel is None:
        funnel = db.query(models.Funnel).order_by(models.Funnel.id).first()
    if funnel is None:
        funnel = models.Funnel(name="Основная", position=0, is_default=True)
        db.add(funnel)
        db.flush()
    elif not funnel.is_default:
        funnel.is_default = True
    return funnel


def seed_stages_for_funnel(db: Session, funnel: models.Funnel) -> list[models.Stage]:
    existing = (
        db.query(models.Stage)
        .filter(models.Stage.funnel_id == funnel.id)
        .order_by(models.Stage.position)
        .all()
    )
    if existing:
        return existing
    stages = []
    for item in DEFAULT_STAGES:
        key = unique_key(db, item["key"], funnel_id=funnel.id)
        stage = models.Stage(
            funnel_id=funnel.id,
            key=key,
            name=item["name"],
            position=item["position"],
            assignee_can_set=item["assignee_can_set"],
            requires_result=item["requires_result"],
            is_final=item["is_final"],
        )
        db.add(stage)
        stages.append(stage)
    db.flush()
    return stages


def ensure_default_stages(db: Session) -> list[models.Stage]:
    """Миграция/старт: есть дефолтная воронка и стадии."""
    funnel = ensure_default_funnel(db)

    # старые стадии без funnel_id → в дефолтную
    orphans = (
        db.query(models.Stage)
        .filter(models.Stage.funnel_id.is_(None))
        .order_by(models.Stage.position, models.Stage.id)
        .all()
    )
    for s in orphans:
        s.funnel_id = funnel.id
    if orphans:
        db.flush()

    stages = seed_stages_for_funnel(db, funnel)
    db.commit()
    return (
        db.query(models.Stage)
        .filter(models.Stage.funnel_id == funnel.id)
        .order_by(models.Stage.position, models.Stage.id)
        .all()
        or stages
    )


def list_funnels(db: Session) -> list[models.Funnel]:
    ensure_default_stages(db)
    return (
        db.query(models.Funnel)
        .options(joinedload(models.Funnel.team), joinedload(models.Funnel.stages))
        .order_by(models.Funnel.position, models.Funnel.id)
        .all()
    )


def get_funnel(db: Session, funnel_id: int) -> Optional[models.Funnel]:
    return (
        db.query(models.Funnel)
        .options(joinedload(models.Funnel.team), joinedload(models.Funnel.stages))
        .filter(models.Funnel.id == funnel_id)
        .first()
    )


def list_stages(
    db: Session, funnel_id: Optional[int] = None
) -> list[models.Stage]:
    ensure_default_stages(db)
    q = db.query(models.Stage)
    if funnel_id is not None:
        q = q.filter(models.Stage.funnel_id == funnel_id)
    return q.order_by(models.Stage.position, models.Stage.id).all()


def get_stage(db: Session, stage_id: int) -> Optional[models.Stage]:
    return db.query(models.Stage).filter(models.Stage.id == stage_id).first()


def get_stage_by_key(
    db: Session, key: str, funnel_id: Optional[int] = None
) -> Optional[models.Stage]:
    q = db.query(models.Stage).filter(models.Stage.key == key)
    if funnel_id is not None:
        q = q.filter(models.Stage.funnel_id == funnel_id)
    return q.first()


def default_stage(
    db: Session, funnel_id: Optional[int] = None
) -> models.Stage:
    if funnel_id is None:
        funnel = ensure_default_funnel(db)
        funnel_id = funnel.id
    stages = list_stages(db, funnel_id=funnel_id)
    for s in stages:
        if not s.is_final:
            return s
    return stages[0]


def unique_key(
    db: Session,
    base: str,
    exclude_id: Optional[int] = None,
    funnel_id: Optional[int] = None,
) -> str:
    key = slugify(base)[:40]
    candidate = key
    i = 2
    while True:
        q = db.query(models.Stage).filter(models.Stage.key == candidate)
        if funnel_id is not None:
            q = q.filter(models.Stage.funnel_id == funnel_id)
        if exclude_id is not None:
            q = q.filter(models.Stage.id != exclude_id)
        if not q.first():
            return candidate
        candidate = f"{key}_{i}"
        i += 1


def preferred_funnel_for_user(
    db: Session, user: models.User
) -> models.Funnel:
    from .permissions import list_visible_funnels

    funnels = list_visible_funnels(db, user)
    if not funnels:
        # fallback: хотя бы дефолтная (админ/миграция)
        funnels = list_funnels(db)
    user_team_ids = {t.id for t in (user.teams or [])}
    for f in funnels:
        if f.team_id and f.team_id in user_team_ids:
            return f
    for f in funnels:
        if f.is_default:
            return f
    return funnels[0]
