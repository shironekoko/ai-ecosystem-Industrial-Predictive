"""
Auth Dependencies — FastAPI dependency injection สำหรับตรวจสอบ JWT

ทุก endpoint ยกเว้น GET /health, POST /auth/signup, POST /auth/login ต้องล็อกอิน
- token ไม่มี/ไม่ถูกต้อง/หมดอายุ → 401 (เว็บล้าง session แล้วพากลับหน้า login)
- บัญชีถูกระงับ / ไม่ใช่ admin → 403
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.features.auth.models import User
from app.features.auth.security import decode_token
from app.features.auth.service import get_user_by_id
from core.database import SessionLocal, get_db

# ใช้ HTTPBearer เพื่อรับ token จาก Authorization header
# แสดง lock icon ใน Swagger UI ให้ใส่ token ได้เลย
bearer_scheme = HTTPBearer()


def user_from_token(db: Session, token: str | None) -> User | None:
    """access token → User (None ถ้า token ไม่ถูกต้อง/หมดอายุ/เป็น token ประเภทอื่น/ไม่พบผู้ใช้)"""
    payload = decode_token(token) if token else None
    if payload is None or payload.get("type") != "access":
        return None
    try:
        user_id = uuid.UUID(payload.get("sub") or "")
    except ValueError:
        return None
    return get_user_by_id(db, user_id)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode JWT access token จาก Authorization header
    แล้ว return User object จาก database

    ใช้เป็น dependency ใน endpoint ที่ต้อง login ก่อน
    """
    user = user_from_token(db, credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ไม่สามารถยืนยันตัวตนได้ — token ไม่ถูกต้องหรือหมดอายุ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """ตรวจสอบว่า user ยัง active อยู่"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="บัญชีนี้ถูกระงับการใช้งาน",
        )
    return current_user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """งานของ admin (สลับ/โหลดแบบจำลอง, promote/reject) — ตรวจที่ backend (หน้าเว็บซ่อนปุ่มอย่างเดียวไม่พอ)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def actor_name(user: User) -> str:
    """ชื่อผู้ทำรายการที่บันทึกใน audit — มาจากบัญชีที่ล็อกอิน ไม่เชื่อค่า actor ที่ client ส่งมา"""
    return user.full_name or user.username


def websocket_user(token: str | None) -> User | None:
    """ตรวจ token ของ WebSocket (browser ส่ง Authorization header กับ WebSocket ไม่ได้) — None = ไม่ผ่าน"""
    with SessionLocal() as db:
        user = user_from_token(db, token)
        return user if user is not None and user.is_active else None
