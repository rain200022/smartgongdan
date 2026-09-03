from dataclasses import dataclass

from app.core.priority import AffectedScope, ImpactLevel, UrgencyLevel
from app.models.ticket import TicketPriority

IMPACT_WEIGHT = 0.5
URGENCY_WEIGHT = 0.3
SCOPE_WEIGHT = 0.2

IMPACT_SCORES: dict[ImpactLevel, int] = {
    ImpactLevel.CORE_BUSINESS: 100,
    ImpactLevel.BUSINESS_LIMITED: 70,
    ImpactLevel.INDIVIDUAL_WORK: 40,
    ImpactLevel.MINOR: 10,
}
URGENCY_SCORES: dict[UrgencyLevel, int] = {
    UrgencyLevel.HIGH: 100,
    UrgencyLevel.MEDIUM: 60,
    UrgencyLevel.LOW: 20,
}
SCOPE_SCORES: dict[AffectedScope, int] = {
    AffectedScope.COMPANY: 100,
    AffectedScope.MULTIPLE_DEPARTMENTS: 80,
    AffectedScope.MULTIPLE_USERS: 60,
    AffectedScope.SINGLE_USER: 20,
}


@dataclass(frozen=True, slots=True)
class PriorityAssessment:
    priority: TicketPriority
    score: float
    impact_score: int
    urgency_score: int
    scope_score: int


def calculate_priority(
    impact: ImpactLevel,
    urgency: UrgencyLevel,
    affected_scope: AffectedScope,
) -> PriorityAssessment:
    impact_score = IMPACT_SCORES[impact]
    urgency_score = URGENCY_SCORES[urgency]
    scope_score = SCOPE_SCORES[affected_scope]
    score = round(
        impact_score * IMPACT_WEIGHT + urgency_score * URGENCY_WEIGHT + scope_score * SCOPE_WEIGHT,
        1,
    )
    if score >= 80:
        priority = TicketPriority.P1
    elif score >= 60:
        priority = TicketPriority.P2
    elif score >= 30:
        priority = TicketPriority.P3
    else:
        priority = TicketPriority.P4
    return PriorityAssessment(
        priority=priority,
        score=score,
        impact_score=impact_score,
        urgency_score=urgency_score,
        scope_score=scope_score,
    )
