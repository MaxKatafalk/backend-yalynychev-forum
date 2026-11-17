from os import getenv

from argon2 import PasswordHasher
from pydantic import ValidationError
from sqlalchemy import text

from .database import SessionLocal
from .models import User
from .schemas import UserRegister
from .storage import UserStore


def create_admin():
    try:
        data = UserRegister(
            username=getenv("ADMIN_USERNAME", ""),
            password=getenv("ADMIN_PASSWORD", ""),
        )
    except ValidationError:
        raise SystemExit("Задайте ADMIN_USERNAME и ADMIN_PASSWORD по правилам регистрации.") from None

    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        existing = UserStore(db).get_by_username(data.username)
        if existing is not None:
            if existing.role == "admin":
                print("Администратор с таким логином уже есть.")
                return
            raise SystemExit("Логин занят обычным пользователем. Выберите другой ADMIN_USERNAME.")

        password_hash = PasswordHasher().hash(data.password.get_secret_value())
        db.add(User(username=data.username, password_hash=password_hash, role="admin"))
        db.commit()
    print(f"Создан администратор {data.username}.")


if __name__ == "__main__":
    create_admin()
