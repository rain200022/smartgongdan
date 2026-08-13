from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.tickets import router as tickets_router
from app.core.config import get_settings
from app.services.ticket_service import InvalidTicketTransitionError, TicketNotFoundError

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tickets_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(TicketNotFoundError)
def ticket_not_found_handler(_request: Request, exc: TicketNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": f"Ticket {exc.args[0]} was not found"},
    )


@app.exception_handler(InvalidTicketTransitionError)
def invalid_transition_handler(
    _request: Request, exc: InvalidTicketTransitionError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )
