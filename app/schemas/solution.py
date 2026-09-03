from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.models.solution import RejectionCategory, SolutionReviewDecision
from app.schemas.common import APIModel


class SolutionEvidence(APIModel):
    reference: str
    source_type: Literal["knowledge", "historical_ticket"]
    title: str
    excerpt: str
    resolution: str | None


class TicketSolutionContext(APIModel):
    ticket_id: int
    title: str
    description: str
    summary: str
    category: str
    subcategory: str
    attempted_actions: list[str]
    evidence: list[SolutionEvidence]


class TicketAISolutionDraft(APIModel):
    diagnosis: str = Field(min_length=1, max_length=2_000)
    possible_causes: list[str] = Field(max_length=10)
    steps: list[str] = Field(max_length=20)
    referenced_cases: list[str] = Field(max_length=10)
    need_human: bool


class TicketSolutionReviewCreate(APIModel):
    decision: SolutionReviewDecision
    engineer_solution: str | None = Field(default=None, max_length=20_000)
    rejection_reason: str | None = Field(default=None, max_length=2_000)
    rejection_category: RejectionCategory | None = None

    @model_validator(mode="after")
    def validate_decision_details(self) -> "TicketSolutionReviewCreate":
        if self.decision is SolutionReviewDecision.ADOPTED:
            if not self.engineer_solution or not self.engineer_solution.strip():
                raise ValueError("采用建议时必须填写工程师解决方案")
            self.engineer_solution = self.engineer_solution.strip()
            self.rejection_reason = None
            self.rejection_category = None
        else:
            self.engineer_solution = None
            if self.rejection_reason is not None:
                self.rejection_reason = self.rejection_reason.strip() or None
        return self


class TicketSolutionReviewRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solution_id: int
    ticket_id: int
    reviewer_user_id: int
    decision: SolutionReviewDecision
    engineer_solution: str | None
    rejection_reason: str | None
    rejection_category: RejectionCategory | None
    created_at: datetime


class TicketAISolutionRead(TicketAISolutionDraft):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    model_name: str
    created_at: datetime
    review: TicketSolutionReviewRead | None = None
