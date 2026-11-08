from typing import Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import models
from .auth import SECRET_KEY, ALGORITHM
from .database import SessionLocal

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: Dict[int, List[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        conns = self.active.get(user_id)
        if conns and ws in conns:
            conns.remove(ws)
            if not conns:
                self.active.pop(user_id, None)

    async def send_to_user(self, user_id: int, message: dict):
        for ws in list(self.active.get(user_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def notify_task_event(
        self, db: Session, task: models.Task, event: str, actor_id: Optional[int] = None
    ):
        recipient_ids: Set[int] = {task.creator_id}
        recipient_ids |= {u.id for u in task.assignees}
        recipient_ids |= {u.id for u in task.observers}

        admin_ids = {
            u.id for u in db.query(models.User).filter(models.User.is_admin.is_(True)).all()
        }
        recipient_ids |= admin_ids

        # Инициатору не шлём событие (и звук/бейдж у него не дергаются)
        if actor_id is not None:
            recipient_ids.discard(int(actor_id))

        message = {"type": event, "task_id": task.id, "actor_id": actor_id}
        for uid in recipient_ids:
            await self.send_to_user(uid, message)


manager = ConnectionManager()


def _get_user_from_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
    except JWTError:
        return None
    return db.query(models.User).filter(models.User.id == int(user_id)).first()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    db = SessionLocal()
    try:
        user = _get_user_from_token(token, db)
        if user is None:
            await websocket.close(code=4401)
            return

        await manager.connect(user.id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(user.id, websocket)
    finally:
        db.close()
