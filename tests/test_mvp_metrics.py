from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.evaluation import SearchEvaluationRun
from app.schemas.evaluation import (
    SearchBenchmarkCase,
    SearchBenchmarkDataset,
)
from app.services import evaluation_service

from .test_search import create_current_ticket, seed_minimal_catalog


def test_mvp_metrics_empty_state_has_explicit_denominators(client: TestClient) -> None:
    response = client.get("/metrics/mvp")

    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["evaluated_tickets"] == 0
    assert body["classification"]["exact_agreement_rate"] is None
    assert body["solutions"] == {
        "generated_suggestions": 0,
        "reviewed_suggestions": 0,
        "pending_suggestions": 0,
        "adopted_suggestions": 0,
        "rejected_suggestions": 0,
        "adoption_rate": None,
        "average_review_minutes": None,
        "rejection_categories": [],
    }
    assert body["handling_time"] == {
        "resolved_tickets": 0,
        "average_resolution_minutes": None,
        "median_resolution_minutes": None,
    }
    assert body["latest_search_evaluation"] is None


def test_mvp_metrics_aggregate_classification_solution_and_handling(
    client: TestClient,
    db_session: Session,
) -> None:
    adopted_ticket = create_current_ticket(client)
    rejected_ticket = create_current_ticket(client)
    for ticket_id in (adopted_ticket, rejected_ticket):
        assert client.post(f"/tickets/{ticket_id}/analyze").status_code == 200

    adopted = client.post(f"/tickets/{adopted_ticket}/solutions/generate").json()
    rejected = client.post(f"/tickets/{rejected_ticket}/solutions/generate").json()
    assert (
        client.post(
            f"/tickets/{adopted_ticket}/solutions/{adopted['id']}/review",
            json={
                "decision": "ADOPTED",
                "engineer_solution": "工程师核验后的最终步骤",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/tickets/{rejected_ticket}/solutions/{rejected['id']}/review",
            json={
                "decision": "REJECTED",
                "rejection_category": "EVIDENCE_MISMATCH",
                "rejection_reason": "现场现象与引用案例不一致",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/tickets/{adopted_ticket}/classification/confirm",
            json={"category": "网络", "subcategory": "VPN"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/tickets/{adopted_ticket}/close",
            json={
                "final_category": "网络/VPN",
                "final_priority": "P3",
                "resolution": "工程师核验后的最终步骤",
            },
        ).status_code
        == 200
    )
    seed_minimal_catalog(db_session)

    response = client.get("/metrics/mvp")

    assert response.status_code == 200
    body = response.json()
    assert body["classification"]["exact_agreement_rate"] == 1.0
    assert body["solutions"]["generated_suggestions"] == 2
    assert body["solutions"]["reviewed_suggestions"] == 2
    assert body["solutions"]["adoption_rate"] == 0.5
    assert body["solutions"]["rejection_categories"] == [
        {"category": "EVIDENCE_MISMATCH", "count": 1}
    ]
    assert body["solutions"]["average_review_minutes"] is not None
    assert body["handling_time"]["resolved_tickets"] == 1
    assert body["handling_time"]["average_resolution_minutes"] is not None


def test_search_evaluation_run_is_reproducible_and_append_only(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    seed_minimal_catalog(db_session)
    dataset = SearchBenchmarkDataset(
        name="test-search-benchmark",
        version="v1",
        cases=[
            SearchBenchmarkCase(
                id="CASE-1",
                title="VPN认证失败",
                description="检查设备证书有效期",
                expected_references=["KB-TEST"],
            )
        ],
    )
    monkeypatch.setattr(evaluation_service, "load_search_benchmark", lambda: dataset)

    first = client.post("/metrics/search/run")
    second = client.post("/metrics/search/run")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["recall_at_5"] == 1.0
    assert first.json()["details"][0]["matched_references"] == ["KB-TEST"]
    assert first.json()["id"] != second.json()["id"]
    assert db_session.scalar(select(func.count(SearchEvaluationRun.id))) == 2
    overview = client.get("/metrics/mvp").json()
    assert overview["latest_search_evaluation"]["id"] == second.json()["id"]


def test_versioned_search_benchmark_is_valid() -> None:
    dataset = evaluation_service.load_search_benchmark()

    assert dataset.name == "smartgongdan-search-benchmark"
    assert dataset.version == "2026-08-30-v1"
    assert len(dataset.cases) == 14
    assert all(case.expected_references for case in dataset.cases)
