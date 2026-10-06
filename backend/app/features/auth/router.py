"""
Auth Router — สมัครสมาชิก / เข้าสู่ระบบ (JWT access token) / ข้อมูลผู้ใช้ปัจจุบัน

ออกจากระบบ = frontend ลบ token ออกจาก localStorage (JWT แบบ stateless ไม่มีสถานะฝั่ง server)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.features.auth.dependencies import get_current_active_user
from app.features.auth.models import User
from app.features.auth.schemas import LoginRequest, SignUpRequest, TokenResponse, UserResponse
from app.features.auth.security import create_access_token
from app.features.auth.service import authenticate_user, create_user, is_email_or_username_taken
from core.database import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="สมัครสมาชิกใหม่")
def signup(body: SignUpRequest, db: Session = Depends(get_db)):
    """สร้างบัญชีใหม่ (ตรวจ email / username ซ้ำ, hash password ด้วย bcrypt)"""
    uname = body.username or body.email.split("@")[0]
    taken = is_email_or_username_taken(db, body.email, uname)
    if taken == "email":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="อีเมลนี้ถูกใช้งานแล้ว")
    if taken == "username":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ชื่อผู้ใช้นี้ถูกใช้งานแล้ว")
    user = create_user(db, email=body.email, username=uname, password=body.password, full_name=body.full_name,
                       role=body.role, department=body.department, title=body.title)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="เข้าสู่ระบบ")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """ตรวจ email + password แล้วออก access token (อายุตาม ACCESS_TOKEN_EXPIRE_MINUTES)"""
    user = authenticate_user(db, email=body.email, password=body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="บัญชีนี้ถูกระงับการใช้งาน")
    return TokenResponse(access_token=create_access_token(data={"sub": str(user.id)}),
                         user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse, summary="ข้อมูลผู้ใช้ปัจจุบัน")
def get_me(current_user: User = Depends(get_current_active_user)):
    return UserResponse.model_validate(current_user)
