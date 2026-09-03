from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services import auth_service

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    token = request.cookies.get(get_settings().auth_cookie_name)
    user = auth_service.get_session_user(db, token)
    if user is None:
        raise AuthenticationError("请先登录")
    return user


def require_staff(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role not in {UserRole.ENGINEER, UserRole.ADMIN}:
        raise AuthorizationError("该操作需要工程师或管理员权限")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role is not UserRole.ADMIN:
        raise AuthorizationError("该操作需要管理员权限")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
StaffUser = Annotated[User, Depends(require_staff)]
AdminUser = Annotated[User, Depends(require_admin)]
