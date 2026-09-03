from datetime import datetime

from pydantic import ConfigDict, Field

from app.core.priority import AffectedScope, ImpactLevel, UrgencyLevel
from app.models.ticket import TicketPriority
from app.schemas.common import ClassificationPair


class TicketAIAnalysisBase(ClassificationPair):
    summary: str = Field(min_length=1, max_length=500)
    device: str | None = Field(default=None, max_length=200)
    symptom: str | None = Field(default=None, max_length=1_000)
    error_message: str | None = Field(default=None, max_length=1_000)
    attempted_actions: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)


class TicketAIAnalysis(TicketAIAnalysisBase):
    impact: ImpactLevel
    urgency: UrgencyLevel
    affected_scope: AffectedScope


class TicketAIAnalysisRead(TicketAIAnalysisBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    impact: ImpactLevel | None
    urgency: UrgencyLevel | None
    affected_scope: AffectedScope | None
    impact_score: int | None
    urgency_score: int | None
    scope_score: int | None
    priority_score: float | None
    calculated_priority: TicketPriority | None
    model_name: str
    created_at: datetime
