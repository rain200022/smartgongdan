from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ticket import TicketStatus
from app.schemas.ticket import TicketClose, TicketCreate, TicketList, TicketRead, TicketUpdate
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])
DbSession = Annotated[Session, Depends(get_db)]
StatusFilter = Annotated[TicketStatus | None, Query(alias="status")]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: DbSession) -> TicketRead:
    return ticket_service.create_ticket(db, payload)


@router.get("", response_model=TicketList)
def list_tickets(
    db: DbSession,
    ticket_status: StatusFilter = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> TicketList:
    items, total = ticket_service.list_tickets(db, status=ticket_status, limit=limit, offset=offset)
    return TicketList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: int, db: DbSession) -> TicketRead:
    return ticket_service.get_ticket(db, ticket_id)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(ticket_id: int, payload: TicketUpdate, db: DbSession) -> TicketRead:
    return ticket_service.update_ticket(db, ticket_id, payload)


@router.post("/{ticket_id}/close", response_model=TicketRead)
def close_ticket(ticket_id: int, payload: TicketClose, db: DbSession) -> TicketRead:
    return ticket_service.close_ticket(db, ticket_id, payload)
