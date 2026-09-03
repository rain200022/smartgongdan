from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class SolutionReviewDecision(StrEnum):
    ADOPTED = "ADOPTED"
    REJECTED = "REJECTED"


class RejectionCategory(StrEnum):
    EVIDENCE_MISMATCH = "EVIDENCE_MISMATCH"
    ALREADY_TRIED = "ALREADY_TRIED"
    RISK_OR_INCOMPLETE = "RISK_OR_INCOMPLETE"
    OTHER = "OTHER"


class TicketAISolution(Base):
    __tablename__ = "ticket_ai_solutions"
    __table_args__ = (Index("ix_ticket_ai_solutions_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    diagnosis: Mapped[str] = mapped_column(Text)
    possible_causes: Mapped[list[str]] = mapped_column(JSON, default=list)
    steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    referenced_cases: Mapped[list[str]] = mapped_column(JSON, default=list)
    need_human: Mapped[bool] = mapped_column(Boolean, default=False)
    model_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    review: Mapped[TicketSolutionReview | None] = relationship(
        back_populates="solution",
        uselist=False,
    )


class TicketSolutionReview(Base):
    __tablename__ = "ticket_solution_reviews"
    __table_args__ = (
        Index("ix_ticket_solution_reviews_ticket_created", "ticket_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    solution_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_ai_solutions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[SolutionReviewDecision] = mapped_column(
        SqlEnum(
            SolutionReviewDecision,
            name="solution_review_decision",
            values_callable=lambda values: [value.value for value in values],
        )
    )
    engineer_solution: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    rejection_category: Mapped[RejectionCategory | None] = mapped_column(
        SqlEnum(
            RejectionCategory,
            name="solution_rejection_category",
            values_callable=lambda values: [value.value for value in values],
        )
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    solution: Mapped[TicketAISolution] = relationship(back_populates="review")
