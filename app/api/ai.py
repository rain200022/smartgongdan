from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import StaffUser
from app.db.session import get_db
from app.schemas.ai_analysis import TicketAIAnalysisRead
from app.services import ai_analysis_service, ticket_service
from app.services.ai_service import AIService, get_ai_service

router = APIRouter(prefix="/tickets", tags=["AI analysis"])
DbSession = Annotated[Session, Depends(get_db)]
AIServiceDependency = Annotated[AIService, Depends(get_ai_service)]


@router.post("/{ticket_id}/analyze", response_model=TicketAIAnalysisRead)
def analyze_ticket(
    ticket_id: int, db: DbSession, ai_service: AIServiceDependency, _staff: StaffUser
) -> TicketAIAnalysisRead:
    record = ai_analysis_service.analyze_ticket(
        db,
        ticket_id=ticket_id,
        ai_service=ai_service,
    )
    return TicketAIAnalysisRead.model_validate(record)


@router.get("/{ticket_id}/analysis/latest", response_model=TicketAIAnalysisRead)
def get_latest_analysis(ticket_id: int, db: DbSession, _staff: StaffUser) -> TicketAIAnalysisRead:
    ticket_service.get_ticket(db, ticket_id)
    record = ai_analysis_service.get_latest_analysis(db, ticket_id)
    return TicketAIAnalysisRead.model_validate(record)
