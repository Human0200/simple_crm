from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, get_current_admin
from ..database import get_db
from ..permissions import can_see_funnel, list_visible_funnels
from ..stages import (
    list_funnels,
    get_funnel,
    ensure_default_stages,
    seed_stages_for_funnel,
    preferred_funnel_for_user,
)

router = APIRouter(prefix="/api/funnels", tags=["funnels"])


def _funnel_out(funnel: models.Funnel) -> schemas.FunnelOut:
    stages = sorted(funnel.stages or [], key=lambda s: (s.position, s.id))
    return schemas.FunnelOut(
        id=funnel.id,
        name=funnel.name,
        position=funnel.position,
        is_default=bool(funnel.is_default),
        team_id=funnel.team_id,
        team=schemas.TeamOut.model_validate(funnel.team) if funnel.team else None,
        stages=[schemas.StageOut.model_validate(s) for s in stages],
    )


@router.get("", response_model=list[schemas.FunnelOut])
def get_funnels(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return [_funnel_out(f) for f in list_visible_funnels(db, current_user)]


@router.get("/preferred", response_model=schemas.FunnelOut)
def get_preferred_funnel(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _funnel_out(preferred_funnel_for_user(db, current_user))


@router.get("/{funnel_id}", response_model=schemas.FunnelOut)
def get_funnel_detail(
    funnel_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    funnel = get_funnel(db, funnel_id)
    if funnel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Воронка не найдена")
    if not can_see_funnel(db, current_user, funnel):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к воронке")
    return _funnel_out(funnel)


@router.post("", response_model=schemas.FunnelOut)
def create_funnel(
    payload: schemas.FunnelCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    ensure_default_stages(db)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название воронки обязательно")
    if payload.team_id is not None:
        team = db.query(models.Team).filter(models.Team.id == payload.team_id).first()
        if team is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Команда не найдена")

    max_pos = db.query(models.Funnel).count()
    funnel = models.Funnel(
        name=name,
        position=max_pos,
        team_id=payload.team_id,
        is_default=False,
    )
    db.add(funnel)
    db.flush()

    if payload.is_default:
        db.query(models.Funnel).update({models.Funnel.is_default: False})
        funnel.is_default = True

    if payload.with_default_stages:
        seed_stages_for_funnel(db, funnel)

    db.commit()
    return _funnel_out(get_funnel(db, funnel.id))


@router.post("/reorder", response_model=list[schemas.FunnelOut])
def reorder_funnels(
    payload: schemas.FunnelReorderIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    funnels = {f.id: f for f in list_funnels(db)}
    for idx, fid in enumerate(payload.funnel_ids):
        if fid in funnels:
            funnels[fid].position = idx
    db.commit()
    return [_funnel_out(f) for f in list_funnels(db)]


@router.put("/{funnel_id}", response_model=schemas.FunnelOut)
def update_funnel(
    funnel_id: int,
    payload: schemas.FunnelUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    funnel = get_funnel(db, funnel_id)
    if funnel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Воронка не найдена")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название воронки обязательно")
        funnel.name = name

    if "team_id" in payload.model_fields_set:
        if payload.team_id is not None:
            team = db.query(models.Team).filter(models.Team.id == payload.team_id).first()
            if team is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Команда не найдена")
        funnel.team_id = payload.team_id

    if payload.position is not None:
        funnel.position = payload.position

    if payload.is_default:
        db.query(models.Funnel).update({models.Funnel.is_default: False})
        funnel.is_default = True

    db.commit()
    return _funnel_out(get_funnel(db, funnel_id))


@router.delete("/{funnel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_funnel(
    funnel_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    funnel = get_funnel(db, funnel_id)
    if funnel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Воронка не найдена")
    total = db.query(models.Funnel).count()
    if total <= 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Нельзя удалить последнюю воронку")

    stage_ids = [s.id for s in funnel.stages]
    if stage_ids:
        tasks_count = (
            db.query(models.Task).filter(models.Task.stage_id.in_(stage_ids)).count()
        )
        if tasks_count:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"В воронке есть задачи ({tasks_count}). Перенесите их перед удалением.",
            )

    was_default = funnel.is_default
    db.delete(funnel)
    db.flush()
    if was_default:
        other = db.query(models.Funnel).order_by(models.Funnel.id).first()
        if other:
            other.is_default = True
    db.commit()
