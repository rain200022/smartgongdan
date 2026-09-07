from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.classification import join_classification
from app.models.ai_analysis import (
    JudgeType,
    TicketClassificationEvaluation,
    TicketJudgment,
)
from app.models.evaluation import SearchEvaluationRun
from app.models.solution import (
    RejectionCategory,
    SolutionReviewDecision,
    TicketAISolution,
    TicketSolutionReview,
)
from app.models.ticket import Ticket, TicketStatus
from app.models.user import User
from app.schemas.evaluation import (
    ClassificationConfirmation,
    ClassificationConfirmationRead,
    ClassificationMetrics,
    HandlingTimeMetrics,
    MVPMetrics,
    RejectionCategoryCount,
    SearchBenchmarkDataset,
    SearchEvaluationDetail,
    SearchEvaluationRunRead,
    SolutionMetrics,
)
from app.services import search_service
from app.services import ticket_mutation_service as mutations
from app.services.embedding_service import EmbeddingService

DEFAULT_SEARCH_BENCHMARK = Path(__file__).resolve().parents[2] / "data" / "search_evaluation.json"


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    engineer_judgment: TicketJudgment
    compared_ai_judgment: TicketJudgment | None
    evaluation: TicketClassificationEvaluation | None


def stage_classification_confirmation(
    db: Session,
    *,
    ticket: Ticket,
    payload: ClassificationConfirmation,
) -> ConfirmationResult:
    ticket.final_category = join_classification(payload.category.value, payload.subcategory)
    engineer_judgment = TicketJudgment(
        ticket_id=ticket.id,
        judge_type=JudgeType.ENGINEER,
        category=payload.category.value,
        subcategory=payload.subcategory,
    )
    db.add(engineer_judgment)
    db.flush()

    ai_judgment = get_latest_judgment(db, ticket.id, JudgeType.AI)
    evaluation = None
    if ai_judgment is not None:
        category_agreement = ai_judgment.category == engineer_judgment.category
        subcategory_agreement = (
            category_agreement and ai_judgment.subcategory == engineer_judgment.subcategory
        )
        evaluation = TicketClassificationEvaluation(
            ticket_id=ticket.id,
            ai_judgment_id=ai_judgment.id,
            engineer_judgment_id=engineer_judgment.id,
            category_agreement=category_agreement,
            subcategory_agreement=subcategory_agreement,
            agreement=subcategory_agreement,
        )
        db.add(evaluation)
        db.flush()

    return ConfirmationResult(engineer_judgment, ai_judgment, evaluation)


def confirm_classification(
    db: Session,
    *,
    ticket: Ticket,
    payload: ClassificationConfirmation,
    actor: User,
    expected_version: int | None = None,
) -> ConfirmationResult:
    mutations.stage_mutation(
        db,
        ticket,
        actor=actor,
        action="classification_confirmed",
        expected_version=expected_version,
    )
    result = stage_classification_confirmation(db, ticket=ticket, payload=payload)
    db.commit()
    db.refresh(result.engineer_judgment)
    if result.evaluation is not None:
        db.refresh(result.evaluation)
    return result


def to_confirmation_read(
    ticket: Ticket, result: ConfirmationResult
) -> ClassificationConfirmationRead:
    return ClassificationConfirmationRead(
        ticket_id=ticket.id,
        final_category=ticket.final_category or "",
        engineer_judgment=result.engineer_judgment,
        compared_ai_judgment=result.compared_ai_judgment,
        evaluation=result.evaluation,
    )


def get_latest_judgment(
    db: Session, ticket_id: int, judge_type: JudgeType
) -> TicketJudgment | None:
    statement = (
        select(TicketJudgment)
        .where(
            TicketJudgment.ticket_id == ticket_id,
            TicketJudgment.judge_type == judge_type,
        )
        .order_by(TicketJudgment.created_at.desc(), TicketJudgment.id.desc())
        .limit(1)
    )
    return db.scalar(statement)


def list_judgments(db: Session, ticket_id: int) -> list[TicketJudgment]:
    statement = (
        select(TicketJudgment)
        .where(TicketJudgment.ticket_id == ticket_id)
        .order_by(TicketJudgment.created_at, TicketJudgment.id)
    )
    return list(db.scalars(statement))


