from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AIAnalysisNotFoundError,
    AIServiceError,
    AuthenticationError,
    AuthorizationError,
    EmbeddingServiceError,
    InvalidSolutionReviewError,
    InvalidTicketTransitionError,
    InvalidUserOperationError,
    SolutionNotFoundError,
    TicketNotFoundError,
    UserAlreadyExistsError,
    UserNotFoundError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TicketNotFoundError)
    def ticket_not_found_handler(_request: Request, exc: TicketNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(AuthenticationError)
    def authentication_error_handler(_request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Session"},
        )

    @app.exception_handler(AuthorizationError)
    def authorization_error_handler(_request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc)},
        )

    @app.exception_handler(UserAlreadyExistsError)
    def user_exists_handler(_request: Request, exc: UserAlreadyExistsError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(UserNotFoundError)
    def user_not_found_handler(_request: Request, exc: UserNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidUserOperationError)
    def invalid_user_operation_handler(
        _request: Request, exc: InvalidUserOperationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidTicketTransitionError)
    def invalid_transition_handler(
        _request: Request, exc: InvalidTicketTransitionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(AIServiceError)
    def ai_service_error_handler(_request: Request, exc: AIServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(EmbeddingServiceError)
    def embedding_service_error_handler(
        _request: Request, exc: EmbeddingServiceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": str(exc)},
        )

    @app.exception_handler(AIAnalysisNotFoundError)
    def ai_analysis_not_found_handler(
        _request: Request, exc: AIAnalysisNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(SolutionNotFoundError)
    def solution_not_found_handler(_request: Request, exc: SolutionNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidSolutionReviewError)
    def invalid_solution_review_handler(
        _request: Request, exc: InvalidSolutionReviewError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )
