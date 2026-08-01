
def test_services_are_retrieved_from_database(client):
    response = client.get("/api/services")
    assert response.status_code == 200
    names = {service["name"] for service in response.json()}
    assert "Campus Advising" in names
    assert all("queue_status" in service for service in response.json())


def test_admin_can_create_and_retrieve_service(client, admin_headers):
    payload = {"name": "Registrar Desk", "description": "Registration and enrollment support.", "expected_duration": 12, "priority_level": "medium"}
    response = client.post("/api/services", headers=admin_headers, json=payload)
    assert response.status_code == 201
    service_id = response.json()["id"]
    services = client.get("/api/services").json()
    assert any(item["id"] == service_id and item["name"] == "Registrar Desk" for item in services)


def test_regular_user_cannot_create_service(client, user_headers):
    payload = {"name": "Unauthorized Service", "description": "Should not be created.", "expected_duration": 10, "priority_level": "low"}
    response = client.post("/api/services", headers=user_headers, json=payload)
    assert response.status_code == 403


def test_service_validation_rejects_bad_data(client, admin_headers):
    response = client.post("/api/services", headers=admin_headers, json={"name": "X", "description": "bad", "expected_duration": 0, "priority_level": "urgent"})
    assert response.status_code == 422


def test_service_name_must_be_unique(client, admin_headers):
    payload = {"name": "Campus Advising", "description": "Duplicate service name.", "expected_duration": 10, "priority_level": "low"}
    response = client.post("/api/services", headers=admin_headers, json=payload)
    assert response.status_code == 409


def test_admin_can_update_service(client, admin_headers):
    services = client.get("/api/services").json()
    service_id = next(item["id"] for item in services if item["name"] == "ID Card Office")
    payload = {"name": "ID Card Center", "description": "Updated identification card services.", "expected_duration": 10, "priority_level": "high"}
    response = client.put(f"/api/services/{service_id}", headers=admin_headers, json=payload)
    assert response.status_code == 200
    assert response.json()["name"] == "ID Card Center"
    assert response.json()["expected_duration"] == 10


def test_update_missing_service_returns_404(client, admin_headers):
    payload = {"name": "Missing", "description": "A valid description.", "expected_duration": 10, "priority_level": "low"}
    assert client.put("/api/services/9999", headers=admin_headers, json=payload).status_code == 404


def test_wait_estimate_uses_position_times_duration(client):
    service = next(item for item in client.get("/api/services").json() if item["name"] == "Campus Advising")
    estimate = client.get(f"/api/services/{service['id']}/estimate")
    assert estimate.status_code == 200
    assert estimate.json()["position"] == 1
    assert estimate.json()["estimated_wait"] == service["expected_duration"]


def test_queue_toggle_persists(client, admin_headers):
    service = client.get("/api/services").json()[0]
    first = client.post(f"/api/services/{service['id']}/queue/toggle", headers=admin_headers)
    assert first.status_code == 200
    assert first.json()["queue_status"] == "closed"
    second = client.get("/api/services").json()
    assert next(s for s in second if s["id"] == service["id"])["queue_status"] == "closed"
