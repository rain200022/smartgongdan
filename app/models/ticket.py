from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (Index("ix_tickets_status_created_at", "status", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    user_category: Mapped[str | None] = mapped_column(String(100))
    final_category: Mapped[str | None] = mapped_column(String(100))
    ai_priority: Mapped[TicketPriority | None] = mapped_column(
        SqlEnum(
            TicketPriority, name="ticket_priority", values_callable=lambda x: [e.value for e in x]
        )
    )
    final_priority: Mapped[TicketPriority | None] = mapped_column(
        SqlEnum(
            TicketPriority, name="ticket_priority", values_callable=lambda x: [e.value for e in x]
        )
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TicketStatus] = mapped_column(
        SqlEnum(TicketStatus, name="ticket_status", values_callable=lambda x: [e.value for e in x]),
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
