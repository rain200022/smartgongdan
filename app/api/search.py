from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import DbSession, StaffUser
from app.schemas.search import SimilarResultList
from app.services import search_service
from app.services.embedding_service import EmbeddingService, get_embedding_service

router = APIRouter(prefix="/tickets", tags=["search"])
EmbeddingServiceDependency = Annotated[EmbeddingService, Depends(get_embedding_service)]
ResultLimit = Annotated[int, Query(ge=1, le=10)]


@router.get("/{ticket_id}/similar", response_model=SimilarResultList)
def get_similar_results(
    ticket_id: int,
    db: DbSession,
    embedding_service: EmbeddingServiceDependency,
    _staff: StaffUser,
    limit: ResultLimit = 5,
) -> SimilarResultList:
    items = search_service.search_similar(
        db,
        ticket_id=ticket_id,
        embedding_service=embedding_service,
        limit=limit,
    )
    return SimilarResultList(items=items, query_model=embedding_service.model_name)
