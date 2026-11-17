from argon2 import PasswordHasher
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Message, Topic, User
from .schemas import MessageCreate, TopicCreate, TopicListQuery, TopicPatch, UserRegister


class TopicStore:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: TopicCreate, owner_id: int) -> Topic:
        topic = Topic(owner_id=owner_id, **data.model_dump())
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

    def update(self, topic: Topic, data: TopicPatch) -> Topic:
        if data.title is not None:
            topic.title = data.title
        if data.author is not None:
            topic.author = data.author
        if data.status is not None:
            topic.status = data.status
        self.db.commit()
        self.db.refresh(topic)
        return topic

    def delete(self, topic: Topic) -> None:
        self.db.delete(topic)
        self.db.commit()


class MessageStore:
    def __init__(self, db: Session):
        self.db = db

    def create(self, topic_id: int, data: MessageCreate, owner_id: int) -> Message:
        message = Message(topic_id=topic_id, owner_id=owner_id, **data.model_dump())
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list(self, topic_id: int) -> list[Message]:
        statement = select(Message).where(Message.topic_id == topic_id).order_by(Message.id)
        return self.db.scalars(statement).all()


class UserStore:
    def __init__(self, db: Session):
        self.db = db

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def register(self, data: UserRegister) -> User | None:
        username = data.username
        password_hash = PasswordHasher().hash(data.password.get_secret_value())
        user = User(username=username, password_hash=password_hash)
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            if self.get_by_username(username) is not None:
                return None
            raise
        self.db.refresh(user)
        return user
