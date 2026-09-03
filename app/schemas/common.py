from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.classification import TicketCategory, validate_classification


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClassificationPair(APIModel):
    category: TicketCategory
    subcategory: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        validate_classification(self.category.value, self.subcategory)
        return self
