from typing import List, Optional
from datetime import datetime
from .schemas import UserItem, CreateUserRequest

_USERS: List[UserItem] = [
    UserItem(
        id="usr-1",
        name="Alex Tan",
        email="alex.tan@machinery.internal",
        role="engineer",
        department="Preventive Maintenance",
        title="Senior Reliability Engineer",
        createdAt="2026-08-01T08:00:00Z",
    ),
    UserItem(
        id="usr-2",
        name="Root Administrator",
        email="admin@machinery.internal",
        role="admin",
        department="Industrial Automation",
        title="Lead Systems Architect",
        createdAt="2026-07-15T08:00:00Z",
    ),
]

def get_users() -> List[UserItem]:
    return _USERS

def create_user(req: CreateUserRequest) -> UserItem:
    new_user = UserItem(
        id=f"usr-{len(_USERS) + 1}",
        name=req.name,
        email=req.email,
        role=req.role,
        department=req.department or "Maintenance",
        title=req.title or "Engineer",
        createdAt=datetime.utcnow().isoformat() + "Z",
    )
    _USERS.append(new_user)
    return new_user

def update_role(user_id: str, new_role: str) -> Optional[UserItem]:
    for u in _USERS:
        if u.id == user_id:
            u.role = new_role  # type: ignore
            return u
    return None

def delete_user(user_id: str) -> bool:
    global _USERS
    orig = len(_USERS)
    _USERS = [u for u in _USERS if u.id != user_id]
    return len(_USERS) < orig
