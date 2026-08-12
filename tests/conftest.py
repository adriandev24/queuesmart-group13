import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent / "test_queuesmart.db"
os.environ["QUEUESMART_DATABASE_URL"] = f"sqlite:///{TEST_DB}"

import pytest
from fastapi.testclient import TestClient
from backend.database import Base, engine
from backend.main import app


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def pytest_sessionfinish(session, exitstatus):
    try:
        TEST_DB.unlink(missing_ok=True)
    except OSError:
        pass
