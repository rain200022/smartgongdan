from fastapi import APIRouter

from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.evaluation import router as evaluation_router
from app.api.search import router as search_router
from app.api.solutions import router as solutions_router
from app.api.tickets import router as tickets_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(tickets_router)
api_router.include_router(ai_router)
api_router.include_router(evaluation_router)
api_router.include_router(search_router)
api_router.include_router(solutions_router)
