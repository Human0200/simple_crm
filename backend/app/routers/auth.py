from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import create_access_token, verify_password, get_current_user
from ..database import get_db
from ..permissions import capabilities_for_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(db: Session, user: models.User) -> schemas.UserOut:
    data = schemas.UserOut.model_validate(user)
    data.capabilities = schemas.UserCapabilities(**capabilities_for_user(db, user))
    return data


@router.post("/login", response_model=schemas.Token)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(access_token=token, user=_user_out(db, user))


@router.get("/me", response_model=schemas.UserOut)
def me(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _user_out(db, current_user)
