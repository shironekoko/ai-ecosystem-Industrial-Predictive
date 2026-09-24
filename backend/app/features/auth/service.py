"""
Auth Service — Business logic สำหรับ sign-up, login, token refresh
"""

import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.features.auth.models import User
from app.features.auth.security import hash_password, verify_password


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """ค้นหา user จาก ID"""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    """ค้นหา user จาก email"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    """ค้นหา user จาก username"""
    return db.query(User).filter(User.username == username).first()


def is_email_or_username_taken(db: Session, email: str, username: str) -> str | None:
    """ตรวจสอบว่า email หรือ username ซ้ำหรือไม่ — return field ที่ซ้ำ หรือ None"""
    existing = (
        db.query(User)
        .filter(or_(User.email == email, User.username == username))
        .first()
    )
    if existing is None:
        return None
    if existing.email == email:
        return "email"
    return "username"


def create_user(
    db: Session,
    *,
    email: str,
    username: str,
    password: str,
    full_name: str | None = None,
) -> User:
    """สร้าง user ใหม่ — hash password แล้วบันทึกลง DB"""
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User | None:
    """ตรวจสอบ email + password — return User ถ้าถูกต้อง, None ถ้าผิด"""
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
