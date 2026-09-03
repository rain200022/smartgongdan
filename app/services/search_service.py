import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.knowledge import Knowledge
from app.models.ticket import Ticket, TicketStatus
from app.schemas.search import SimilarResult
from app.services import ai_analysis_service, ticket_service
from app.services.embedding_service import EmbeddingService

SearchSource = Literal["knowledge", "historical_ticket"]
RRF_K = 60
STOP_TERMS = {"用户", "问题", "公司", "今天", "已经", "进行", "出现", "当前"}


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    key: str
    source_type: SearchSource
    source_id: int
    reference: str
    title: str
    excerpt: str
    category: str
    subcategory: str
    resolution: str | None
    created_at: datetime
    keyword_score: float | None = None
    semantic_score: float | None = None


@dataclass(slots=True)
class _MergedCandidate:
    candidate: SearchCandidate
    reciprocal_rank: float = 0.0
    keyword_score: float | None = None
    semantic_score: float | None = None
    keyword_match: bool = False
    semantic_match: bool = False


def search_similar(
    db: Session,
    *,
    ticket_id: int,
    embedding_service: EmbeddingService,
    limit: int,
) -> list[SimilarResult]:
    ticket = ticket_service.get_ticket(db, ticket_id)
    query_text = build_query_text(db, ticket)
    return search_similar_text(
        db,
        query_text=query_text,
        embedding_service=embedding_service,
        limit=limit,
        exclude_ticket_id=ticket.id,
    )


def search_similar_text(
    db: Session,
    *,
    query_text: str,
    embedding_service: EmbeddingService,
    limit: int,
    exclude_ticket_id: int | None = None,
) -> list[SimilarResult]:
    query_vector = embedding_service.embed(query_text)
    candidate_limit = max(10, limit * 4)

    keyword_candidates = _keyword_candidates(
        db,
        exclude_ticket_id=exclude_ticket_id,
        terms=extract_search_terms(query_text),
        limit=candidate_limit,
    )
    vector_candidates = _vector_candidates(
        db,
        exclude_ticket_id=exclude_ticket_id,
        query_vector=query_vector,
        limit=candidate_limit,
    )
    return merge_ranked_results(keyword_candidates, vector_candidates, limit=limit)


def build_query_text(db: Session, ticket: Ticket) -> str:
    parts = [ticket.title, ticket.description]
    analysis = ai_analysis_service.find_latest_analysis(db, ticket.id)
    if analysis is not None:
        parts.extend(
            value
            for value in (
                analysis.summary,
                analysis.category,
                analysis.subcategory,
                analysis.device,
                analysis.symptom,
                analysis.error_message,
            )
            if value
        )
    return "\n".join(parts)


def extract_search_terms(text: str) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", text.lower()):
        if len(token) >= 2 and token not in terms:
            terms.append(token)
    for sequence in re.findall(r"[\u4e00-\u9fff]+", text):
        candidates = [sequence] if len(sequence) <= 6 else []
        candidates.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
        for token in candidates:
            if token not in STOP_TERMS and token not in terms:
                terms.append(token)
    return terms[:24]


def merge_ranked_results(
    keyword_candidates: Sequence[SearchCandidate],
    vector_candidates: Sequence[SearchCandidate],
    *,
    limit: int,
) -> list[SimilarResult]:
    merged: dict[str, _MergedCandidate] = {}
    for is_keyword, candidates in ((True, keyword_candidates), (False, vector_candidates)):
        for rank, candidate in enumerate(candidates, start=1):
            item = merged.setdefault(candidate.key, _MergedCandidate(candidate=candidate))
            item.reciprocal_rank += 1 / (RRF_K + rank)
            if is_keyword:
                item.keyword_match = True
                item.keyword_score = candidate.keyword_score
            else:
                item.semantic_match = True
                item.semantic_score = candidate.semantic_score

    maximum_rrf = 2 / (RRF_K + 1)
    ranked = sorted(
        merged.values(),
        key=lambda item: (
            item.reciprocal_rank,
            item.semantic_score or 0,
            item.keyword_score or 0,
        ),
        reverse=True,
    )[:limit]
    return [
        SimilarResult(
            source_type=item.candidate.source_type,
            source_id=item.candidate.source_id,
            reference=item.candidate.reference,
            title=item.candidate.title,
            excerpt=item.candidate.excerpt,
            category=item.candidate.category,
            subcategory=item.candidate.subcategory,
            resolution=item.candidate.resolution,
            keyword_score=item.keyword_score,
            semantic_score=item.semantic_score,
            combined_score=round(min(item.reciprocal_rank / maximum_rrf, 1.0), 4),
            match_reasons=[
                label
                for matched, label in (
                    (item.keyword_match, "关键词匹配"),
                    (item.semantic_match, "语义相似"),
                )
                if matched
            ],
            created_at=item.candidate.created_at,
        )
        for item in ranked
    ]


def _keyword_candidates(
    db: Session,
    *,
    exclude_ticket_id: int | None,
    terms: Sequence[str],
    limit: int,
) -> list[SearchCandidate]:
    if not terms:
        return []
    knowledge_text = Knowledge.title + " " + Knowledge.content
    ticket_text = (
        Ticket.title + " " + Ticket.description + " " + func.coalesce(Ticket.resolution, "")
    )
    knowledge_conditions = [
        knowledge_text.ilike(f"%{_escape_like(term)}%", escape="\\") for term in terms
    ]
    ticket_conditions = [
        ticket_text.ilike(f"%{_escape_like(term)}%", escape="\\") for term in terms
    ]
    knowledge = list(
        db.scalars(
            select(Knowledge)
            .where(Knowledge.is_active.is_(True), or_(*knowledge_conditions))
            .limit(limit * 2)
        )
    )
    history_filters = [
        Ticket.status == TicketStatus.CLOSED,
        Ticket.resolution.is_not(None),
        or_(*ticket_conditions),
    ]
    if exclude_ticket_id is not None:
        history_filters.append(Ticket.id != exclude_ticket_id)
    history = list(db.scalars(select(Ticket).where(*history_filters).limit(limit * 2)))
    candidates = [
        _knowledge_candidate(item, keyword_score=_keyword_score(item.title, item.content, terms))
        for item in knowledge
    ]
    candidates.extend(
        _ticket_candidate(
            item,
            keyword_score=_keyword_score(
                item.title, f"{item.description} {item.resolution}", terms
            ),
        )
        for item in history
    )
    return sorted(candidates, key=lambda item: item.keyword_score or 0, reverse=True)[:limit]


