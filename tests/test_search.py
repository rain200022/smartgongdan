import math
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import EmbeddingServiceError
from app.core.time import utc_now
from app.models.knowledge import Knowledge
from app.models.ticket import Ticket
from app.models.user import UserRole
from app.schemas.auth import UserCreate
from app.schemas.search import HistoricalTicketSeed, KnowledgeSeed
from app.services import auth_service, knowledge_service, search_service
from app.services.embedding_service import (
    LocalEmbeddingService,
    get_embedding_service,
)


def create_current_ticket(client: TestClient) -> int:
    response = client.post(
        "/tickets",
        json={
            "title": "VPN认证服务器不可用",
            "description": "公司笔记本无法连接VPN，已经重启客户端",
            "user_category": "网络/VPN",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def seed_minimal_catalog(db: Session) -> knowledge_service.SeedResult:
    return knowledge_service.seed_sample_catalog(
        db,
        knowledge_items=[
            KnowledgeSeed(
                code="KB-TEST",
                title="VPN认证失败处理",
                content="检查设备证书有效期，重新签发企业证书后连接VPN。",
                category="网络",
                subcategory="VPN",
            )
        ],
        historical_items=[
            HistoricalTicketSeed(
                reference="HIST-TEST",
                title="VPN认证服务器不可用",
                description="设备证书过期导致认证失败。",
                category="网络",
                subcategory="VPN",
                priority="P2",
                resolution="重新签发设备证书并重启VPN客户端。",
            )
        ],
        embedding_service=LocalEmbeddingService(),
    )


def test_similar_endpoint_merges_knowledge_and_history(
    client: TestClient, db_session: Session
) -> None:
    ticket_id = create_current_ticket(client)
    seed_minimal_catalog(db_session)

    response = client.get(f"/tickets/{ticket_id}/similar?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert body["query_model"] == "local-hash-v1"
    assert {item["source_type"] for item in body["items"]} == {
        "knowledge",
        "historical_ticket",
    }
    assert body["items"][0]["match_reasons"] == ["关键词匹配", "语义相似"]
    assert all(0 <= item["combined_score"] <= 1 for item in body["items"])


def test_search_missing_ticket_returns_404(client: TestClient) -> None:
    assert client.get("/tickets/999/similar").status_code == 404


def test_search_requires_staff_role(client: TestClient, db_session: Session) -> None:
    user = auth_service.create_user(
        db_session,
        UserCreate(
            username="search-user",
            display_name="检索普通用户",
            password="Search-User-Password-2026!",
            role=UserRole.USER,
        ),
    )
    client.post("/auth/logout")
    login = client.post(
        "/auth/login",
        json={"username": user.username, "password": "Search-User-Password-2026!"},
    )
    assert login.status_code == 200
    ticket_id = create_current_ticket(client)

    assert client.get(f"/tickets/{ticket_id}/similar").status_code == 403


def test_embedding_failure_is_translated_without_writes(
    client: TestClient, db_session: Session
) -> None:
    class FailingEmbeddingService:
        model_name = "failing"
        dimensions = 128

        def embed(self, _text: str) -> list[float]:
            raise EmbeddingServiceError("Embedding provider unavailable")

    ticket_id = create_current_ticket(client)
    client.app.dependency_overrides[get_embedding_service] = lambda: FailingEmbeddingService()
    try:
        response = client.get(f"/tickets/{ticket_id}/similar")
    finally:
        client.app.dependency_overrides.pop(get_embedding_service, None)

    assert response.status_code == 502
    assert response.json() == {"detail": "Embedding provider unavailable"}
    assert db_session.scalar(select(func.count(Knowledge.id))) == 0


def test_seed_catalog_is_idempotent_for_history_and_refreshes_knowledge(
    client: TestClient,
    db_session: Session,
) -> None:
    first = seed_minimal_catalog(db_session)
    second = seed_minimal_catalog(db_session)

    assert first.knowledge_created == 1
    assert first.history_created == 1
    assert second.knowledge_updated == 1
    assert second.history_skipped == 1
    assert db_session.scalar(select(func.count(Knowledge.id))) == 1
    assert db_session.scalar(select(func.count(Ticket.external_reference))) == 1
    queue = client.get("/tickets?status=closed")
    assert queue.status_code == 200
    assert queue.json()["total"] == 0


def test_local_embedding_is_stable_normalized_and_rejects_empty_text() -> None:
    service = LocalEmbeddingService()
    first = service.embed("VPN 认证失败")
    second = service.embed("VPN 认证失败")

    assert first == second
    assert len(first) == 128
    assert math.sqrt(sum(value * value for value in first)) == pytest.approx(1.0)
    with pytest.raises(EmbeddingServiceError):
        service.embed("   ")


def test_merge_ranked_results_deduplicates_sources() -> None:
    now = utc_now()
    shared = search_service.SearchCandidate(
        key="knowledge:1",
        source_type="knowledge",
        source_id=1,
        reference="KB001",
        title="VPN认证失败",
        excerpt="证书处理",
        category="网络",
        subcategory="VPN",
        resolution=None,
        created_at=now,
        keyword_score=0.9,
    )
    semantic = replace(shared, keyword_score=None, semantic_score=0.8)
    result = search_service.merge_ranked_results([shared], [semantic], limit=5)

    assert len(result) == 1
    assert result[0].match_reasons == ["关键词匹配", "语义相似"]
    assert result[0].combined_score == 1.0


def test_search_seed_schema_rejects_invalid_classification() -> None:
    with pytest.raises(ValidationError):
        KnowledgeSeed(
            code="BAD",
            title="错误分类",
            content="测试",
            category="网络",
            subcategory="不存在",
        )
    with pytest.raises(ValidationError):
        HistoricalTicketSeed(
            reference="BAD",
            title="错误分类",
            description="测试",
            category="账号",
            subcategory="不存在",
            priority="P3",
            resolution="测试",
        )


def test_get_embedding_service_uses_local_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.embedding_service as module

    module.get_embedding_service.cache_clear()
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(
            embedding_provider="local",
            embedding_model="test-hash",
            embedding_dimensions=128,
        ),
    )
    service = module.get_embedding_service()
    try:
        assert service.model_name == "test-hash"
        assert len(service.embed("测试")) == 128
    finally:
        module.get_embedding_service.cache_clear()
