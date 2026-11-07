from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, get_current_admin
from ..database import get_db
from ..permissions import can_see_funnel, visible_funnel_ids
from ..stages import (
    list_stages,
    unique_key,
    ensure_default_stages,
    ensure_default_funnel,
    get_funnel,
)

router = APIRouter(prefix="/api/stages", tags=["stages"])


@router.get("", response_model=list[schemas.StageOut])
def get_stages(
    funnel_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if funnel_id is not None:
        funnel = get_funnel(db, funnel_id)
        if funnel is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Воронка не найдена")
        if not can_see_funnel(db, current_user, funnel):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет доступа к воронке")
        return list_stages(db, funnel_id=funnel_id)

    stages = list_stages(db)
    allowed = visible_funnel_ids(db, current_user)
    if allowed is None:
        return stages
    return [s for s in stages if s.funnel_id in allowed]


@router.post("", response_model=schemas.StageOut)
def create_stage(
    payload: schemas.StageCreate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    ensure_default_stages(db)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название стадии обязательно")

    funnel_id = payload.funnel_id
    if funnel_id is None:
        funnel_id = ensure_default_funnel(db).id
    else:
        if get_funnel(db, funnel_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Воронка не найдена")

    max_pos = (
        db.query(models.Stage).filter(models.Stage.funnel_id == funnel_id).count()
    )
    stage = models.Stage(
        funnel_id=funnel_id,
        key=unique_key(db, name, funnel_id=funnel_id),
        name=name,
        position=max_pos,
        assignee_can_set=payload.assignee_can_set,
        requires_result=payload.requires_result,
        is_final=payload.is_final,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


@router.put("/{stage_id}", response_model=schemas.StageOut)
def update_stage(
    stage_id: int,
    payload: schemas.StageUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    stage = db.query(models.Stage).filter(models.Stage.id == stage_id).first()
    if stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Стадия не найдена")
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Название стадии обязательно")
        stage.name = name
    if payload.assignee_can_set is not None:
        stage.assignee_can_set = payload.assignee_can_set
    if payload.requires_result is not None:
        stage.requires_result = payload.requires_result
    if payload.is_final is not None:
        stage.is_final = payload.is_final
    if payload.position is not None:
        stage.position = payload.position
    db.commit()
    db.refresh(stage)
    return stage


@router.post("/reorder", response_model=list[schemas.StageOut])
def reorder_stages(
    payload: schemas.StageReorderIn,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    q = db.query(models.Stage)
    if payload.funnel_id is not None:
        q = q.filter(models.Stage.funnel_id == payload.funnel_id)
    stages = {s.id: s for s in q.all()}
    for idx, sid in enumerate(payload.stage_ids):
        if sid in stages:
            stages[sid].position = idx
    db.commit()
    return list_stages(db, funnel_id=payload.funnel_id)


@router.delete("/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage(
    stage_id: int,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    stage = db.query(models.Stage).filter(models.Stage.id == stage_id).first()
    if stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Стадия не найдена")
    funnel_id = stage.funnel_id
    total = (
        db.query(models.Stage).filter(models.Stage.funnel_id == funnel_id).count()
        if funnel_id
        else db.query(models.Stage).count()
    )
    if total <= 1:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Нельзя удалить последнюю стадию воронки"
        )
    tasks_count = db.query(models.Task).filter(models.Task.stage_id == stage_id).count()
    if tasks_count:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"На стадии есть задачи ({tasks_count}). Перенесите их перед удалением.",
        )
    db.delete(stage)
    db.commit()
