import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    AIServiceError,
    InvalidSolutionReviewError,
    SolutionNotFoundError,
)
from app.models.solution import (
    RejectionCategory,
    SolutionReviewDecision,
    TicketAISolution,
    TicketSolutionReview,
)
from app.models.user import User
from app.schemas.solution import (
    SolutionEvidence,
    TicketAISolutionDraft,
    TicketSolutionContext,
    TicketSolutionReviewCreate,
)
from app.services import ai_analysis_service, search_service, ticket_service
from app.services.ai_service import AIService
from app.services.embedding_service import EmbeddingService


def generate_solution(
    db: Session,
    *,
    ticket_id: int,
    ai_service: AIService,
    embedding_service: EmbeddingService,
) -> TicketAISolution:
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket_service.ensure_ticket_editable(ticket)
    analysis = ai_analysis_service.get_latest_analysis(db, ticket_id)
    results = search_service.search_similar(
        db,
        ticket_id=ticket_id,
        embedding_service=embedding_service,
        limit=5,
    )
    context = TicketSolutionContext(
        ticket_id=ticket.id,
        title=ticket.title,
        description=ticket.description,
        summary=analysis.summary,
        category=analysis.category,
        subcategory=analysis.subcategory,
        attempted_actions=analysis.attempted_actions,
        evidence=[
            SolutionEvidence(
                reference=item.reference,
                source_type=item.source_type,
                title=item.title,
                excerpt=item.excerpt,
                resolution=item.resolution,
            )
            for item in results
        ],
    )
    draft = ai_service.generate_solution(context)
    validated = _validate_draft(draft, context)
    record = TicketAISolution(
        ticket_id=ticket.id,
        model_name=ai_service.model_name,
        **validated.model_dump(),
    )
    db.add(record)
    db.commit()
    return get_solution(db, ticket_id=ticket_id, solution_id=record.id)


def get_latest_solution(db: Session, ticket_id: int) -> TicketAISolution:
    ticket_service.get_ticket(db, ticket_id)
    statement = (
        select(TicketAISolution)
        .options(selectinload(TicketAISolution.review))
        .where(TicketAISolution.ticket_id == ticket_id)
        .order_by(TicketAISolution.created_at.desc(), TicketAISolution.id.desc())
        .limit(1)
    )
    record = db.scalar(statement)
    if record is None:
        raise SolutionNotFoundError(ticket_id=ticket_id)
    return record


def get_solution(db: Session, *, ticket_id: int, solution_id: int) -> TicketAISolution:
    statement = (
        select(TicketAISolution)
        .options(selectinload(TicketAISolution.review))
        .where(
            TicketAISolution.id == solution_id,
            TicketAISolution.ticket_id == ticket_id,
        )
    )
    record = db.scalar(statement)
    if record is None:
        raise SolutionNotFoundError(ticket_id=ticket_id, solution_id=solution_id)
    return record


def review_solution(
    db: Session,
    *,
    ticket_id: int,
    solution_id: int,
    reviewer: User,
    payload: TicketSolutionReviewCreate,
) -> TicketAISolution:
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket_service.ensure_ticket_editable(ticket)
    solution = get_solution(db, ticket_id=ticket_id, solution_id=solution_id)
    if solution.review is not None:
        raise InvalidSolutionReviewError("AI 建议已经完成审核，不能重复提交")
    review_values = payload.model_dump()
    if payload.decision is SolutionReviewDecision.REJECTED and payload.rejection_category is None:
        review_values["rejection_category"] = RejectionCategory.OTHER
    db.add(
        TicketSolutionReview(
            solution_id=solution.id,
            ticket_id=ticket.id,
            reviewer_user_id=reviewer.id,
            **review_values,
        )
    )
    db.commit()
    db.expire(solution, ["review"])
    return get_solution(db, ticket_id=ticket_id, solution_id=solution_id)


def _validate_draft(
    draft: TicketAISolutionDraft,
    context: TicketSolutionContext,
) -> TicketAISolutionDraft:
    allowed_references = {item.reference for item in context.evidence}
    references = list(dict.fromkeys(draft.referenced_cases))
    if any(reference not in allowed_references for reference in references):
        raise AIServiceError("AI provider cited evidence outside the retrieved result set")

    steps = [
        step.strip()
        for step in draft.steps
        if step.strip() and not _repeats_attempt(step, context.attempted_actions)
    ]
    causes = list(dict.fromkeys(cause.strip() for cause in draft.possible_causes if cause.strip()))
    return draft.model_copy(
        update={
            "possible_causes": causes,
            "steps": list(dict.fromkeys(steps)),
            "referenced_cases": references,
            "need_human": draft.need_human or not steps,
        }
    )


def _repeats_attempt(step: str, attempted_actions: list[str]) -> bool:
    normalized_step = _normalize_action(step)
    return any(
        normalized_attempt
        and (normalized_attempt in normalized_step or normalized_step in normalized_attempt)
        for action in attempted_actions
        if (normalized_attempt := _normalize_action(action))
    )


def _normalize_action(value: str) -> str:
    normalized = (
        value.lower().replace("重新启动", "重启").replace("重新连接", "重连").replace("vpn", "")
    )
    return re.sub(r"[\W_]|请|首先|然后|再次", "", normalized)
