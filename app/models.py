from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func

from .database import Base


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed')", name="ck_topics_status"),
    )

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    author = Column(String(100), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(6), nullable=False, server_default="open")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"))
    author = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    id = Column(Integer, primary_key=True)
    username = Column(String(64), nullable=False)
    password_hash = Column(Text, nullable=False)
