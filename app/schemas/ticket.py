from datetime import datetime

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.classification import split_classification, validate_classification
from app.models.ticket import TicketPriority, TicketStatus
from app.schemas.common import APIModel


class TicketCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    user_category: str | None = Field(default=None, max_length=100)


class TicketUpdate(APIModel):
    final_category: str | None = Field(default=None, min_length=1, max_length=100)
    final_priority: TicketPriority | None = None
    status: TicketStatus | None = None

    @field_validator("final_category")
    @classmethod
    def validate_final_category(cls, value: str | None) -> str | None:
        if value is None:
            return value
        category, subcategory = split_classification(value)
        validate_classification(category, subcategory)
        return f"{category}/{subcategory}"

    @model_validator(mode="after")
    def reject_empty_update(self) -> "TicketUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class TicketClose(APIModel):
    final_category: str = Field(min_length=1, max_length=100)
    final_priority: TicketPriority
    resolution: str = Field(min_length=1, max_length=20_000)

    @field_validator("final_category")
    @classmethod
    def validate_final_category(cls, value: str) -> str:
        category, subcategory = split_classification(value)
        validate_classification(category, subcategory)
        return f"{category}/{subcategory}"


class TicketRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_id: int | None
    assigned_engineer_id: int | None
    title: str
    description: str
    user_category: str | None
    final_category: str | None
    ai_priority: TicketPriority | None
    final_priority: TicketPriority | None
    resolution: str | None
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class TicketList(APIModel):
    items: list[TicketRead]
    total: int
    limit: int
    offset: int
