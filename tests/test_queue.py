def test_wait_estimate_uses_position_times_expected_duration(client):
    response = client.get("/api/services/1/estimate")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"position": 4, "estimated_wait": 32}


def test_user_joins_queue_and_receives_notifications(client, user_headers):
    response = client.post(
        "/api/queues/join",
        headers=user_headers,
        json={"service_id": 3, "reason": "Replace damaged ID card"},
    )
    assert response.status_code == 201
    entry = response.json()["queue_entry"]
    assert entry["position"] == 1
    assert entry["estimated_wait"] == 6
    assert entry["priority"] == "medium"

    notifications = client.get("/api/notifications", headers=user_headers).json()["notifications"]
    types = {item["type"] for item in notifications}
    assert "joined" in types
    assert "almost_ready" in types


def test_user_cannot_join_two_queues(client, user_headers):
    first = client.post(
        "/api/queues/join",
        headers=user_headers,
        json={"service_id": 2, "reason": "Award question"},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/queues/join",
        headers=user_headers,
        json={"service_id": 3, "reason": "Card question"},
    )
    assert second.status_code == 409


def test_join_queue_validates_reason_and_service_type(client, user_headers):
    response = client.post(
        "/api/queues/join",
        headers=user_headers,
        json={"service_id": "abc", "reason": "x"},
    )
    assert response.status_code == 422
    fields = {item["field"] for item in response.json()["details"]}
    assert {"service_id", "reason"}.issubset(fields)


def test_user_leaves_queue_and_history_is_recorded(client, user_headers):
    joined = client.post(
        "/api/queues/join",
        headers=user_headers,
        json={"service_id": 2, "reason": "Verify financial aid form"},
    )
    assert joined.status_code == 201

    left = client.delete("/api/queues/2/leave", headers=user_headers)
    assert left.status_code == 200
    assert left.json()["history"]["outcome"] == "left_queue"

    status = client.get("/api/queues/status", headers=user_headers)
    assert status.json()["queue_status"] is None

    history = client.get("/api/history", headers=user_headers).json()["history"]
    assert history[0]["service_name"] == "Financial Aid Desk"
    assert history[0]["outcome"] == "left_queue"


def test_admin_queue_is_priority_then_arrival_order(client, admin_headers):
    response = client.get("/api/admin/queues/1", headers=admin_headers)
    assert response.status_code == 200
    queue = response.json()["queue"]
    assert [item["priority"] for item in queue] == ["high", "medium", "low"]
    assert [item["position"] for item in queue] == [1, 2, 3]


def test_admin_serves_next_user_and_updates_history(client, admin_headers):
    response = client.post("/api/admin/queues/1/serve-next", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["served_user"] == "Maya Thompson"
    assert payload["history"]["outcome"] == "served"
    assert len(payload["remaining_queue"]) == 2
    assert payload["remaining_queue"][0]["user_name"] == "Omar Carter"


def test_user_cannot_access_admin_queue(client, user_headers):
    response = client.get("/api/admin/queues/1", headers=user_headers)
    assert response.status_code == 403


def test_admin_dashboard_totals_are_backend_generated(client, admin_headers):
    response = client.get("/api/dashboard/admin", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["open_services"] == 4
    assert payload["total_waiting"] == 3
    assert payload["longest_wait"] == 24
