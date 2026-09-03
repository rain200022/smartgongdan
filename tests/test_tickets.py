from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import EmbeddingServiceError
from app.models.ai_analysis import JudgeType, TicketJudgment
from app.models.ticket import Ticket, TicketStatus
from app.services.embedding_service import get_embedding_service


def create_ticket(client: TestClient) -> dict:
    response = client.post(
        "/tickets",
        json={
            "title": "VPN无法连接",
            "description": "认证服务器不可用，已经重启客户端",
            "user_category": "软件/VPN",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_ticket_lifecycle(client: TestClient, db_session: Session) -> None:
    ticket = create_ticket(client)
    assert ticket["status"] == "open"

    response = client.patch(
        f"/tickets/{ticket['id']}",
        json={"final_category": "网络/VPN", "final_priority": "P2", "status": "in_progress"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

    response = client.post(
        f"/tickets/{ticket['id']}/close",
        json={
            "final_category": "网络/VPN",
            "final_priority": "P2",
            "resolution": "重新签发设备证书后恢复连接",
        },
    )
    assert response.status_code == 200
    closed = response.json()
    assert closed["status"] == "closed"
    assert closed["resolution"] == "重新签发设备证书后恢复连接"
    assert closed["resolved_at"] is not None
    record = db_session.get(Ticket, ticket["id"])
    assert record is not None
    assert record.search_embedding is not None
    assert len(record.search_embedding) == 128
    assert record.search_embedding_model == "local-hash-v1"


def test_list_and_filter_tickets(client: TestClient) -> None:
    ticket = create_ticket(client)

    response = client.get("/tickets?status=open")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == ticket["id"]

    response = client.get("/tickets?status=closed")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_missing_ticket_returns_404(client: TestClient) -> None:
    response = client.get("/tickets/999")
    assert response.status_code == 404


def test_closed_ticket_cannot_be_edited_or_closed_twice(client: TestClient) -> None:
    ticket = create_ticket(client)
    close_payload = {
        "final_category": "网络/VPN",
        "final_priority": "P3",
        "resolution": "刷新证书缓存后恢复",
    }
    assert client.post(f"/tickets/{ticket['id']}/close", json=close_payload).status_code == 200

    assert (
        client.patch(f"/tickets/{ticket['id']}", json={"final_priority": "P1"}).status_code == 409
    )
    assert client.post(f"/tickets/{ticket['id']}/close", json=close_payload).status_code == 409


def test_close_requires_engineer_decision(client: TestClient) -> None:
    ticket = create_ticket(client)
    response = client.post(f"/tickets/{ticket['id']}/close", json={})
    assert response.status_code == 422


def test_embedding_failure_does_not_partially_close_ticket(
    client: TestClient, db_session: Session
) -> None:
    class FailingEmbeddingService:
        model_name = "failing"
        dimensions = 128

        def embed(self, _text: str) -> list[float]:
            raise EmbeddingServiceError("Embedding provider unavailable")

    ticket = create_ticket(client)
    client.app.dependency_overrides[get_embedding_service] = lambda: FailingEmbeddingService()
    try:
        response = client.post(
            f"/tickets/{ticket['id']}/close",
            json={
                "final_category": "网络/VPN",
                "final_priority": "P3",
                "resolution": "重新签发证书",
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_embedding_service, None)

    assert response.status_code == 502
    record = db_session.get(Ticket, ticket["id"])
    assert record is not None
    assert record.status is TicketStatus.OPEN
    assert record.resolution is None
    engineer_judgments = list(
        db_session.scalars(
            select(TicketJudgment).where(TicketJudgment.judge_type == JudgeType.ENGINEER)
        )
    )
    assert engineer_judgments == []


def test_create_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post(
        "/tickets",
        json={
            "title": "VPN无法连接",
            "description": "认证失败",
            "unexpected": "must not be silently ignored",
        },
    )

    assert response.status_code == 422
