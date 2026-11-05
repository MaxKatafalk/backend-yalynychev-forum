from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Message, Topic
from .schemas import MessageCreate, TopicCreate, TopicListQuery, TopicPatch


class TopicStore:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: TopicCreate) -> Topic:
        topic = Topic(**data.model_dump())
        self.db.add(topic)
        self.db.commit()
        self.db.refresh(topic)
        return topic

    def get(self, topic_id: int) -> Topic | None:
        return self.db.get(Topic, topic_id)

    def list(self, query: TopicListQuery) -> list[Topic]:
        statement = select(Topic)
        if query.author is not None:
            statement = statement.where(Topic.author == query.author)
        if query.status is not None:
            statement = statement.where(Topic.status == query.status)
        if query.q is not None:
            statement = statement.where(func.casefold(Topic.title).contains(query.q.casefold(), autoescape=True))
        statement = statement.order_by(Topic.id).offset(query.offset).limit(query.limit)
        return self.db.scalars(statement).all()

    def stats(self):
        message_count = func.count(Message.id)
        statement = (
            select(Topic.id.label("topic_id"), Topic.title, message_count.label("message_count"))
            .outerjoin(Message, Message.topic_id == Topic.id)
            .group_by(Topic.id, Topic.title)
            .order_by(message_count.desc(), Topic.id)
        )
        return self.db.execute(statement).mappings().all()

    def update(self, topic_id: int, data: TopicPatch) -> Topic | None:
        topic = self.get(topic_id)
        if topic is None:
            return None
        if data.title is not None:
            topic.title = data.title
        if data.author is not None:
            topic.author = data.author
        if data.status is not None:
            topic.status = data.status
        self.db.commit()
        self.db.refresh(topic)
        return topic

    def delete(self, topic_id: int) -> bool:
        topic = self.get(topic_id)
        if topic is None:
            return False
        self.db.delete(topic)
        self.db.commit()
        return True


class MessageStore:
    def __init__(self, db: Session):
        self.db = db

    def create(self, topic_id: int, data: MessageCreate) -> Message:
        message = Message(topic_id=topic_id, **data.model_dump())
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list(self, topic_id: int) -> list[Message]:
        statement = select(Message).where(Message.topic_id == topic_id).order_by(Message.id)
        return self.db.scalars(statement).all()
