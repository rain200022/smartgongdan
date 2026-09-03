from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_analysis import TicketClassificationEvaluation, TicketJudgment


def create_ticket(client: TestClient, suffix: str) -> int:
    response = client.post(
        "/tickets",
        json={
            "title": f"VPN无法连接 {suffix}",
            "description": "连接VPN时提示认证服务器不可用",
            "user_category": "软件/VPN",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def analyze(client: TestClient, ticket_id: int) -> None:
    assert client.post(f"/tickets/{ticket_id}/analyze").status_code == 200


def confirm(client: TestClient, ticket_id: int, category: str, subcategory: str) -> dict:
    response = client.post(
        f"/tickets/{ticket_id}/classification/confirm",
        json={"category": category, "subcategory": subcategory},
    )
    assert response.status_code == 200
    return response.json()


def test_classification_tree_is_available_to_clients(client: TestClient) -> None:
    response = client.get("/classification-tree")
    assert response.status_code == 200
    assert response.json()["网络"] == ["VPN", "WiFi", "DNS", "网络不可用"]
    assert response.json()["其他"] == ["未分类"]


def test_confirmation_records_exact_agreement_and_history(client: TestClient) -> None:
    ticket_id = create_ticket(client, "exact")
    analyze(client, ticket_id)

    result = confirm(client, ticket_id, "网络", "VPN")

    assert result["final_category"] == "网络/VPN"
    assert result["engineer_judgment"]["judge_type"] == "ENGINEER"
    assert result["compared_ai_judgment"]["judge_type"] == "AI"
    assert result["evaluation"]["category_agreement"] is True
    assert result["evaluation"]["subcategory_agreement"] is True
    assert result["evaluation"]["agreement"] is True

    history = client.get(f"/tickets/{ticket_id}/judgments")
    assert history.status_code == 200
    assert [item["judge_type"] for item in history.json()] == ["USER", "AI", "ENGINEER"]


def test_confirmation_without_ai_is_kept_but_not_evaluated(client: TestClient) -> None:
    ticket_id = create_ticket(client, "human-only")

    result = confirm(client, ticket_id, "账号", "权限")

    assert result["compared_ai_judgment"] is None
    assert result["evaluation"] is None
    metrics = client.get("/metrics/classification").json()
    assert metrics == {
        "confirmed_tickets": 1,
        "evaluated_tickets": 0,
        "category_matches": 0,
        "exact_matches": 0,
        "category_agreement_rate": None,
        "exact_agreement_rate": None,
    }


def test_metrics_use_latest_confirmation_per_ticket(
    client: TestClient, db_session: Session
) -> None:
    exact_id = create_ticket(client, "exact")
    category_only_id = create_ticket(client, "category-only")
    no_ai_id = create_ticket(client, "no-ai")
    analyze(client, exact_id)
    analyze(client, category_only_id)

    confirm(client, exact_id, "网络", "VPN")
    first = confirm(client, category_only_id, "账号", "密码")
    assert first["evaluation"]["category_agreement"] is False
    second = confirm(client, category_only_id, "网络", "WiFi")
    assert second["evaluation"]["category_agreement"] is True
    assert second["evaluation"]["agreement"] is False
    confirm(client, no_ai_id, "其他", "未分类")

    metrics = client.get("/metrics/classification")
    assert metrics.status_code == 200
    assert metrics.json() == {
        "confirmed_tickets": 3,
        "evaluated_tickets": 2,
        "category_matches": 2,
        "exact_matches": 1,
        "category_agreement_rate": 1.0,
        "exact_agreement_rate": 0.5,
    }

    assert len(list(db_session.scalars(select(TicketClassificationEvaluation)))) == 3


def test_invalid_pair_is_rejected_and_closed_ticket_is_immutable(client: TestClient) -> None:
    ticket_id = create_ticket(client, "invalid")
    invalid = client.post(
        f"/tickets/{ticket_id}/classification/confirm",
        json={"category": "网络", "subcategory": "模型发明的分类"},
    )
    assert invalid.status_code == 422

    close = client.post(
        f"/tickets/{ticket_id}/close",
        json={
            "final_category": "网络/VPN",
            "final_priority": "P3",
            "resolution": "重新签发证书",
        },
    )
    assert close.status_code == 200
    after_close = client.post(
        f"/tickets/{ticket_id}/classification/confirm",
        json={"category": "网络", "subcategory": "WiFi"},
    )
    assert after_close.status_code == 409


def test_legacy_patch_classification_also_creates_engineer_judgment(
    client: TestClient, db_session: Session
) -> None:
    ticket_id = create_ticket(client, "patch")
    analyze(client, ticket_id)

    response = client.patch(
        f"/tickets/{ticket_id}",
        json={"final_category": "网络/VPN", "status": "in_progress"},
    )
    assert response.status_code == 200

    judgments = list(
        db_session.scalars(select(TicketJudgment).where(TicketJudgment.ticket_id == ticket_id))
    )
    evaluations = list(
        db_session.scalars(
            select(TicketClassificationEvaluation).where(
                TicketClassificationEvaluation.ticket_id == ticket_id
            )
        )
    )
    assert [item.judge_type.value for item in judgments] == ["USER", "AI", "ENGINEER"]
    assert len(evaluations) == 1
    assert evaluations[0].agreement is True
