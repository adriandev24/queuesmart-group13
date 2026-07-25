from backend.store import store


def test_admin_cannot_create_duplicate_service(client, admin_headers):
    response = client.post(
        "/api/services",
        headers=admin_headers,
        json={
            "name": "Campus Advising",
            "description": "Duplicate service should not be created.",
            "expected_duration": 10,
            "priority_level": "medium",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"] == "A service with this name already exists"


def test_missing_service_wait_estimate_returns_404(client):
    response = client.get("/api/services/999/estimate")

    assert response.status_code == 404
    assert response.json()["error"] == "Service not found"


def test_user_cannot_join_closed_queue(client, user_headers):
    store.services[2]["is_open"] = False

    response = client.post(
        "/api/queues/join",
        headers=user_headers,
        json={"service_id": 3, "reason": "Replace damaged ID card"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "This queue is currently closed"


def test_user_cannot_leave_queue_they_did_not_join(client, user_headers):
    response = client.delete("/api/queues/2/leave", headers=user_headers)

    assert response.status_code == 404
    assert response.json()["error"] == "Active queue entry not found"


def test_admin_cannot_serve_empty_queue(client, admin_headers):
    response = client.post("/api/admin/queues/4/serve-next", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["error"] == "No users are waiting in this queue"
