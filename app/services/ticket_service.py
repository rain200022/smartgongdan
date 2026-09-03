from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.classification import split_classification
from app.core.exceptions import InvalidTicketTransitionError, TicketNotFoundError
from app.core.time import utc_now
from app.models.ai_analysis import JudgeType, TicketJudgment
from app.models.ticket import Ticket, TicketStatus
from app.schemas.evaluation import ClassificationConfirmation
from app.schemas.ticket import TicketClose, TicketCreate, TicketUpdate
from app.services import evaluation_service
from app.services.embedding_service import EmbeddingService


def create_ticket(db: Session, payload: TicketCreate, *, requester_id: int) -> Ticket:
    ticket = Ticket(**payload.model_dump(), requester_id=requester_id)
    db.add(ticket)
    db.flush()
    if payload.user_category:
        category, subcategory = split_classification(payload.user_category)
        db.add(
            TicketJudgment(
                ticket_id=ticket.id,
                judge_type=JudgeType.USER,
                category=category,
                subcategory=subcategory,
            )
        )
    db.commit()
    db.refresh(ticket)
    return ticket


def list_tickets(
    db: Session,
    *,
    status: TicketStatus | None,
    requester_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[Ticket], int]:
    filters: list[ColumnElement[bool]] = [Ticket.external_reference.is_(None)]
    if status:
        filters.append(Ticket.status == status)
    if requester_id is not None:
        filters.append(Ticket.requester_id == requester_id)
    total = db.scalar(select(func.count(Ticket.id)).where(*filters)) or 0
    statement = (
        select(Ticket)
        .where(*filters)
        .order_by(Ticket.created_at.desc(), Ticket.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement)), total


def get_ticket(db: Session, ticket_id: int) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise TicketNotFoundError(ticket_id)
    return ticket


def update_ticket(db: Session, ticket_id: int, payload: TicketUpdate) -> Ticket:
    ticket = get_ticket(db, ticket_id)
    ensure_ticket_editable(ticket)

    changes = payload.model_dump(exclude_unset=True)
    final_category = changes.pop("final_category", None)
    requested_status = changes.get("status")
    if requested_status is TicketStatus.CLOSED:
        raise InvalidTicketTransitionError("Use the close endpoint to close a ticket")

    for field, value in changes.items():
        setattr(ticket, field, value)
    if final_category is not None:
        ensure_engineer_classification(db, ticket, final_category)
    db.commit()
    db.refresh(ticket)
    return ticket


def close_ticket(
    db: Session,
    ticket_id: int,
    payload: TicketClose,
    *,
    embedding_service: EmbeddingService,
) -> Ticket:
    ticket = get_ticket(db, ticket_id)
    ensure_ticket_editable(ticket)

    search_text = "\n".join(
        (ticket.title, ticket.description, payload.final_category, payload.resolution)
    )
    search_embedding = embedding_service.embed(search_text)
    ensure_engineer_classification(db, ticket, payload.final_category)
    ticket.final_priority = payload.final_priority
    ticket.resolution = payload.resolution
    ticket.search_embedding = search_embedding
    ticket.search_embedding_model = embedding_service.model_name
    ticket.status = TicketStatus.CLOSED
    ticket.resolved_at = utc_now()
    db.commit()
    db.refresh(ticket)
    return ticket


def ensure_ticket_editable(ticket: Ticket) -> None:
    if ticket.status is TicketStatus.CLOSED:
        raise InvalidTicketTransitionError("Closed tickets cannot be edited")


def ensure_engineer_classification(db: Session, ticket: Ticket, value: str) -> None:
    category, subcategory = split_classification(value)
    latest = evaluation_service.get_latest_judgment(db, ticket.id, JudgeType.ENGINEER)
    if latest is not None and latest.category == category and latest.subcategory == subcategory:
        ticket.final_category = value
        return
    evaluation_service.stage_classification_confirmation(
        db,
        ticket=ticket,
        payload=ClassificationConfirmation(category=category, subcategory=subcategory),
    )
