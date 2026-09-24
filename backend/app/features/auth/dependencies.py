"""
Auth Dependencies — FastAPI dependency injection สำหรับตรวจสอบ JWT
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.features.auth.models import User
from app.features.auth.security import decode_token
from app.features.auth.service import get_user_by_id
from core.database import get_db

# ใช้ HTTPBearer เพื่อรับ token จาก Authorization header
# แสดง lock icon ใน Swagger UI ให้ใส่ token ได้เลย
bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode JWT access token จาก Authorization header
    แล้ว return User object จาก database

    ใช้เป็น dependency ใน endpoint ที่ต้อง login ก่อน
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="ไม่สามารถยืนยันตัวตนได้ — token ไม่ถูกต้องหรือหมดอายุ",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise credentials_exception

    # ตรวจสอบว่าเป็น access token (ไม่ใช่ refresh token)
    if payload.get("type") != "access":
        raise credentials_exception

    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

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
