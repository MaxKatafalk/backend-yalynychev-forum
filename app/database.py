import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Укажите DATABASE_URL в .env или переменных окружения")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


@event.listens_for(engine, "connect")
def configure_connection(connection, connection_record):
    connection.create_function("casefold", 1, str.casefold, deterministic=True)
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
