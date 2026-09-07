from datetime import datetime

from pydantic import ConfigDict

from app.schemas.common import APIModel


class TicketEventRead(APIModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    version: int
    actor_id: int
    actor_name: str
    action: str
    created_at: datetime
