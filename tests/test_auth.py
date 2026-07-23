def test_registers_user_and_returns_token(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Taylor Morgan",
            "email": "taylor@example.com",
            "password": "StrongPass123",
            "role": "user",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["user"]["email"] == "taylor@example.com"
    assert payload["user"]["role"] == "user"
    assert payload["token"]


def test_rejects_duplicate_registration(client):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Another User",
            "email": "user@queuesmartapp.com",
            "password": "StrongPass123",
            "role": "user",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["error"]


def test_registration_validates_lengths_types_and_email(client):
    response = client.post(
        "/api/auth/register",
        json={"full_name": "1", "email": "not-an-email", "password": "short", "role": "manager"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == "Validation failed"
    fields = {item["field"] for item in payload["details"]}
    assert {"full_name", "email", "password", "role"}.issubset(fields)


def test_login_authenticates_user(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "user@queuesmartapp.com", "password": "UserPass123", "role": "user"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["full_name"] == "Demo User"


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "user@queuesmartapp.com", "password": "WrongPass123", "role": "user"},
    )
    assert response.status_code == 401


def test_login_rejects_role_mismatch(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "user@queuesmartapp.com", "password": "UserPass123", "role": "administrator"},
    )
    assert response.status_code == 403


def test_protected_route_requires_token(client):
    response = client.get("/api/dashboard/user")
    assert response.status_code == 401
