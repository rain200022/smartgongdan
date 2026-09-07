from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, StaffUser, TicketVersion
from app.db.session import get_db
from app.models.ticket import TicketPriority, TicketStatus
from app.models.user import UserRole
from app.schemas.ticket import TicketClose, TicketCreate, TicketList, TicketRead, TicketUpdate
from app.schemas.ticket_event import TicketEventRead
from app.services import authorization_service, ticket_mutation_service, ticket_service
from app.services.embedding_service import EmbeddingService, get_embedding_service

router = APIRouter(prefix="/tickets", tags=["tickets"])
DbSession = Annotated[Session, Depends(get_db)]
StatusFilter = Annotated[TicketStatus | None, Query(alias="status")]
SearchFilter = Annotated[str | None, Query(min_length=1, max_length=200, pattern=r"\S")]
PriorityFilter = Annotated[TicketPriority | None, Query()]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
EmbeddingServiceDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: DbSession, user: CurrentUser) -> TicketRead:
    ticket = ticket_service.create_ticket(db, payload, requester_id=user.id)
    return TicketRead.model_validate(ticket)


@router.get("", response_model=TicketList)
def list_tickets(
    db: DbSession,
    user: CurrentUser,
    ticket_status: StatusFilter = None,
    limit: Limit = 20,
    offset: Offset = 0,
    q: SearchFilter = None,
    priority: PriorityFilter = None,
) -> TicketList:
    requester_id = user.id if user.role is UserRole.USER else None
    items, total, status_counts = ticket_service.list_tickets(
        db,
        status=ticket_status,
        requester_id=requester_id,
        limit=limit,
        offset=offset,
        q=q,
        priority=priority,
    )
    return TicketList(
        items=[TicketRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
        status_counts=status_counts,
    )


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: int, db: DbSession, user: CurrentUser) -> TicketRead:
    ticket = ticket_service.get_ticket(db, ticket_id)
    authorization_service.ensure_can_view_ticket(user, ticket)
    return TicketRead.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: DbSession,
    staff: StaffUser,
    version: TicketVersion = None,
) -> TicketRead:
    ticket = ticket_service.update_ticket(
        db, ticket_id, payload, actor=staff, expected_version=version
    )
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/close", response_model=TicketRead)
def close_ticket(
    ticket_id: int,
    payload: TicketClose,
    db: DbSession,
    embedding_service: EmbeddingServiceDependency,
    staff: StaffUser,
    version: TicketVersion = None,
) -> TicketRead:
    ticket = ticket_service.close_ticket(
        db,
        ticket_id,
        payload,
        embedding_service=embedding_service,
        actor=staff,
        expected_version=version,
    )
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/claim", response_model=TicketRead)
def claim_ticket(
    ticket_id: int, db: DbSession, staff: StaffUser, version: TicketVersion = None
) -> TicketRead:
    ticket = ticket_service.claim_ticket(db, ticket_id, actor=staff, expected_version=version)
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/release", response_model=TicketRead)
def release_ticket(
    ticket_id: int, db: DbSession, staff: StaffUser, version: TicketVersion = None
) -> TicketRead:
    ticket = ticket_service.release_ticket(db, ticket_id, actor=staff, expected_version=version)
    return TicketRead.model_validate(ticket)


@router.get("/{ticket_id}/events", response_model=list[TicketEventRead])
def list_events(
    ticket_id: int, db: DbSession, _staff: StaffUser, limit: Limit = 100, offset: Offset = 0
) -> list[TicketEventRead]:
    ticket_service.get_ticket(db, ticket_id)
    return [
        TicketEventRead.model_validate(item)
        for item in ticket_mutation_service.list_events(db, ticket_id, limit=limit, offset=offset)
    ]
