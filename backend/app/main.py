import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import admin, auth, tasks, users, email_status, clients, stages, external, funnels
from .seed import seed
from . import ws
from .automation import automation_loop

seed()

STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parent.parent / "static"))
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "avatars").mkdir(parents=True, exist_ok=True)

_stop_event: asyncio.Event | None = None
_scheduler_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _stop_event, _scheduler_task
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(automation_loop(_stop_event))
    yield
    _stop_event.set()
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Simple CRM", lifespan=lifespan)

cors_origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:8080,http://localhost",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(clients.router)
app.include_router(stages.router)
app.include_router(funnels.router)
app.include_router(admin.router)
app.include_router(external.router)
app.include_router(email_status.router)
app.include_router(ws.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
