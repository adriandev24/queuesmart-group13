def test_health_endpoint_reports_in_memory_storage(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "storage": "in-memory"}


def test_frontend_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "QueueSmart" in response.text


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/dashboard/user",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
