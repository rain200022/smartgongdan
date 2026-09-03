import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AIServiceError
from app.core.priority import AffectedScope, ImpactLevel, UrgencyLevel
from app.models.ai_analysis import JudgeType, TicketAIAnalysisRecord, TicketJudgment
from app.models.ticket import Ticket, TicketPriority
from app.schemas.ai_analysis import TicketAIAnalysis
from app.services.ai_service import get_ai_service


def create_ticket(
    client: TestClient,
    *,
    title: str = "VPN无法连接",
    description: str = "公司笔记本提示：认证服务器不可用，我已经重启VPN客户端",
) -> int:
    response = client.post(
        "/tickets",
        json={
            "title": title,
            "description": description,
            "user_category": "软件/VPN",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_analyze_ticket_persists_analysis_and_ai_judgment(
    client: TestClient, db_session: Session
) -> None:
    ticket_id = create_ticket(client)

    response = client.post(f"/tickets/{ticket_id}/analyze")

    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"] == ticket_id
    assert body["category"] == "网络"
    assert body["subcategory"] == "VPN"
    assert body["device"] == "公司笔记本"
    assert body["error_message"] == "认证服务器不可用"
    assert "重启VPN客户端" in body["attempted_actions"]
    assert body["impact"] == "业务功能受限"
    assert body["urgency"] == "中"
    assert body["affected_scope"] == "单用户"
    assert body["impact_score"] == 70
    assert body["urgency_score"] == 60
    assert body["scope_score"] == 20
    assert body["priority_score"] == 57.0
    assert body["calculated_priority"] == "P3"
    assert body["model_name"] == "local-rules-v1"

    latest_response = client.get(f"/tickets/{ticket_id}/analysis/latest")
    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == body["id"]

    records = list(db_session.scalars(select(TicketAIAnalysisRecord)))
    judgments = list(db_session.scalars(select(TicketJudgment).order_by(TicketJudgment.created_at)))
    assert len(records) == 1
    assert [item.judge_type for item in judgments] == [JudgeType.USER, JudgeType.AI]
    assert judgments[1].category == "网络"
    assert judgments[1].confidence == body["confidence"]
    assert db_session.get(Ticket, ticket_id).ai_priority is TicketPriority.P3


def test_reanalysis_appends_history_instead_of_overwriting(
    client: TestClient, db_session: Session
) -> None:
    ticket_id = create_ticket(client)

    assert client.post(f"/tickets/{ticket_id}/analyze").status_code == 200
    assert client.post(f"/tickets/{ticket_id}/analyze").status_code == 200

    assert len(list(db_session.scalars(select(TicketAIAnalysisRecord)))) == 2
    ai_judgments = list(
        db_session.scalars(select(TicketJudgment).where(TicketJudgment.judge_type == JudgeType.AI))
    )
    assert len(ai_judgments) == 2


def test_unknown_issue_uses_fallback_classification(client: TestClient) -> None:
    ticket_id = create_ticket(
        client,
        title="需要咨询",
        description="我想了解公司IT服务台的办公时间",
    )

    response = client.post(f"/tickets/{ticket_id}/analyze")

    assert response.status_code == 200
    assert response.json()["category"] == "其他"
    assert response.json()["subcategory"] == "未分类"


def test_analyze_missing_ticket_returns_404_without_calling_provider(client: TestClient) -> None:
    response = client.post("/tickets/999/analyze")
    assert response.status_code == 404


def test_provider_failure_returns_502_without_partial_records(
    client: TestClient, db_session: Session
) -> None:
    class FailingAIService:
        model_name = "failing-provider"

        def analyze_ticket(self, _ticket: object) -> TicketAIAnalysis:
            raise AIServiceError("AI provider unavailable")

    ticket_id = create_ticket(client)
    client.app.dependency_overrides[get_ai_service] = lambda: FailingAIService()
    try:
        response = client.post(f"/tickets/{ticket_id}/analyze")
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider unavailable"}
    assert list(db_session.scalars(select(TicketAIAnalysisRecord))) == []
    ai_judgments = list(
        db_session.scalars(select(TicketJudgment).where(TicketJudgment.judge_type == JudgeType.AI))
    )
    assert ai_judgments == []
    assert db_session.get(Ticket, ticket_id).ai_priority is None


def test_closed_ticket_rejects_analysis_before_provider_call(
    client: TestClient, db_session: Session
) -> None:
    class TrackingAIService:
        model_name = "tracking-provider"
        called = False

        def analyze_ticket(self, _ticket: object) -> TicketAIAnalysis:
            self.called = True
            return TicketAIAnalysis(
                summary="不应保存",
                category="网络",
                subcategory="VPN",
                confidence=0.9,
                impact=ImpactLevel.BUSINESS_LIMITED,
                urgency=UrgencyLevel.MEDIUM,
                affected_scope=AffectedScope.SINGLE_USER,
            )

    ticket_id = create_ticket(client)
    closed = client.post(
        f"/tickets/{ticket_id}/close",
        json={
            "final_category": "网络/VPN",
            "final_priority": "P3",
            "resolution": "已恢复",
        },
    )
    assert closed.status_code == 200
    provider = TrackingAIService()
    client.app.dependency_overrides[get_ai_service] = lambda: provider
    try:
        response = client.post(f"/tickets/{ticket_id}/analyze")
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert response.status_code == 409
    assert provider.called is False
    assert list(db_session.scalars(select(TicketAIAnalysisRecord))) == []


def test_latest_analysis_returns_404_before_analysis(client: TestClient) -> None:
    ticket_id = create_ticket(client)
    response = client.get(f"/tickets/{ticket_id}/analysis/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Ticket {ticket_id} has no AI analysis"


def test_schema_rejects_category_invented_by_model() -> None:
    with pytest.raises(ValidationError):
        TicketAIAnalysis.model_validate(
            {
                "summary": "VPN故障",
                "category": "网络",
                "subcategory": "远程访问",
                "attempted_actions": [],
                "confidence": 0.9,
            }
        )


def test_engineer_close_creates_separate_judgment(client: TestClient, db_session: Session) -> None:
    ticket_id = create_ticket(client)
    assert client.post(f"/tickets/{ticket_id}/analyze").status_code == 200

    response = client.post(
        f"/tickets/{ticket_id}/close",
        json={
            "final_category": "网络/VPN",
            "final_priority": "P3",
            "resolution": "重新签发证书",
        },
    )
    assert response.status_code == 200

    judgments = list(db_session.scalars(select(TicketJudgment)))
    assert [judgment.judge_type for judgment in judgments] == [
        JudgeType.USER,
        JudgeType.AI,
        JudgeType.ENGINEER,
    ]
    assert judgments[-1].category == "网络"
    assert judgments[-1].subcategory == "VPN"
