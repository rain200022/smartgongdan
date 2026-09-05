"""Disposable browser-test server; never imports or connects to the deployment database."""

import os
from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def create_test_app(database_path: Path) -> "FastAPI":
    # Override deployment settings before importing the application/database modules.
    database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
    os.environ.update(
        DATABASE_URL=database_url,
        AI_PROVIDER="local",
        AI_MODEL="local-rules-v1",
        AUTH_COOKIE_SECURE="false",
        ALLOWED_ORIGINS="http://127.0.0.1:15173",
    )

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import NullPool

    from app.core.config import get_settings
    from app.core.time import utc_now
    from app.db.base import Base
    from app.db.session import get_db
    from app.main import create_app
    from app.models.ticket import Ticket, TicketPriority
    from app.models.user import UserRole
    from app.schemas.auth import UserCreate
    from app.services.auth_service import create_user

    get_settings.cache_clear()
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )
    # Parallel HTTP requests need separate connections and transaction isolation.
    with engine.connect() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL"))
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # Only this explicit test factory creates a disposable schema; production uses Alembic.
    Base.metadata.create_all(engine)
    with testing_session() as db:
        user_ids: dict[str, int] = {}
        for username, role in (
            ("e2e-user", UserRole.USER),
            ("e2e-other", UserRole.USER),
            ("e2e-engineer", UserRole.ENGINEER),
        ):
            user = create_user(
                db,
                UserCreate(
                    username=username,
                    display_name=username,
                    password="E2E-Only-Password-2026!",
                    role=role,
                ),
            )
            user_ids[username] = user.id
        created_at = utc_now() - timedelta(days=1)
        for number in range(1, 106):
            db.add(
                Ticket(
                    id=number,
                    requester_id=user_ids["e2e-user"],
                    title=(
                        "跨百条分页回归：VPN认证失败" if number == 1 else f"历史工单 {number:03d}"
                    ),
                    description="VPN认证服务器不可用，已重启客户端，问题仍然存在。",
                    user_category="网络/VPN",
                    final_priority=TicketPriority.P3,
                    created_at=created_at + timedelta(seconds=number),
                    updated_at=created_at + timedelta(seconds=number),
                )
            )
        db.add(
            Ticket(
                id=106,
                requester_id=user_ids["e2e-other"],
                title="其他用户的私人工单",
                description="另一账号的私有问题，仅本人和工程师可见。",
            )
        )
        db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session() as db:
            yield db

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    return application


def main() -> None:
    import uvicorn

    with TemporaryDirectory(prefix="smartgongdan-e2e-") as directory:
        application = create_test_app(Path(directory) / "browser-tests.sqlite")
        uvicorn.run(application, host="127.0.0.1", port=18000, access_log=False)


if __name__ == "__main__":
    main()
