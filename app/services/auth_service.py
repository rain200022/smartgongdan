import hashlib
import secrets
from datetime import timedelta

from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    InvalidUserOperationError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.core.time import utc_now
from app.models.user import AuthSession, User
from app.schemas.auth import UserCreate

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("smart-gongdan-dummy-password")


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user(db: Session, payload: UserCreate) -> User:
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise UserAlreadyExistsError(payload.username)
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=password_hash.hash(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User:
    normalized = username.strip().lower()
    user = db.scalar(select(User).where(User.username == normalized))
    stored_hash = user.password_hash if user is not None else DUMMY_HASH
    valid, updated_hash = password_hash.verify_and_update(password, stored_hash)
    if user is None or not valid or not user.is_active:
        raise AuthenticationError("用户名或密码错误")
    if updated_hash is not None:
        user.password_hash = updated_hash
        db.commit()
    return user


def create_session(db: Session, user: User) -> str:
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    record = AuthSession(
        token_hash=hash_session_token(token),
        user_id=user.id,
        expires_at=utc_now() + timedelta(hours=settings.auth_session_hours),
    )
    db.add(record)
    db.commit()
    return token


def get_session_user(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    statement = (
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == hash_session_token(token),
            AuthSession.expires_at > utc_now(),
            User.is_active.is_(True),
        )
    )
    return db.scalar(statement)


def revoke_session(db: Session, token: str | None) -> None:
    if not token:
        return
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_session_token(token))
    )
    if session is not None:
        db.delete(session)
        db.commit()


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at, User.id)))


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError(user_id)
    return user


def set_user_active(db: Session, *, user_id: int, is_active: bool, acting_user: User) -> User:
    user = get_user(db, user_id)
    if user.id == acting_user.id and not is_active:
        raise InvalidUserOperationError("不能停用当前登录账号")
    user.is_active = is_active
    if not is_active:
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    db.refresh(user)
    return user


def reset_user_password(db: Session, *, user_id: int, new_password: str, acting_user: User) -> User:
    user = get_user(db, user_id)
    if user.id == acting_user.id:
        raise InvalidUserOperationError("请通过个人密码修改流程更新当前账号密码")
    user.password_hash = password_hash.hash(new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    db.refresh(user)
    return user
