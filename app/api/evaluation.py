from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentUser, StaffUser
from app.core.classification import CLASSIFICATION_TREE
from app.db.session import get_db
from app.schemas.evaluation import (
    ClassificationConfirmation,
    ClassificationConfirmationRead,
    ClassificationMetrics,
    JudgmentRead,
    MVPMetrics,
    SearchEvaluationRunRead,
)
from app.services import evaluation_service, ticket_service
from app.services.embedding_service import EmbeddingService, get_embedding_service

router = APIRouter(tags=["classification evaluation"])
DbSession = Annotated[Session, Depends(get_db)]
EmbeddingServiceDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]


@router.get("/classification-tree", response_model=dict[str, list[str]])
def get_classification_tree(_user: CurrentUser) -> dict[str, list[str]]:
    return {
        category.value: list(subcategories)
        for category, subcategories in CLASSIFICATION_TREE.items()
    }


@router.post(
    "/tickets/{ticket_id}/classification/confirm",
    response_model=ClassificationConfirmationRead,
)
def confirm_classification(
    ticket_id: int, payload: ClassificationConfirmation, db: DbSession, _staff: StaffUser
) -> ClassificationConfirmationRead:
    ticket = ticket_service.get_ticket(db, ticket_id)
    ticket_service.ensure_ticket_editable(ticket)
    result = evaluation_service.confirm_classification(db, ticket=ticket, payload=payload)
    return evaluation_service.to_confirmation_read(ticket, result)


@router.get("/tickets/{ticket_id}/judgments", response_model=list[JudgmentRead])
def list_judgments(ticket_id: int, db: DbSession, _staff: StaffUser) -> list[JudgmentRead]:
    ticket_service.get_ticket(db, ticket_id)
    judgments = evaluation_service.list_judgments(db, ticket_id)
    return [JudgmentRead.model_validate(item) for item in judgments]


@router.get("/metrics/classification", response_model=ClassificationMetrics)
def classification_metrics(db: DbSession, _staff: StaffUser) -> ClassificationMetrics:
    return evaluation_service.classification_metrics(db)


@router.get("/metrics/mvp", response_model=MVPMetrics)
def mvp_metrics(db: DbSession, _staff: StaffUser) -> MVPMetrics:
    return evaluation_service.mvp_metrics(db)


@router.post("/metrics/search/run", response_model=SearchEvaluationRunRead)
def run_search_evaluation(
    db: DbSession,
    embedding_service: EmbeddingServiceDependency,
    _staff: StaffUser,
) -> SearchEvaluationRunRead:
    record = evaluation_service.run_search_evaluation(
        db,
        dataset=evaluation_service.load_search_benchmark(),
        embedding_service=embedding_service,
    )
    return SearchEvaluationRunRead.model_validate(record)
