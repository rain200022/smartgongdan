from datetime import datetime

from pydantic import ConfigDict, Field

from app.models.ai_analysis import JudgeType
from app.models.solution import RejectionCategory
from app.schemas.common import APIModel, ClassificationPair


class ClassificationConfirmation(ClassificationPair):
    pass


class JudgmentRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    judge_type: JudgeType
    category: str
    subcategory: str
    confidence: float | None
    created_at: datetime


class ClassificationEvaluationRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    ai_judgment_id: int
    engineer_judgment_id: int
    category_agreement: bool
    subcategory_agreement: bool
    agreement: bool
    created_at: datetime


class ClassificationConfirmationRead(APIModel):
    ticket_id: int
    final_category: str
    engineer_judgment: JudgmentRead
    compared_ai_judgment: JudgmentRead | None
    evaluation: ClassificationEvaluationRead | None


class ClassificationMetrics(APIModel):
    confirmed_tickets: int
    evaluated_tickets: int
    category_matches: int
    exact_matches: int
    category_agreement_rate: float | None
    exact_agreement_rate: float | None


class SearchBenchmarkCase(APIModel):
    id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    expected_references: list[str] = Field(min_length=1, max_length=10)


class SearchBenchmarkDataset(APIModel):
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=50)
    cases: list[SearchBenchmarkCase] = Field(min_length=1, max_length=500)


class SearchEvaluationDetail(APIModel):
    case_id: str
    expected_references: list[str]
    retrieved_references: list[str]
    matched_references: list[str]
    recall_at_5: float


class SearchEvaluationRunRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_name: str
    dataset_version: str
    query_count: int
    recall_at_5: float
    embedding_model: str
    details: list[SearchEvaluationDetail]
    created_at: datetime


class RejectionCategoryCount(APIModel):
    category: RejectionCategory
    count: int


class SolutionMetrics(APIModel):
    generated_suggestions: int
    reviewed_suggestions: int
    pending_suggestions: int
    adopted_suggestions: int
    rejected_suggestions: int
    adoption_rate: float | None
    average_review_minutes: float | None
    rejection_categories: list[RejectionCategoryCount]


class HandlingTimeMetrics(APIModel):
    resolved_tickets: int
    average_resolution_minutes: float | None
    median_resolution_minutes: float | None


class MVPMetrics(APIModel):
    classification: ClassificationMetrics
    solutions: SolutionMetrics
    handling_time: HandlingTimeMetrics
    latest_search_evaluation: SearchEvaluationRunRead | None
