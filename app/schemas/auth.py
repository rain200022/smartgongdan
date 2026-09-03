from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from app.models.user import UserRole
from app.schemas.common import APIModel


class LoginRequest(APIModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()


class UserCreate(APIModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=10, max_length=200)
    role: UserRole = UserRole.USER

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("display_name")
    @classmethod
    def trim_display_name(cls, value: str) -> str:
        return value.strip()


class UserRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserStatusUpdate(APIModel):
    is_active: bool


class UserPasswordReset(APIModel):
    new_password: str = Field(min_length=10, max_length=200)
