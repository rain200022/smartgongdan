"""Real independent-connection races, on SQLite and an explicitly isolated PostgreSQL DB."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import AuthorizationError, InvalidTicketTransitionError
from app.db.base import Base
from app.models.ai_analysis import TicketAIAnalysisRecord, TicketJudgment
from app.models.solution import TicketAISolution
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.user import User, UserRole
from app.schemas.ticket import TicketClose
from app.services import ai_analysis_service, solution_service, ticket_service
from app.services.ai_service import LocalAIService
from app.services.embedding_service import LocalEmbeddingService
from app.services.ticket_mutation_service import ensure_can_mutate, stage_mutation


@pytest.fixture(params=["sqlite", "postgresql"])
def sessions(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "postgresql":
        url = os.environ.get("TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set TEST_DATABASE_URL to the isolated smartgongdan_test_concurrency DB")
        if make_url(url).database != "smartgongdan_test_concurrency":
            pytest.fail("Refusing to use any database other than smartgongdan_test_concurrency")
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    else:
        engine = create_engine(
            f"sqlite:///{tmp_path / 'race.sqlite'}", connect_args={"timeout": 10}
        )
    # Test-only schema; this URL can never default to the development database.
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False, autoflush=False)
    with factory() as db:
        db.add(
            User(
                id=1,
                username="race",
                display_name="race",
                password_hash="unused",
                role=UserRole.ENGINEER,
            )
        )
        db.add(Ticket(id=1, title="VPN", description="认证失败", user_category="网络/VPN"))
        db.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_two_writers_only_one_version_wins(sessions) -> None:
    barrier = Barrier(2)

    def worker() -> str:
        with sessions() as db:
            ticket = db.get(Ticket, 1)
            actor = db.get(User, 1)
            barrier.wait(timeout=10)
            try:
                stage_mutation(db, ticket, actor=actor, action="claimed", expected_version=None)
                ticket.assigned_engineer_id = actor.id
                db.commit()
                return "won"
            except InvalidTicketTransitionError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: worker(), range(2)))
    assert sorted(outcomes) == ["conflict", "won"]
    with sessions() as db:
        assert db.get(Ticket, 1).version == 2
        assert db.scalar(select(func.count()).select_from(TicketEvent)) == 1


@pytest.mark.parametrize("operation", ["analysis", "solution"])
def test_late_ai_result_after_close_leaves_no_partial_rows(sessions, operation: str) -> None:
    started, finish = Event(), Event()

    class SlowAI(LocalAIService):
        def analyze_ticket(self, ticket):
            started.set()
            assert finish.wait(timeout=10)
            return super().analyze_ticket(ticket)

        def generate_solution(self, context):
            started.set()
            assert finish.wait(timeout=10)
            return super().generate_solution(context)

    with sessions() as db:
        if operation == "solution":
            ai_analysis_service.analyze_ticket(
                db, ticket_id=1, ai_service=LocalAIService(), actor=db.get(User, 1)
            )
        before_analyses = db.scalar(select(func.count()).select_from(TicketAIAnalysisRecord))
        before_ai_judgments = db.scalar(select(func.count()).select_from(TicketJudgment))

    def worker() -> None:
        with sessions() as db:
            if operation == "analysis":
                ai_analysis_service.analyze_ticket(
                    db, ticket_id=1, ai_service=SlowAI(), actor=db.get(User, 1)
                )
            else:
                solution_service.generate_solution(
                    db,
                    ticket_id=1,
                    ai_service=SlowAI(),
                    embedding_service=LocalEmbeddingService(),
                    actor=db.get(User, 1),
                )

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(worker)
        try:
            assert started.wait(timeout=10)
            with sessions() as db:
                ticket_service.close_ticket(
                    db,
                    1,
                    TicketClose(
                        final_category="网络/VPN", final_priority="P3", resolution="证书恢复"
                    ),
                    embedding_service=LocalEmbeddingService(),
                    actor=db.get(User, 1),
                )
        finally:
            finish.set()
        with pytest.raises(InvalidTicketTransitionError):
            pending.result(timeout=10)
    with sessions() as db:
        assert db.get(Ticket, 1).status == "closed"
        assert (
            db.scalar(select(func.count()).select_from(TicketAIAnalysisRecord)) == before_analyses
        )
        assert (
            db.scalar(select(func.count()).select_from(TicketJudgment)) == before_ai_judgments + 1
        )
        assert db.scalar(select(func.count()).select_from(TicketAISolution)) == 0


def test_stage_rollback_and_inactive_actor(sessions) -> None:
    with sessions() as db:
        ticket, actor = db.get(Ticket, 1), db.get(User, 1)
        stage_mutation(db, ticket, actor=actor, action="updated", expected_version=1)
        db.rollback()
        assert db.get(Ticket, 1).version == 1
        assert db.scalar(select(func.count()).select_from(TicketEvent)) == 0
        actor.is_active = False
        with pytest.raises(AuthorizationError):
            ensure_can_mutate(ticket, actor, None)
