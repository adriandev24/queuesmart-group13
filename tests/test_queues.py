from tests.conftest import login


def get_service(client, name="Campus Advising"):
    return next(item for item in client.get("/api/services").json() if item["name"] == name)


def register_and_login(client, number):
    email = f"student{number}@example.com"
    password = "StudentPass9!"
    client.post("/api/auth/register", json={"full_name": f"Student {number}", "email": email, "password": password, "role": "user"})
    return login(client, email, password)


def test_user_can_join_and_status_is_retrievable(client, user_headers):
    service = get_service(client)
    joined = client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "Degree plan review"})
    assert joined.status_code == 201
    assert joined.json()["position"] == 1
    status = client.get("/api/queues/status", headers=user_headers)
    assert status.json()["active"] is True
    assert status.json()["service_name"] == "Campus Advising"


def test_join_creates_persistent_notifications(client, user_headers):
    service = get_service(client)
    client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "Degree plan review"})
    notes = client.get("/api/notifications", headers=user_headers)
    assert notes.status_code == 200
    messages = [item["message"] for item in notes.json()]
    assert any("joined Campus Advising" in message for message in messages)
    assert any("Almost ready" in message for message in messages)


def test_duplicate_active_join_is_rejected(client, user_headers):
    service = get_service(client)
    payload = {"service_id": service["id"], "reason_for_visit": "Advising"}
    assert client.post("/api/queues/join", headers=user_headers, json=payload).status_code == 201
    assert client.post("/api/queues/join", headers=user_headers, json=payload).status_code == 409


def test_closed_queue_rejects_join(client, user_headers, admin_headers):
    service = get_service(client, "Tech Help Counter")
    client.post(f"/api/services/{service['id']}/queue/toggle", headers=admin_headers)
    response = client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "Laptop issue"})
    assert response.status_code == 409


def test_leave_queue_creates_history_and_clears_status(client, user_headers):
    service = get_service(client)
    joined = client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "Schedule review"}).json()
    response = client.delete(f"/api/queues/{joined['queue_id']}/leave", headers=user_headers)
    assert response.status_code == 200
    assert client.get("/api/queues/status", headers=user_headers).json() == {"active": False}
    history = client.get("/api/history", headers=user_headers).json()
    assert history[0]["outcome"] == "canceled"
    assert history[0]["service_name"] == "Campus Advising"


def test_admin_views_queue_and_serves_next(client, user_headers, admin_headers):
    service = get_service(client)
    client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "Graduation check"})
    queue = client.get(f"/api/admin/queues/{service['id']}", headers=admin_headers)
    assert queue.status_code == 200
    assert len(queue.json()["entries"]) == 1
    served = client.post(f"/api/admin/queues/{service['id']}/serve-next", headers=admin_headers)
    assert served.status_code == 200
    history = client.get("/api/history", headers=user_headers).json()
    assert history[0]["outcome"] == "served"


def test_serve_empty_queue_returns_conflict(client, admin_headers):
    service = get_service(client)
    assert client.post(f"/api/admin/queues/{service['id']}/serve-next", headers=admin_headers).status_code == 409


def test_positions_are_renumbered_after_admin_removal(client, user_headers, admin_headers):
    service = get_service(client)
    second_headers = register_and_login(client, 2)
    client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "First"})
    client.post("/api/queues/join", headers=second_headers, json={"service_id": service["id"], "reason_for_visit": "Second"})
    queue = client.get(f"/api/admin/queues/{service['id']}", headers=admin_headers).json()
    first_entry = queue["entries"][0]
    assert client.delete(f"/api/admin/queue-entries/{first_entry['entry_id']}", headers=admin_headers).status_code == 200
    updated = client.get(f"/api/admin/queues/{service['id']}", headers=admin_headers).json()
    assert updated["entries"][0]["position"] == 1


def test_admin_can_reorder_queue(client, user_headers, admin_headers):
    service = get_service(client)
    second_headers = register_and_login(client, 3)
    client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "First"})
    client.post("/api/queues/join", headers=second_headers, json={"service_id": service["id"], "reason_for_visit": "Second"})
    queue = client.get(f"/api/admin/queues/{service['id']}", headers=admin_headers).json()
    second_entry = queue["entries"][1]
    moved = client.post(f"/api/admin/queue-entries/{second_entry['entry_id']}/move", headers=admin_headers, json={"position": 1})
    assert moved.status_code == 200
    assert moved.json()["position"] == 1


def test_notification_can_be_marked_viewed(client, user_headers):
    service = get_service(client)
    client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "Question"})
    note = client.get("/api/notifications", headers=user_headers).json()[0]
    response = client.post(f"/api/notifications/{note['id']}/view", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "viewed"


def test_role_checks_protect_user_and_admin_routes(client, user_headers, admin_headers):
    service = get_service(client)
    assert client.get(f"/api/admin/queues/{service['id']}", headers=user_headers).status_code == 403
    assert client.get("/api/queues/status", headers=admin_headers).status_code == 403


def test_admin_dashboard_reads_database_counts(client, user_headers, admin_headers):
    service = get_service(client)
    client.post("/api/queues/join", headers=user_headers, json={"service_id": service["id"], "reason_for_visit": "Count me"})
    dashboard = client.get("/api/admin/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_waiting"] == 1
    assert dashboard.json()["open_queues"] == 4
