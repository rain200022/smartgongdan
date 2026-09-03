import os
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import UserRole
from app.schemas.auth import UserCreate
from app.services import auth_service

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def reset_database() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    with TestingSession() as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    auth_service.create_user(
        db_session,
        UserCreate(
            username="test-engineer",
            display_name="测试工程师",
            password="Test-Engineer-Password-2026!",
            role=UserRole.ENGINEER,
        ),
    )
    with TestClient(app) as test_client:
        login = test_client.post(
            "/auth/login",
            json={
                "username": "test-engineer",
                "password": "Test-Engineer-Password-2026!",
            },
        )
        assert login.status_code == 200
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def anonymous_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
