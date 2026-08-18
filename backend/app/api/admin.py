"""用户管理 API（仅管理员）"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.core.deps import get_admin_user
from app.schemas.user import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


class UserListResponse(BaseModel):
    total: int
    users: list[UserResponse]


class UpdateRoleRequest(BaseModel):
    role: str  # admin / user


@router.get("/users", response_model=UserListResponse)
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有用户列表（仅管理员）"""
    result = await db.execute(
        select(User).order_by(User.created_at.asc())
    )
    users = result.scalars().all()
    return UserListResponse(
        total=len(users),
        users=[UserResponse.model_validate(u) for u in users],
    )


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    data: UpdateRoleRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """修改用户角色（仅管理员）"""
    if data.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="角色必须为 admin 或 user")

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.user_id == admin.user_id and data.role != "admin":
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")

    user.role = data.role
    await db.flush()
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}/active", response_model=UserResponse)
async def toggle_user_active(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用用户（仅管理员）"""
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="不能禁用自己")

    user.is_active = not user.is_active
    await db.flush()
    return UserResponse.model_validate(user)
