import json

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .database import BASE_DIR, SessionLocal
from .models import Message, Topic, User
from .storage import UserStore


DEMO_ACCOUNTS = {
    "demo_ivan": "123",
    "demo_anna": "456",
}


def get_demo_owner(db: Session, username: str, password: str) -> User:
    hasher = PasswordHasher()
    user = UserStore(db).get_by_username(username)
    if user is None:
        user = User(username=username, password_hash=hasher.hash(password), role="user")
        db.add(user)
        db.flush()
        return user

    if user.role == "user":
        try:
            if hasher.verify(user.password_hash, password):
                return user
        except (InvalidHashError, VerificationError):
            pass

    raise SystemExit(f"Логин {username} уже занят. Используйте отдельную тестовую базу.")


def seed():
    path = BASE_DIR / "data" / "seed.json"
    examples = json.loads(path.read_text(encoding="utf-8"))
    topic_count = 0
    message_count = 0

    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        owners = {}
        for username, password in DEMO_ACCOUNTS.items():
            owners[username] = get_demo_owner(db, username, password).id

        for item in examples:
            owner_id = owners[item["owner"]]
            topic = db.scalar(select(Topic).where(Topic.title == item["title"], Topic.owner_id == owner_id))
            if topic is None:
                topic = Topic(title=item["title"], author=item["author"], status=item["status"], owner_id=owner_id)
                db.add(topic)
                db.flush()
                topic_count += 1

            for item_message in item["messages"]:
                message_owner_id = owners[item_message["owner"]]
                existing = db.scalar(select(Message.id).where(
                    Message.topic_id == topic.id,
                    Message.owner_id == message_owner_id,
                    Message.text == item_message["text"],
                ))
                if existing is None:
                    db.add(Message(
                        topic_id=topic.id,
                        author=item_message["author"],
                        text=item_message["text"],
                        owner_id=message_owner_id,
                    ))
                    message_count += 1

        db.commit()

    print(f"Тестовые аккаунты: {', '.join(owners)}. Добавлено тем: {topic_count}, сообщений: {message_count}.")


if __name__ == "__main__":
    seed()
