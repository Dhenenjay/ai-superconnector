from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from core.config import settings
import os


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_dir(db_url: str):
    if db_url.startswith("sqlite+pysqlite"):
        path = db_url.replace("sqlite+pysqlite:///", "")
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)


DATABASE_URL = settings.resolved_database_url
_ensure_sqlite_dir(DATABASE_URL)

# SQLite engine with check_same_thread False for FastAPI concurrency
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if DATABASE_URL.startswith("sqlite") else None,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

