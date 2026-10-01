from typing import List, Optional
from datetime import datetime
import uuid
from .schemas import UserItem, CreateUserRequest
from core.database import SessionLocal
from app.features.auth.models import User as UserModel
from app.features.auth.security import hash_password


def _model_to_item(u: UserModel) -> UserItem:
    return UserItem(
        id=str(u.id),
        name=u.full_name or u.username or u.email.split("@")[0],
        email=u.email,
        role=getattr(u, "role", "engineer") or "engineer",
        department=getattr(u, "department", "Maintenance Team") or "Maintenance Team",
        title=getattr(u, "title", "Reliability Engineer") or "Reliability Engineer",
        createdAt=u.created_at.isoformat() if u.created_at else datetime.utcnow().isoformat() + "Z",
    )


def get_users() -> List[UserItem]:
    db = SessionLocal()
    try:
        users = db.query(UserModel).order_by(UserModel.created_at.asc()).all()
        return [_model_to_item(u) for u in users]
    finally:
        db.close()


def create_user(req: CreateUserRequest) -> UserItem:
    db = SessionLocal()
    try:
        uname = req.email.split("@")[0]
        pwd = getattr(req, "password", None) or "default123"
        new_u = UserModel(
            email=req.email,
            username=uname,
            hashed_password=hash_password(pwd),
            full_name=req.name,
            role=req.role,
            department=req.department or "Maintenance Team",
            title=req.title or "Reliability Engineer",
            is_active=True,
        )
        db.add(new_u)
        db.commit()
        db.refresh(new_u)
        return _model_to_item(new_u)
    finally:
        db.close()


def update_role(user_id: str, new_role: str) -> Optional[UserItem]:
    db = SessionLocal()
    try:
        u = None
        try:
            uid = uuid.UUID(user_id)
            u = db.query(UserModel).filter(UserModel.id == uid).first()
        except Exception:
            u = db.query(UserModel).filter(UserModel.email == user_id).first()

        if u:
            u.role = new_role
            db.commit()
            db.refresh(u)
            return _model_to_item(u)
        return None
    finally:
        db.close()


def delete_user(user_id: str) -> bool:
    db = SessionLocal()
    try:
        u = None
        try:
            uid = uuid.UUID(user_id)
            u = db.query(UserModel).filter(UserModel.id == uid).first()
        except Exception:
            u = db.query(UserModel).filter(UserModel.email == user_id).first()

        if u:
            db.delete(u)
            db.commit()
            return True
        return False
    finally:
        db.close()