def classification_metrics(db: Session) -> ClassificationMetrics:
    engineer_ticket_ids = set(
        db.scalars(
            select(TicketJudgment.ticket_id).where(TicketJudgment.judge_type == JudgeType.ENGINEER)
        )
    )
    evaluations = list(
        db.scalars(
            select(TicketClassificationEvaluation).order_by(
                TicketClassificationEvaluation.created_at,
                TicketClassificationEvaluation.id,
            )
        )
    )
    latest_by_ticket = {evaluation.ticket_id: evaluation for evaluation in evaluations}
    latest = list(latest_by_ticket.values())
    evaluated = len(latest)
    category_matches = sum(item.category_agreement for item in latest)
    exact_matches = sum(item.agreement for item in latest)
    return ClassificationMetrics(
        confirmed_tickets=len(engineer_ticket_ids),
        evaluated_tickets=evaluated,
        category_matches=category_matches,
        exact_matches=exact_matches,
        category_agreement_rate=category_matches / evaluated if evaluated else None,
        exact_agreement_rate=exact_matches / evaluated if evaluated else None,
    )


def load_search_benchmark(path: Path = DEFAULT_SEARCH_BENCHMARK) -> SearchBenchmarkDataset:
    return SearchBenchmarkDataset.model_validate_json(path.read_text(encoding="utf-8"))


def run_search_evaluation(
    db: Session,
    *,
    dataset: SearchBenchmarkDataset,
    embedding_service: EmbeddingService,
) -> SearchEvaluationRun:
    details: list[SearchEvaluationDetail] = []
    for case in dataset.cases:
        results = search_service.search_similar_text(
            db,
            query_text=f"{case.title}\n{case.description}",
            embedding_service=embedding_service,
            limit=5,
        )
        retrieved = [item.reference for item in results]
        matched = [reference for reference in case.expected_references if reference in retrieved]
        details.append(
            SearchEvaluationDetail(
                case_id=case.id,
                expected_references=case.expected_references,
                retrieved_references=retrieved,
                matched_references=matched,
                recall_at_5=len(matched) / len(case.expected_references),
            )
        )

    record = SearchEvaluationRun(
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        query_count=len(details),
        recall_at_5=round(fmean(item.recall_at_5 for item in details), 4),
        embedding_model=embedding_service.model_name,
        details=[item.model_dump(mode="json") for item in details],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def latest_search_evaluation(db: Session) -> SearchEvaluationRun | None:
    return db.scalar(
        select(SearchEvaluationRun)
        .order_by(SearchEvaluationRun.created_at.desc(), SearchEvaluationRun.id.desc())
        .limit(1)
    )


def solution_metrics(db: Session) -> SolutionMetrics:
    solutions = list(db.scalars(select(TicketAISolution)))
    reviews = list(db.scalars(select(TicketSolutionReview)))
    solution_by_id = {solution.id: solution for solution in solutions}
    adopted = sum(review.decision is SolutionReviewDecision.ADOPTED for review in reviews)
    rejected = len(reviews) - adopted
    category_counts = Counter(
        review.rejection_category or RejectionCategory.OTHER
        for review in reviews
        if review.decision is SolutionReviewDecision.REJECTED
    )
    review_minutes = [
        max(
            (review.created_at - solution_by_id[review.solution_id].created_at).total_seconds()
            / 60,
            0,
        )
        for review in reviews
        if review.solution_id in solution_by_id
    ]
    return SolutionMetrics(
        generated_suggestions=len(solutions),
        reviewed_suggestions=len(reviews),
        pending_suggestions=len(solutions) - len(reviews),
        adopted_suggestions=adopted,
        rejected_suggestions=rejected,
        adoption_rate=adopted / len(reviews) if reviews else None,
        average_review_minutes=round(fmean(review_minutes), 2) if review_minutes else None,
        rejection_categories=[
            RejectionCategoryCount(category=category, count=count)
            for category, count in sorted(category_counts.items(), key=lambda item: item[0].value)
        ],
    )


def handling_time_metrics(db: Session) -> HandlingTimeMetrics:
    tickets = list(
        db.scalars(
            select(Ticket).where(
                Ticket.external_reference.is_(None),
                Ticket.status == TicketStatus.CLOSED,
                Ticket.resolved_at.is_not(None),
            )
        )
    )
    durations = [
        max((ticket.resolved_at - ticket.created_at).total_seconds() / 60, 0)
        for ticket in tickets
        if ticket.resolved_at is not None
    ]
    return HandlingTimeMetrics(
        resolved_tickets=len(durations),
        average_resolution_minutes=round(fmean(durations), 2) if durations else None,
        median_resolution_minutes=round(median(durations), 2) if durations else None,
    )


def mvp_metrics(db: Session) -> MVPMetrics:
    latest = latest_search_evaluation(db)
    return MVPMetrics(
        classification=classification_metrics(db),
        solutions=solution_metrics(db),
        handling_time=handling_time_metrics(db),
        latest_search_evaluation=(
            SearchEvaluationRunRead.model_validate(latest) if latest is not None else None
        ),
    )
