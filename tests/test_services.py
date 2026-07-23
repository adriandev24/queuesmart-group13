def test_lists_services_from_backend(client):
    response = client.get("/api/services")
    assert response.status_code == 200
    services = response.json()["services"]
    assert len(services) == 4
    assert services[0]["name"] == "Campus Advising"
    assert "queue_length" in services[0]


def test_admin_creates_service(client, admin_headers):
    response = client.post(
        "/api/services",
        headers=admin_headers,
        json={
            "name": "Veteran Services",
            "description": "Help for veterans and military-connected students.",
            "expected_duration": 12,
            "priority_level": "high",
        },
    )
    assert response.status_code == 201
    service = response.json()["service"]
    assert service["id"] == 5
    assert service["queue_length"] == 0


def test_service_validation_rejects_bad_fields(client, admin_headers):
    response = client.post(
        "/api/services",
        headers=admin_headers,
        json={"name": "A", "description": "bad", "expected_duration": "long", "priority_level": "urgent"},
    )
    assert response.status_code == 422
    fields = {item["field"] for item in response.json()["details"]}
    assert {"name", "description", "expected_duration", "priority_level"}.issubset(fields)


def test_user_cannot_create_service(client, user_headers):
    response = client.post(
        "/api/services",
        headers=user_headers,
        json={
            "name": "Career Center",
            "description": "Career counseling and resume help.",
            "expected_duration": 15,
            "priority_level": "medium",
        },
    )
    assert response.status_code == 403


def test_admin_updates_service(client, admin_headers):
    response = client.put(
        "/api/services/1",
        headers=admin_headers,
        json={
            "name": "Academic Advising",
            "description": "Updated advising service description.",
            "expected_duration": 9,
            "priority_level": "high",
        },
    )
    assert response.status_code == 200
    service = response.json()["service"]
    assert service["name"] == "Academic Advising"
    assert service["expected_duration"] == 9
    assert service["priority_level"] == "high"


def test_update_missing_service_returns_404(client, admin_headers):
    response = client.put(
        "/api/services/999",
        headers=admin_headers,
        json={
            "name": "Missing Service",
            "description": "This service does not exist.",
            "expected_duration": 9,
            "priority_level": "low",
        },
    )
    assert response.status_code == 404
