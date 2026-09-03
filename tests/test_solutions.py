from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AIServiceError
from app.models.solution import (
    SolutionReviewDecision,
    TicketAISolution,
    TicketSolutionReview,
)
from app.schemas.solution import TicketAISolutionDraft
from app.services.ai_service import get_ai_service

from .test_search import create_current_ticket, seed_minimal_catalog


def prepare_analyzed_ticket(client: TestClient) -> int:
    ticket_id = create_current_ticket(client)
    assert client.post(f"/tickets/{ticket_id}/analyze").status_code == 200
    return ticket_id


def test_generate_solution_uses_retrieved_evidence_and_appends_history(
    client: TestClient,
    db_session: Session,
) -> None:
    ticket_id = prepare_analyzed_ticket(client)
    seed_minimal_catalog(db_session)

    first = client.post(f"/tickets/{ticket_id}/solutions/generate")
    second = client.post(f"/tickets/{ticket_id}/solutions/generate")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert set(first.json()["referenced_cases"]) <= {"KB-TEST", "HIST-TEST"}
    assert first.json()["steps"]
    assert all("重启VPN客户端" not in step for step in first.json()["steps"])
    assert db_session.scalar(select(func.count(TicketAISolution.id))) == 2
    latest = client.get(f"/tickets/{ticket_id}/solutions/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == second.json()["id"]


def test_generate_without_analysis_returns_404_without_solution(
    client: TestClient,
    db_session: Session,
) -> None:
    ticket_id = create_current_ticket(client)

    response = client.post(f"/tickets/{ticket_id}/solutions/generate")

    assert response.status_code == 404
    assert db_session.scalar(select(func.count(TicketAISolution.id))) == 0


def test_generate_without_evidence_requires_human(client: TestClient) -> None:
    ticket_id = prepare_analyzed_ticket(client)

    response = client.post(f"/tickets/{ticket_id}/solutions/generate")

    assert response.status_code == 200
    assert response.json()["need_human"] is True
    assert response.json()["steps"] == []
    assert response.json()["referenced_cases"] == []


def test_provider_failure_does_not_persist_partial_solution(
    client: TestClient,
    db_session: Session,
) -> None:
    class FailingSolutionProvider:
        model_name = "failing-provider"

        def generate_solution(self, _context: object) -> TicketAISolutionDraft:
            raise AIServiceError("Solution provider unavailable")

    ticket_id = prepare_analyzed_ticket(client)
    seed_minimal_catalog(db_session)
    client.app.dependency_overrides[get_ai_service] = lambda: FailingSolutionProvider()
    try:
        response = client.post(f"/tickets/{ticket_id}/solutions/generate")
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert response.status_code == 502
    assert db_session.scalar(select(func.count(TicketAISolution.id))) == 0


def test_provider_cannot_cite_unretrieved_evidence(
    client: TestClient,
    db_session: Session,
) -> None:
    class FabricatingProvider:
        model_name = "fabricating-provider"

        def generate_solution(self, _context: object) -> TicketAISolutionDraft:
            return TicketAISolutionDraft(
                diagnosis="编造的结论",
                possible_causes=["未知"],
                steps=["执行未知操作"],
                referenced_cases=["KB-NOT-RETRIEVED"],
                need_human=False,
            )

    ticket_id = prepare_analyzed_ticket(client)
    seed_minimal_catalog(db_session)
    client.app.dependency_overrides[get_ai_service] = lambda: FabricatingProvider()
    try:
        response = client.post(f"/tickets/{ticket_id}/solutions/generate")
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert response.status_code == 502
    assert db_session.scalar(select(func.count(TicketAISolution.id))) == 0


def test_engineer_can_adopt_edited_solution_once(
    client: TestClient,
    db_session: Session,
) -> None:
    ticket_id = prepare_analyzed_ticket(client)
    solution = client.post(f"/tickets/{ticket_id}/solutions/generate").json()

    response = client.post(
        f"/tickets/{ticket_id}/solutions/{solution['id']}/review",
        json={
            "decision": "ADOPTED",
            "engineer_solution": "检查证书有效期后重新签发设备证书。",
        },
    )

    assert response.status_code == 200
    review = response.json()["review"]
    assert review["decision"] == "ADOPTED"
    assert review["engineer_solution"] == "检查证书有效期后重新签发设备证书。"
    assert db_session.scalar(select(func.count(TicketSolutionReview.id))) == 1
    duplicate = client.post(
        f"/tickets/{ticket_id}/solutions/{solution['id']}/review",
        json={"decision": "REJECTED", "rejection_reason": "不适用"},
    )
    assert duplicate.status_code == 409


def test_engineer_can_reject_solution(client: TestClient, db_session: Session) -> None:
    ticket_id = prepare_analyzed_ticket(client)
    solution = client.post(f"/tickets/{ticket_id}/solutions/generate").json()

    response = client.post(
        f"/tickets/{ticket_id}/solutions/{solution['id']}/review",
        json={"decision": "REJECTED", "rejection_reason": "现场症状与建议不符"},
    )

    assert response.status_code == 200
    review = db_session.scalar(select(TicketSolutionReview))
    assert review is not None
    assert review.decision is SolutionReviewDecision.REJECTED
    assert review.rejection_reason == "现场症状与建议不符"


def test_closed_ticket_rejects_generation_before_provider_call(client: TestClient) -> None:
    class TrackingProvider:
        model_name = "tracking-provider"
        called = False

        def generate_solution(self, _context: object) -> TicketAISolutionDraft:
            self.called = True
            raise AssertionError("provider must not be called")

    ticket_id = prepare_analyzed_ticket(client)
    assert (
        client.post(
            f"/tickets/{ticket_id}/close",
            json={
                "final_category": "网络/VPN",
                "final_priority": "P3",
                "resolution": "已恢复",
            },
        ).status_code
        == 200
    )
    provider = TrackingProvider()
    client.app.dependency_overrides[get_ai_service] = lambda: provider
    try:
        response = client.post(f"/tickets/{ticket_id}/solutions/generate")
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert response.status_code == 409
    assert provider.called is False


def test_adopted_review_requires_engineer_solution(client: TestClient) -> None:
    ticket_id = prepare_analyzed_ticket(client)
    solution = client.post(f"/tickets/{ticket_id}/solutions/generate").json()

    response = client.post(
        f"/tickets/{ticket_id}/solutions/{solution['id']}/review",
        json={"decision": "ADOPTED"},
    )

    assert response.status_code == 422


def test_latest_solution_returns_404_before_generation(client: TestClient) -> None:
    ticket_id = prepare_analyzed_ticket(client)
    response = client.get(f"/tickets/{ticket_id}/solutions/latest")
    assert response.status_code == 404


def test_review_solution_must_belong_to_ticket(client: TestClient) -> None:
    first_ticket = prepare_analyzed_ticket(client)
    second_ticket = prepare_analyzed_ticket(client)
    solution = client.post(f"/tickets/{first_ticket}/solutions/generate").json()

    response = client.post(
        f"/tickets/{second_ticket}/solutions/{solution['id']}/review",
        json={"decision": "REJECTED"},
    )

    assert response.status_code == 404


def test_solution_provider_receives_attempts_and_top_five_evidence(
    client: TestClient,
    db_session: Session,
) -> None:
    captured = SimpleNamespace(context=None)

    class CapturingProvider:
        model_name = "capturing-provider"

        def generate_solution(self, context: object) -> TicketAISolutionDraft:
            captured.context = context
            return TicketAISolutionDraft(
                diagnosis="需要人工核查",
                possible_causes=[],
                steps=[],
                referenced_cases=[],
                need_human=True,
            )

    ticket_id = prepare_analyzed_ticket(client)
    seed_minimal_catalog(db_session)
    client.app.dependency_overrides[get_ai_service] = lambda: CapturingProvider()
    try:
        response = client.post(f"/tickets/{ticket_id}/solutions/generate")
    finally:
        client.app.dependency_overrides.pop(get_ai_service, None)

    assert response.status_code == 200
    assert captured.context is not None
    assert captured.context.attempted_actions == ["重启客户端"]
    assert len(captured.context.evidence) <= 5