def _vector_candidates(
    db: Session,
    *,
    exclude_ticket_id: int | None,
    query_vector: list[float],
    limit: int,
) -> list[SearchCandidate]:
    if db.get_bind().dialect.name == "postgresql":
        return _postgres_vector_candidates(
            db,
            exclude_ticket_id=exclude_ticket_id,
            query_vector=query_vector,
            limit=limit,
        )
    return _python_vector_candidates(
        db,
        exclude_ticket_id=exclude_ticket_id,
        query_vector=query_vector,
        limit=limit,
    )


def _postgres_vector_candidates(
    db: Session,
    *,
    exclude_ticket_id: int | None,
    query_vector: list[float],
    limit: int,
) -> list[SearchCandidate]:
    knowledge_distance = Knowledge.embedding.cosine_distance(query_vector)
    history_distance = Ticket.search_embedding.cosine_distance(query_vector)
    knowledge_rows = db.execute(
        select(Knowledge, knowledge_distance.label("distance"))
        .where(Knowledge.is_active.is_(True))
        .order_by(knowledge_distance)
        .limit(limit)
    ).all()
    history_filters = [
        Ticket.status == TicketStatus.CLOSED,
        Ticket.resolution.is_not(None),
        Ticket.search_embedding.is_not(None),
    ]
    if exclude_ticket_id is not None:
        history_filters.append(Ticket.id != exclude_ticket_id)
    history_rows = db.execute(
        select(Ticket, history_distance.label("distance"))
        .where(*history_filters)
        .order_by(history_distance)
        .limit(limit)
    ).all()
    candidates = [
        _knowledge_candidate(item, semantic_score=_semantic_score(distance))
        for item, distance in knowledge_rows
    ]
    candidates.extend(
        _ticket_candidate(item, semantic_score=_semantic_score(distance))
        for item, distance in history_rows
    )
    return sorted(candidates, key=lambda item: item.semantic_score or 0, reverse=True)[:limit]


def _python_vector_candidates(
    db: Session,
    *,
    exclude_ticket_id: int | None,
    query_vector: list[float],
    limit: int,
) -> list[SearchCandidate]:
    knowledge = list(db.scalars(select(Knowledge).where(Knowledge.is_active.is_(True))))
    history_filters = [
        Ticket.status == TicketStatus.CLOSED,
        Ticket.resolution.is_not(None),
        Ticket.search_embedding.is_not(None),
    ]
    if exclude_ticket_id is not None:
        history_filters.append(Ticket.id != exclude_ticket_id)
    history = list(db.scalars(select(Ticket).where(*history_filters)))
    candidates = [
        _knowledge_candidate(
            item,
            semantic_score=_cosine_similarity(query_vector, list(item.embedding)),
        )
        for item in knowledge
    ]
    candidates.extend(
        _ticket_candidate(
            item,
            semantic_score=_cosine_similarity(
                query_vector,
                list(item.search_embedding) if item.search_embedding is not None else [],
            ),
        )
        for item in history
    )
    return sorted(candidates, key=lambda item: item.semantic_score or 0, reverse=True)[:limit]


def _knowledge_candidate(
    item: Knowledge,
    *,
    keyword_score: float | None = None,
    semantic_score: float | None = None,
) -> SearchCandidate:
    return SearchCandidate(
        key=f"knowledge:{item.id}",
        source_type="knowledge",
        source_id=item.id,
        reference=item.code,
        title=item.title,
        excerpt=_excerpt(item.content),
        category=item.category,
        subcategory=item.subcategory,
        resolution=None,
        created_at=item.created_at,
        keyword_score=keyword_score,
        semantic_score=semantic_score,
    )


def _ticket_candidate(
    item: Ticket,
    *,
    keyword_score: float | None = None,
    semantic_score: float | None = None,
) -> SearchCandidate:
    category, _, subcategory = (item.final_category or "其他/未分类").partition("/")
    return SearchCandidate(
        key=f"historical_ticket:{item.id}",
        source_type="historical_ticket",
        source_id=item.id,
        reference=item.external_reference or f"INC-{item.id:04d}",
        title=item.title,
        excerpt=_excerpt(item.description),
        category=category,
        subcategory=subcategory or "未分类",
        resolution=item.resolution,
        created_at=item.created_at,
        keyword_score=keyword_score,
        semantic_score=semantic_score,
    )


def _keyword_score(title: str, body: str, terms: Sequence[str]) -> float:
    lowered_title = title.lower()
    lowered_body = body.lower()
    score = sum(
        2 if term in lowered_title else 1
        for term in terms
        if term in lowered_body or term in lowered_title
    )
    return round(min(score / max(len(terms), 1), 1.0), 4)


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return round(max(0.0, min(dot / (left_norm * right_norm), 1.0)), 4)


def _semantic_score(distance: float) -> float:
    return round(max(0.0, min(1.0 - float(distance), 1.0)), 4)


def _excerpt(value: str, limit: int = 180) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1]}…"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
