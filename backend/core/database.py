"""
Database — SQLAlchemy engine & session factory

ใช้ร่วมกันทั้ง app ผ่าน FastAPI dependency injection
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings

engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class สำหรับ ORM models ทั้งหมด"""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — สร้าง DB session per-request แล้ว close อัตโนมัติ"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
