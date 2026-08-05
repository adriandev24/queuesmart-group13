import backend.database as database
from backend.models import SessionToken, UserCredential


def test_health_reports_database_connected(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected", "storage": "SQLite"}


def test_register_persists_hashed_password(client):
    payload = {
        "full_name": "New Student",
        "email": "new.student@example.com",
        "password": "StrongPass9!",
        "role": "user",
        "contact_info": "555-0102",
        "preferences": "Email",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    with database.SessionLocal() as db:
        user = db.query(UserCredential).filter_by(email="new.student@example.com").one()
        assert user.password_hash != payload["password"]
        assert user.password_hash.startswith("pbkdf2_sha256$")
        assert user.profile.full_name == "New Student"


def test_duplicate_email_is_rejected(client):
    payload = {"full_name": "Duplicate", "email": "user@queuesmart.example", "password": "Password9!", "role": "user"}
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 409


def test_registration_validates_lengths_and_types(client):
    response = client.post("/api/auth/register", json={"full_name": "A", "email": "bad", "password": "short", "role": "invalid"})
    assert response.status_code == 422


def test_login_success_and_profile(client, user_headers):
    response = client.get("/api/profile", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "user@queuesmart.example"
    assert response.json()["role"] == "user"


def test_login_rejects_wrong_password(client):
    response = client.post("/api/auth/login", json={"email": "user@queuesmart.example", "password": "WrongPass9!"})
    assert response.status_code == 401


def test_login_creates_persistent_session_token(client, user_headers):
    with database.SessionLocal() as db:
        token_value = user_headers["Authorization"].removeprefix("Bearer ")
        session = db.query(SessionToken).filter_by(token=token_value).one_or_none()
        assert session is not None
        assert session.user.email == "user@queuesmart.example"


def test_missing_and_invalid_tokens_are_rejected(client):
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_profile_update_is_persistent(client, user_headers):
    response = client.put("/api/profile", headers=user_headers, json={"full_name": "Updated Student", "contact_info": "555-7777", "preferences": "Text"})
    assert response.status_code == 200
    second = client.get("/api/profile", headers=user_headers)
    assert second.json()["full_name"] == "Updated Student"
    assert second.json()["contact_info"] == "555-7777"


def test_logout_invalidates_session(client, user_headers):
    assert client.post("/api/auth/logout", headers=user_headers).status_code == 200
    assert client.get("/api/profile", headers=user_headers).status_code == 401
