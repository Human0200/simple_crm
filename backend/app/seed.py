"""Создаёт 5 рабочих аккаунтов при первом запуске (если пользователей ещё нет)."""

from .database import SessionLocal, engine, Base
from . import models
from .auth import hash_password

DEFAULT_ACCOUNTS = [
    ("user1", "Пользователь 1", "password1"),
    ("user2", "Пользователь 2", "password2"),
    ("user3", "Пользователь 3", "password3"),
    ("user4", "Пользователь 4", "password4"),
    ("user5", "Пользователь 5", "password5"),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.User).count() > 0:
            return
        for username, full_name, password in DEFAULT_ACCOUNTS:
            db.add(
                models.User(
                    username=username,
                    full_name=full_name,
                    password_hash=hash_password(password),
                    is_admin=(username == "user1"),
                )
            )
        db.commit()
        print("Созданы 5 рабочих аккаунтов (user1..user5 / password1..password5)")
        print("user1 назначен администратором")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
