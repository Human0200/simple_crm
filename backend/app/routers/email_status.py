from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from .. import models, schemas, email_service

router = APIRouter(prefix="/api/email", tags=["email"])


@router.get("/status")
def email_status(
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    settings = email_service.get_settings(db)
    return {"configured": bool(settings and email_service.is_configured(settings))}


@router.get("/templates", response_model=list[schemas.MessageTemplateOut])
def list_message_templates(
    db: Session = Depends(get_db),
    _user: models.User = Depends(get_current_user),
):
    """Список шаблонов писем для формы отправки (доступен всем авторизованным)."""
    return (
        db.query(models.MessageTemplate)
        .order_by(models.MessageTemplate.name, models.MessageTemplate.id)
        .all()
    )
