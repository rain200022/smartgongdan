from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import DbSession, StaffUser, TicketVersion
from app.schemas.solution import TicketAISolutionRead, TicketSolutionReviewCreate
from app.services import solution_service
from app.services.ai_service import AIService, get_ai_service
from app.services.embedding_service import EmbeddingService, get_embedding_service

router = APIRouter(prefix="/tickets", tags=["AI solutions"])
AIServiceDependency = Annotated[AIService, Depends(get_ai_service)]
EmbeddingServiceDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]


@router.post("/{ticket_id}/solutions/generate", response_model=TicketAISolutionRead)
def generate_solution(
    ticket_id: int,
    db: DbSession,
    ai_service: AIServiceDependency,
    embedding_service: EmbeddingServiceDependency,
    staff: StaffUser,
    version: TicketVersion = None,
) -> TicketAISolutionRead:
    record = solution_service.generate_solution(
        db,
        ticket_id=ticket_id,
        ai_service=ai_service,
        embedding_service=embedding_service,
        actor=staff,
        expected_version=version,
    )
    return TicketAISolutionRead.model_validate(record)


@router.get("/{ticket_id}/solutions/latest", response_model=TicketAISolutionRead)
def get_latest_solution(
    ticket_id: int,
    db: DbSession,
    _staff: StaffUser,
) -> TicketAISolutionRead:
    record = solution_service.get_latest_solution(db, ticket_id)
    return TicketAISolutionRead.model_validate(record)


@router.post(
    "/{ticket_id}/solutions/{solution_id}/review",
    response_model=TicketAISolutionRead,
)
def review_solution(
    ticket_id: int,
    solution_id: int,
    payload: TicketSolutionReviewCreate,
    db: DbSession,
    staff: StaffUser,
    version: TicketVersion = None,
) -> TicketAISolutionRead:
    record = solution_service.review_solution(
        db,
        ticket_id=ticket_id,
        solution_id=solution_id,
        reviewer=staff,
        payload=payload,
        expected_version=version,
    )
    return TicketAISolutionRead.model_validate(record)
