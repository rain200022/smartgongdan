from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.ticket import TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    user_category: str | None = Field(default=None, max_length=100)


class TicketUpdate(BaseModel):
    final_category: str | None = Field(default=None, min_length=1, max_length=100)
    final_priority: TicketPriority | None = None
    status: TicketStatus | None = None

    @model_validator(mode="after")
    def reject_empty_update(self) -> "TicketUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class TicketClose(BaseModel):
    final_category: str = Field(min_length=1, max_length=100)
    final_priority: TicketPriority
    resolution: str = Field(min_length=1, max_length=20_000)


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
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


class TicketList(BaseModel):
    items: list[TicketRead]
    total: int
    limit: int
    offset: int
