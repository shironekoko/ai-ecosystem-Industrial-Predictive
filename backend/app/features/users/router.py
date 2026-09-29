from fastapi import APIRouter, HTTPException
from typing import List
from .schemas import UserItem, CreateUserRequest, UpdateUserRoleRequest
from . import service

router = APIRouter(prefix="/users", tags=["Users & RBAC Access Console"])

@router.get("", response_model=List[UserItem], summary="Get all operators and users")
async def get_users():
    """Retrieve all maintenance engineers and administrators"""
    return service.get_users()

@router.post("", response_model=UserItem, status_code=201, summary="Create a new user")
async def create_user(req: CreateUserRequest):
    """Register a new operator or staff member into the system"""
    return service.create_user(req)

@router.patch("/{user_id}/role", response_model=UserItem, summary="Change user RBAC role")
async def update_user_role(user_id: str, req: UpdateUserRoleRequest):
    """Change authorization role (admin / engineer / inspector)"""
    updated = service.update_role(user_id, req.role)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated

@router.delete("/{user_id}", summary="Delete user account")
async def delete_user(user_id: str):
    """Delete an operator account"""
    success = service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted", "id": user_id}
