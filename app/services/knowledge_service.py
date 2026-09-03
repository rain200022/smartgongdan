from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.ai_analysis import JudgeType, TicketJudgment
from app.models.knowledge import Knowledge
from app.models.ticket import Ticket, TicketStatus
from app.schemas.search import HistoricalTicketSeed, KnowledgeSeed
from app.services.embedding_service import EmbeddingService


@dataclass(frozen=True, slots=True)
class SeedResult:
    knowledge_created: int
    knowledge_updated: int
    history_created: int
    history_skipped: int


def seed_sample_catalog(
    db: Session,
    *,
    knowledge_items: list[KnowledgeSeed],
    historical_items: list[HistoricalTicketSeed],
    embedding_service: EmbeddingService,
) -> SeedResult:
    knowledge_vectors = [
        embedding_service.embed(_knowledge_text(knowledge_item))
        for knowledge_item in knowledge_items
    ]
    history_vectors = [
        embedding_service.embed(_history_text(history_item)) for history_item in historical_items
    ]
    existing_knowledge = {
        item.code: item
        for item in db.scalars(
            select(Knowledge).where(Knowledge.code.in_([item.code for item in knowledge_items]))
        )
    }
    existing_history = set(
        db.scalars(
            select(Ticket.external_reference).where(
                Ticket.external_reference.in_([item.reference for item in historical_items])
            )
        )
    )
    knowledge_created = 0
    knowledge_updated = 0
    for knowledge_item, vector in zip(knowledge_items, knowledge_vectors, strict=True):
        record = existing_knowledge.get(knowledge_item.code)
        if record is None:
            record = Knowledge(code=knowledge_item.code)
            db.add(record)
            knowledge_created += 1
        else:
            knowledge_updated += 1
        record.title = knowledge_item.title
        record.content = knowledge_item.content
        record.category = knowledge_item.category.value
        record.subcategory = knowledge_item.subcategory
        record.embedding = vector
        record.embedding_model = embedding_service.model_name
        record.is_active = True

    history_created = 0
    history_skipped = 0
    seed_time = utc_now()
    for index, (history_item, vector) in enumerate(
        zip(historical_items, history_vectors, strict=True), start=1
    ):
        if history_item.reference in existing_history:
            history_skipped += 1
            continue
        resolved_at = seed_time - timedelta(days=index)
        ticket = Ticket(
            external_reference=history_item.reference,
            title=history_item.title,
            description=history_item.description,
            final_category=f"{history_item.category.value}/{history_item.subcategory}",
            final_priority=history_item.priority,
            resolution=history_item.resolution,
            status=TicketStatus.CLOSED,
            search_embedding=vector,
            search_embedding_model=embedding_service.model_name,
            created_at=resolved_at - timedelta(hours=4),
            updated_at=resolved_at,
            resolved_at=resolved_at,
        )
        db.add(ticket)
        db.flush()
        db.add(
            TicketJudgment(
                ticket_id=ticket.id,
                judge_type=JudgeType.ENGINEER,
                category=history_item.category.value,
                subcategory=history_item.subcategory,
            )
        )
        history_created += 1
    db.commit()
    return SeedResult(
        knowledge_created=knowledge_created,
        knowledge_updated=knowledge_updated,
        history_created=history_created,
        history_skipped=history_skipped,
    )


def _knowledge_text(item: KnowledgeSeed) -> str:
    return "\n".join((item.title, item.content, item.category.value, item.subcategory))


def _history_text(item: HistoricalTicketSeed) -> str:
    return "\n".join(
        (
            item.title,
            item.description,
            item.category.value,
            item.subcategory,
            item.resolution,
        )
    )
