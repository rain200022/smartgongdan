from app.core.exceptions import AuthorizationError
from app.models.ticket import Ticket
from app.models.user import User, UserRole


def ensure_can_view_ticket(user: User, ticket: Ticket) -> None:
    if user.role is UserRole.USER and ticket.requester_id != user.id:
        raise AuthorizationError("你无权访问该工单")
