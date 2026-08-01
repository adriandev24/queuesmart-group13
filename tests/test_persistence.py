from fastapi.testclient import TestClient

import backend.database as database
from backend.main import app
from backend.models import History, QueueEntry, Service, UserCredential
from tests.conftest import login


def test_data_survives_separate_requests_and_sessions(client, user_headers):
    service = client.get("/api/services").json()[0]
    joined = client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "Persistence test"})
    assert joined.status_code == 201

    # A new SQLAlchemy session sees the same committed records.
    with database.SessionLocal() as db:
        assert db.query(QueueEntry).filter_by(status="waiting").count() == 1
        assert db.query(Service).count() == 4
        assert db.query(UserCredential).count() == 2

    # A separate HTTP request retrieves the same persisted queue entry.
    retrieved = client.get("/api/queues/status", headers=user_headers)
    assert retrieved.status_code == 200
    assert retrieved.json()["reason_for_visit"] == "Persistence test"


def test_history_is_stored_as_a_relational_record(client, user_headers, admin_headers):
    service = next(item for item in client.get("/api/services").json() if item["name"] == "Financial Aid Desk")
    client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "FAFSA review"})
    client.post(f"/api/admin/queues/{service['id']}/serve-next", headers=admin_headers)
    with database.SessionLocal() as db:
        record = db.query(History).one()
        assert record.user.email == "user@queuesmart.example"
        assert record.service.name == "Financial Aid Desk"
        assert record.queue_entry.status == "served"


def test_frontend_is_served_by_backend(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "QueueSmart" in response.text
    assert "A4 Database Build" in response.text
