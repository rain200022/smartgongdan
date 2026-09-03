from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.priority import AffectedScope, ImpactLevel, UrgencyLevel
from app.core.time import utc_now
from app.db.base import Base
from app.models.ticket import TicketPriority


class JudgeType(StrEnum):
    USER = "USER"
    AI = "AI"
    ENGINEER = "ENGINEER"


class TicketAIAnalysisRecord(Base):
    __tablename__ = "ticket_ai_analysis"
    __table_args__ = (
        Index("ix_ticket_ai_analysis_ticket_created", "ticket_id", "created_at"),
        CheckConstraint(
            "impact_score IS NULL OR impact_score BETWEEN 0 AND 100",
            name="ck_ticket_ai_analysis_impact_score",
        ),
        CheckConstraint(
            "urgency_score IS NULL OR urgency_score BETWEEN 0 AND 100",
            name="ck_ticket_ai_analysis_urgency_score",
        ),
        CheckConstraint(
            "scope_score IS NULL OR scope_score BETWEEN 0 AND 100",
            name="ck_ticket_ai_analysis_scope_score",
        ),
        CheckConstraint(
            "priority_score IS NULL OR priority_score BETWEEN 0 AND 100",
            name="ck_ticket_ai_analysis_priority_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100))
    subcategory: Mapped[str] = mapped_column(String(100))
    device: Mapped[str | None] = mapped_column(String(200))
    symptom: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    attempted_actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    impact: Mapped[ImpactLevel | None] = mapped_column(
        SqlEnum(
            ImpactLevel,
            name="ticket_impact_level",
            values_callable=lambda x: [e.value for e in x],
        )
    )
    urgency: Mapped[UrgencyLevel | None] = mapped_column(
        SqlEnum(
            UrgencyLevel,
            name="ticket_urgency_level",
            values_callable=lambda x: [e.value for e in x],
        )
    )
    affected_scope: Mapped[AffectedScope | None] = mapped_column(
        SqlEnum(
            AffectedScope,
            name="ticket_affected_scope",
            values_callable=lambda x: [e.value for e in x],
        )
    )
    impact_score: Mapped[int | None] = mapped_column(Integer)
    urgency_score: Mapped[int | None] = mapped_column(Integer)
    scope_score: Mapped[int | None] = mapped_column(Integer)
    priority_score: Mapped[float | None] = mapped_column(Float)
    calculated_priority: Mapped[TicketPriority | None] = mapped_column(
        SqlEnum(
            TicketPriority,
            name="ticket_priority",
            values_callable=lambda x: [e.value for e in x],
        )
    )
    model_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TicketJudgment(Base):
    __tablename__ = "ticket_judgments"
    __table_args__ = (Index("ix_ticket_judgments_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    judge_type: Mapped[JudgeType] = mapped_column(
        SqlEnum(JudgeType, name="judge_type", values_callable=lambda x: [e.value for e in x])
    )
    category: Mapped[str] = mapped_column(String(100))
    subcategory: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TicketClassificationEvaluation(Base):
    __tablename__ = "ticket_classification_evaluations"
    __table_args__ = (
        Index(
            "ix_ticket_classification_evaluations_ticket_created",
            "ticket_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    ai_judgment_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_judgments.id", ondelete="CASCADE"), nullable=False
    )
    engineer_judgment_id: Mapped[int] = mapped_column(
        ForeignKey("ticket_judgments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    category_agreement: Mapped[bool] = mapped_column(Boolean)
    subcategory_agreement: Mapped[bool] = mapped_column(Boolean)
    agreement: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
