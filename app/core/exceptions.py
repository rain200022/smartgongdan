class ApplicationError(Exception):
    """Base class for expected domain and integration failures."""


class TicketNotFoundError(ApplicationError):
    def __init__(self, ticket_id: int) -> None:
        self.ticket_id = ticket_id
        super().__init__(f"Ticket {ticket_id} was not found")


class InvalidTicketTransitionError(ApplicationError):
    """Raised when a requested ticket state change violates workflow rules."""


class AIServiceError(ApplicationError):
    """Raised when the configured AI provider cannot return a valid analysis."""


class EmbeddingServiceError(ApplicationError):
    """Raised when the configured embedding provider cannot return a valid vector."""


class AIAnalysisNotFoundError(ApplicationError):
    def __init__(self, ticket_id: int) -> None:
        self.ticket_id = ticket_id
        super().__init__(f"Ticket {ticket_id} has no AI analysis")


class SolutionNotFoundError(ApplicationError):
    def __init__(self, ticket_id: int, solution_id: int | None = None) -> None:
        target = f"solution {solution_id}" if solution_id is not None else "AI solution"
        super().__init__(f"Ticket {ticket_id} has no {target}")


class InvalidSolutionReviewError(ApplicationError):
    """Raised when an AI solution review violates workflow rules."""


class AuthenticationError(ApplicationError):
    """Raised when a request has no valid authenticated session."""


class AuthorizationError(ApplicationError):
    """Raised when an authenticated user cannot perform an operation."""


class UserAlreadyExistsError(ApplicationError):
    def __init__(self, username: str) -> None:
        super().__init__(f"User '{username}' already exists")


class UserNotFoundError(ApplicationError):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} was not found")


class InvalidUserOperationError(ApplicationError):
    """Raised when an account-management action violates identity invariants."""
