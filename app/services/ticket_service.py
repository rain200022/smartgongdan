from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ticket import Ticket, TicketStatus
from app.schemas.ticket import TicketClose, TicketCreate, TicketUpdate


class TicketNotFoundError(Exception):
    pass


class InvalidTicketTransitionError(Exception):
    pass


def create_ticket(db: Session, payload: TicketCreate) -> Ticket:
    ticket = Ticket(**payload.model_dump())
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def list_tickets(
    db: Session, *, status: TicketStatus | None, limit: int, offset: int
) -> tuple[list[Ticket], int]:
    filters = [Ticket.status == status] if status else []
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
    if ticket.status is TicketStatus.CLOSED:
        raise InvalidTicketTransitionError("Closed tickets cannot be edited")

    changes = payload.model_dump(exclude_unset=True)
    requested_status = changes.get("status")
    if requested_status is TicketStatus.CLOSED:
        raise InvalidTicketTransitionError("Use the close endpoint to close a ticket")

    for field, value in changes.items():
        setattr(ticket, field, value)
    db.commit()
    db.refresh(ticket)
    return ticket


def close_ticket(db: Session, ticket_id: int, payload: TicketClose) -> Ticket:
    ticket = get_ticket(db, ticket_id)
    if ticket.status is TicketStatus.CLOSED:
        raise InvalidTicketTransitionError("Ticket is already closed")

    ticket.final_category = payload.final_category
    ticket.final_priority = payload.final_priority
    ticket.resolution = payload.resolution
    ticket.status = TicketStatus.CLOSED
    ticket.resolved_at = datetime.now(UTC)
    db.commit()
    db.refresh(ticket)
    return ticket
