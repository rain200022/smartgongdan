import pytest

from app.core.priority import AffectedScope, ImpactLevel, UrgencyLevel
from app.models.ticket import TicketPriority
from app.services.priority_service import calculate_priority


@pytest.mark.parametrize(
    ("impact", "urgency", "scope", "expected_score", "expected_priority"),
    [
        (
            ImpactLevel.CORE_BUSINESS,
            UrgencyLevel.HIGH,
            AffectedScope.SINGLE_USER,
            84.0,
            TicketPriority.P1,
        ),
        (
            ImpactLevel.BUSINESS_LIMITED,
            UrgencyLevel.HIGH,
            AffectedScope.SINGLE_USER,
            69.0,
            TicketPriority.P2,
        ),
        (
            ImpactLevel.INDIVIDUAL_WORK,
            UrgencyLevel.MEDIUM,
            AffectedScope.SINGLE_USER,
            42.0,
            TicketPriority.P3,
        ),
        (
            ImpactLevel.MINOR,
            UrgencyLevel.LOW,
            AffectedScope.SINGLE_USER,
            15.0,
            TicketPriority.P4,
        ),
    ],
)
def test_calculate_priority_uses_weighted_thresholds(
    impact: ImpactLevel,
    urgency: UrgencyLevel,
    scope: AffectedScope,
    expected_score: float,
    expected_priority: TicketPriority,
) -> None:
    result = calculate_priority(impact, urgency, scope)

    assert result.score == expected_score
    assert result.priority is expected_priority
