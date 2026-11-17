import argparse
import json

from sqlalchemy import select

from .database import BASE_DIR, SessionLocal
from .models import Message, Topic, User


def add_demo_records(db, owner_id: int) -> tuple[int, int]:
    path = BASE_DIR / "data" / "seed.json"
    topics = json.loads(path.read_text(encoding="utf-8"))
    message_count = 0

    for item in topics:
        topic = Topic(
            title=item["title"],
            author=item["author"],
            status=item["status"],
            owner_id=owner_id,
        )
        db.add(topic)
        db.flush()

        for message in item["messages"]:
            db.add(Message(
                topic_id=topic.id,
                author=message["author"],
                text=message["text"],
                owner_id=owner_id,
            ))
            message_count += 1

    return len(topics), message_count


def seed(username: str):
    with SessionLocal() as db:
        if db.scalar(select(Topic.id).limit(1)) is not None:
            print("В базе уже есть темы. Заполнение пропущено.")
            return

        owner = db.scalar(select(User).where(User.username == username))
        if owner is None:
            raise SystemExit("Пользователь не найден. Сначала зарегистрируйте его через POST /auth/register.")

        topic_count, message_count = add_demo_records(db, owner.id)
        db.commit()

    print(f"Добавлено тем: {topic_count}, сообщений: {message_count}. Владелец: {username}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Заполнить пустой форум примерами")
    parser.add_argument("username", help="Логин зарегистрированного владельца записей")
    seed(parser.parse_args().username)
