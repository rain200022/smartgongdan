import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

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
def client() -> TestClient:
    def override_get_db():
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
