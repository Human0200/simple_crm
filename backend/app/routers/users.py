import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..permissions import assignable_users, observable_users

router = APIRouter(prefix="/api/users", tags=["users"])

STATIC_ROOT = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parent.parent.parent / "static"))
AVATAR_DIR = STATIC_ROOT / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_AVATAR_BYTES = 3 * 1024 * 1024


@router.get("", response_model=list[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.User)
        .options(joinedload(models.User.teams))
        .order_by(models.User.full_name)
        .all()
    )


@router.get("/assignable", response_model=list[schemas.UserOut])
def list_assignable_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    users = assignable_users(db, current_user)
    return sorted(users, key=lambda u: u.full_name)


@router.get("/observable", response_model=list[schemas.UserOut])
def list_observable_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    users = observable_users(db, current_user)
    return sorted(users, key=lambda u: u.full_name)


@router.patch("/me", response_model=schemas.UserOut)
def update_profile(
    payload: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    full_name = payload.full_name.strip()
    if not full_name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Имя не может быть пустым")
    current_user.full_name = full_name
    current_user.bio = payload.bio.strip()
    current_user.email = (payload.email or "").strip()
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=schemas.UserOut)
def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Допустимые форматы: PNG, JPEG, WEBP",
        )
    contents = file.file.read(MAX_AVATAR_BYTES + 1)
    if len(contents) > MAX_AVATAR_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Файл слишком большой (макс. 3 МБ)")

    ext = ALLOWED_TYPES[file.content_type]
    filename = f"{current_user.id}-{uuid.uuid4().hex}{ext}"
    (AVATAR_DIR / filename).write_bytes(contents)

    current_user.avatar_url = f"/static/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    return current_user
