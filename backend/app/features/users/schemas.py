from pydantic import BaseModel
from typing import Literal, Optional

class UserItem(BaseModel):
    id: str
    name: str
    email: str
    role: Literal["admin", "engineer", "inspector"]
    department: str
    title: str
    createdAt: str

class CreateUserRequest(BaseModel):
    name: str
    email: str
    password: Optional[str] = "default123"
    role: Literal["admin", "engineer", "inspector"] = "engineer"
    department: Optional[str] = "Maintenance"
    title: Optional[str] = "Maintenance Engineer"

class UpdateUserRoleRequest(BaseModel):
    role: Literal["admin", "engineer", "inspector"]
