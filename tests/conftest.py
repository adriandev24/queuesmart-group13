import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.store import store


@pytest.fixture(autouse=True)
def reset_in_memory_store():
    store.reset()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client: TestClient, email: str, password: str, role: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password, "role": role},
    )
    assert response.status_code == 200
    return response.json()["token"]


@pytest.fixture
def user_headers(client):
    token = login(client, "user@queuesmartapp.com", "UserPass123", "user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client):
    token = login(client, "admin@queuesmartapp.com", "AdminPass123", "administrator")
    return {"Authorization": f"Bearer {token}"}
