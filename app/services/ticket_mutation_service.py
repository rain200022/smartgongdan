from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.exceptions import AuthorizationError, InvalidTicketTransitionError
from app.core.time import utc_now
from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_event import TicketEvent
from app.models.user import User, UserRole


def ensure_can_mutate(ticket: Ticket, actor: User, expected_version: int | None) -> None:
    if not actor.is_active or actor.role not in {UserRole.ENGINEER, UserRole.ADMIN}:
        raise AuthorizationError("该操作需要有效的工程师或管理员账号")
    if ticket.status is TicketStatus.CLOSED:
        raise InvalidTicketTransitionError("Closed tickets cannot be edited")
    if ticket.assigned_engineer_id not in {None, actor.id} and actor.role is not UserRole.ADMIN:
        raise AuthorizationError("工单已由其他工程师认领，您只能查看")
    if expected_version is not None and expected_version != ticket.version:
        raise InvalidTicketTransitionError("工单已更新，请刷新并核对最新内容后重试；您的草稿未提交")


def stage_mutation(
    db: Session, ticket: Ticket, *, actor: User, action: str, expected_version: int | None
) -> None:
    """Reserve one version in this transaction, after slow external calls and before writes.

    The conditional UPDATE serializes all mutation paths without holding a row lock
    while waiting for the AI provider. A losing transaction adds no audit/business rows.
    """
    ensure_can_mutate(ticket, actor, expected_version)
    version = ticket.version
    with db.no_autoflush:
        new_version = db.scalar(
            update(Ticket)
            .where(
                Ticket.id == ticket.id,
                Ticket.version == version,
                Ticket.status != TicketStatus.CLOSED,
            )
            .values(version=version + 1, updated_at=utc_now())
            .returning(Ticket.version)
            .execution_options(synchronize_session=False)
        )
    if new_version is None:
        db.rollback()
        raise InvalidTicketTransitionError("工单已被其他操作更新，请刷新并核对后重试")
    set_committed_value(ticket, "version", new_version)
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            version=new_version,
            actor_id=actor.id,
            actor_name=actor.display_name,
            action=action,
        )
    )


def list_events(db: Session, ticket_id: int, *, limit: int, offset: int) -> list[TicketEvent]:
    return list(
        db.scalars(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.version)
            .limit(limit)
            .offset(offset)
        )
    )
