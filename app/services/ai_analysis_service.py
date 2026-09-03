from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AIAnalysisNotFoundError
from app.models.ai_analysis import JudgeType, TicketAIAnalysisRecord, TicketJudgment
from app.models.ticket import Ticket
from app.schemas.ai_analysis import TicketAIAnalysis
from app.services import priority_service, ticket_service
from app.services.ai_service import AIService


def analyze_ticket(
    db: Session,
    *,
    ticket_id: int,
    ai_service: AIService,
) -> TicketAIAnalysisRecord:
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket_service.ensure_ticket_editable(ticket)
    analysis = ai_service.analyze_ticket(ticket)
    record = stage_analysis(
        db,
        ticket=ticket,
        analysis=analysis,
        model_name=ai_service.model_name,
    )
    db.commit()
    db.refresh(record)
    return record


def stage_analysis(
    db: Session,
    *,
    ticket: Ticket,
    analysis: TicketAIAnalysis,
    model_name: str,
) -> TicketAIAnalysisRecord:
    assessment = priority_service.calculate_priority(
        analysis.impact,
        analysis.urgency,
        analysis.affected_scope,
    )
    values = analysis.model_dump(mode="json")
    record = TicketAIAnalysisRecord(
        ticket_id=ticket.id,
        model_name=model_name,
        impact_score=assessment.impact_score,
        urgency_score=assessment.urgency_score,
        scope_score=assessment.scope_score,
        priority_score=assessment.score,
        calculated_priority=assessment.priority,
        **values,
    )
    judgment = TicketJudgment(
        ticket_id=ticket.id,
        judge_type=JudgeType.AI,
        category=analysis.category.value,
        subcategory=analysis.subcategory,
        confidence=analysis.confidence,
    )
    db.add_all([record, judgment])
    ticket.ai_priority = assessment.priority
    return record


def get_latest_analysis(db: Session, ticket_id: int) -> TicketAIAnalysisRecord:
    record = find_latest_analysis(db, ticket_id)
    if record is None:
        raise AIAnalysisNotFoundError(ticket_id)
    return record


def find_latest_analysis(db: Session, ticket_id: int) -> TicketAIAnalysisRecord | None:
    statement = (
        select(TicketAIAnalysisRecord)
        .where(TicketAIAnalysisRecord.ticket_id == ticket_id)
        .order_by(TicketAIAnalysisRecord.created_at.desc(), TicketAIAnalysisRecord.id.desc())
        .limit(1)
    )
    return db.scalar(statement)
