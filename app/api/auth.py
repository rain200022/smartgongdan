from fastapi import APIRouter, Request, Response, status

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.auth import (
    LoginRequest,
    UserCreate,
    UserPasswordReset,
    UserRead,
    UserStatusUpdate,
)
from app.services import auth_service

router = APIRouter(tags=["authentication"])


@router.post("/auth/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, db: DbSession) -> UserRead:
    user = auth_service.authenticate_user(db, payload.username, payload.password)
    token = auth_service.create_session(db, user)
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_hours * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return UserRead.model_validate(user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> None:
    settings = get_settings()
    auth_service.revoke_session(db, request.cookies.get(settings.auth_cookie_name))
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/auth/me", response_model=UserRead)
def current_user(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, _admin: AdminUser) -> UserRead:
    return UserRead.model_validate(auth_service.create_user(db, payload))


@router.get("/users", response_model=list[UserRead])
def list_users(db: DbSession, _admin: AdminUser) -> list[UserRead]:
    return [UserRead.model_validate(user) for user in auth_service.list_users(db)]


@router.patch("/users/{user_id}/status", response_model=UserRead)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: DbSession,
    admin: AdminUser,
) -> UserRead:
    user = auth_service.set_user_active(
        db,
        user_id=user_id,
        is_active=payload.is_active,
        acting_user=admin,
    )
    return UserRead.model_validate(user)


@router.post("/users/{user_id}/password/reset", response_model=UserRead)
def reset_user_password(
    user_id: int,
    payload: UserPasswordReset,
    db: DbSession,
    admin: AdminUser,
) -> UserRead:
    user = auth_service.reset_user_password(
        db,
        user_id=user_id,
        new_password=payload.new_password,
        acting_user=admin,
    )
    return UserRead.model_validate(user)
