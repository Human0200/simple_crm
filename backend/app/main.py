from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import admin, auth, tasks, users
from .seed import seed
from . import ws

seed()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Simple CRM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(ws.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
