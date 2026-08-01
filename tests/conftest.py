from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.database import configure_database, init_db
from backend.main import app


@pytest.fixture
def client(tmp_path):
    database_path = tmp_path / "queuesmart_test.db"
    configure_database(f"sqlite:///{database_path}")
    init_db(seed=True)
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def user_headers(client):
    return login(client, "user@queuesmart.example", "User123!")


@pytest.fixture
def admin_headers(client):
    return login(client, "admin@queuesmart.example", "Admin123!")
