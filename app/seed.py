import json

from sqlalchemy import select

from .database import BASE_DIR, SessionLocal
from .models import Message, Topic


def seed():
    with SessionLocal() as db:
        if db.scalar(select(Topic.id).limit(1)) is not None:
            print("В базе уже есть темы. Заполнение пропущено.")
            return

        path = BASE_DIR / "data" / "seed.json"
        topics = json.loads(path.read_text(encoding="utf-8"))
        message_count = 0

        for item in topics:
            topic = Topic(
                title=item["title"],
                author=item["author"],
                status=item["status"],
            )
            db.add(topic)
            db.flush()

            for message in item["messages"]:
                db.add(Message(
                    topic_id=topic.id,
                    author=message["author"],
                    text=message["text"],
                ))
                message_count += 1

        db.commit()

    print(f"Добавлено тем: {len(topics)}, сообщений: {message_count}.")


if __name__ == "__main__":
    seed()
