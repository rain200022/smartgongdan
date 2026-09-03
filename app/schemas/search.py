from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.core.classification import TicketCategory, validate_classification
from app.models.ticket import TicketPriority
from app.schemas.common import APIModel


class KnowledgeSeed(APIModel):
    code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)
    category: TicketCategory
    subcategory: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_pair(self) -> "KnowledgeSeed":
        validate_classification(self.category, self.subcategory)
        return self


class HistoricalTicketSeed(APIModel):
    reference: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    category: TicketCategory
    subcategory: str = Field(min_length=1, max_length=100)
    priority: TicketPriority
    resolution: str = Field(min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def validate_pair(self) -> "HistoricalTicketSeed":
        validate_classification(self.category, self.subcategory)
        return self


class SimilarResult(APIModel):
    model_config = ConfigDict(from_attributes=True)

    source_type: Literal["knowledge", "historical_ticket"]
    source_id: int
    reference: str
    title: str
    excerpt: str
    category: str
    subcategory: str
    resolution: str | None
    keyword_score: float | None
    semantic_score: float | None
    combined_score: float
    match_reasons: list[str]
    created_at: datetime


class SimilarResultList(APIModel):
    items: list[SimilarResult]
    query_model: str
