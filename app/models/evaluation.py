from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class SearchEvaluationRun(Base):
    __tablename__ = "search_evaluation_runs"
    __table_args__ = (Index("ix_search_evaluation_runs_created", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dataset_name: Mapped[str] = mapped_column(String(100))
    dataset_version: Mapped[str] = mapped_column(String(50))
    query_count: Mapped[int] = mapped_column(Integer)
    recall_at_5: Mapped[float] = mapped_column(Float)
    embedding_model: Mapped[str] = mapped_column(String(200))
    details: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
