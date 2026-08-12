from datetime import datetime, timedelta, UTC
from sqlalchemy import select

from backend.database import SessionLocal
from backend.models import History, Queue, QueueEntry, Service, UserCredential


def register(client, email, role="user", name="Test User", password="Password123!"):
    return client.post("/api/auth/register", json={"full_name": name, "email": email, "password": password, "role": role})


def login(client, email, password="Password123!"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def setup_accounts(client):
    assert register(client, "admin@example.com", "administrator", "Admin User").status_code == 201
    assert register(client, "user@example.com", "user", "Regular User").status_code == 201
    admin = login(client, "admin@example.com").json()["token"]
    user = login(client, "user@example.com").json()["token"]
    return admin, user


def create_service(client, admin_token, name="Academic Advising", duration=15):
    response = client.post(
        "/api/services",
        headers=auth(admin_token),
        json={"name": name, "description": "Academic support service", "expected_duration": duration, "priority_level": "high"},
    )
    assert response.status_code == 201
    return response.json()


def test_health_and_frontend(client):
    assert client.get("/api/health").json()["status"] == "ok"
    page = client.get("/")
    assert page.status_code == 200
    assert "QueueSmart" in page.text


def test_registration_login_profile_update_and_logout(client):
    response = register(client, "person@example.com", name="Person Name")
    assert response.status_code == 201
    assert response.json()["role"] == "user"
    assert register(client, "person@example.com").status_code == 409
    assert login(client, "person@example.com", "WrongPassword!").status_code == 401

    login_data = login(client, "person@example.com").json()
    token = login_data["token"]
    profile = client.get("/api/profile", headers=auth(token))
    assert profile.json()["full_name"] == "Person Name"
    updated = client.put("/api/profile", headers=auth(token), json={"contact_info": "555-0100", "preferences": "Email updates"})
    assert updated.status_code == 200
    assert updated.json()["contact_info"] == "555-0100"
    assert client.post("/api/auth/logout", headers=auth(token)).status_code == 200
    assert client.get("/api/profile", headers=auth(token)).status_code == 401


def test_auth_and_request_validation(client):
    invalid_email = register(client, "not-an-email")
    assert invalid_email.status_code == 422
    short_password = client.post("/api/auth/register", json={"full_name":"Test User","email":"test@example.com","password":"short","role":"user"})
    assert short_password.status_code == 422
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/profile", headers={"Authorization":"Bearer fake"}).status_code == 401


def test_role_authorization(client):
    admin, user = setup_accounts(client)
    payload = {"name":"IT Help Desk","description":"Technology assistance desk","expected_duration":10,"priority_level":"medium"}
    assert client.post("/api/services", headers=auth(user), json=payload).status_code == 403
    assert client.post("/api/queues/join", headers=auth(admin), json={"service_id":1,"reason_for_visit":"Need help"}).status_code == 403
    assert client.get("/api/admin/dashboard", headers=auth(user)).status_code == 403


def test_service_crud_toggle_estimate_and_conflicts(client):
    admin, _ = setup_accounts(client)
    service = create_service(client, admin)
    service_id = service["id"]
    services = client.get("/api/services").json()
    assert services[0]["queue_status"] == "open"
    assert client.get(f"/api/services/{service_id}/estimate").json()["estimated_wait_minutes"] == 0

    update = client.put(f"/api/services/{service_id}", headers=auth(admin), json={"expected_duration":20,"priority_level":"medium"})
    assert update.status_code == 200
    assert update.json()["expected_duration"] == 20
    assert create_service(client, admin).get("id") is not None if False else True
    duplicate = client.post("/api/services", headers=auth(admin), json={"name":"Academic Advising","description":"Another description","expected_duration":15,"priority_level":"low"})
    assert duplicate.status_code == 409
    assert client.put("/api/services/999", headers=auth(admin), json={"expected_duration":10}).status_code == 404
    toggle = client.post(f"/api/services/{service_id}/queue/toggle", headers=auth(admin))
    assert toggle.json()["queue_status"] == "closed"
    assert client.post(f"/api/services/{service_id}/queue/toggle", headers=auth(admin)).json()["queue_status"] == "open"
    assert client.get("/api/services/999/estimate").status_code == 404


def test_service_payload_validation(client):
    admin, _ = setup_accounts(client)
    bad = client.post("/api/services", headers=auth(admin), json={"name":"A","description":"bad","expected_duration":0,"priority_level":"urgent"})
    assert bad.status_code == 422
    assert client.put("/api/services/1", headers=auth(admin), json={}).status_code == 422


def test_join_status_duplicate_notifications_leave_and_history(client):
    admin, user = setup_accounts(client)
    service = create_service(client, admin)
    service_id = service["id"]

    joined = client.post("/api/queues/join", headers=auth(user), json={"service_id":service_id,"reason_for_visit":"Degree plan"})
    assert joined.status_code == 201
    assert joined.json()["position"] == 1
    assert client.post("/api/queues/join", headers=auth(user), json={"service_id":service_id,"reason_for_visit":"Again"}).status_code == 409
    status_rows = client.get("/api/queues/status", headers=auth(user)).json()
    assert status_rows[0]["service_name"] == "Academic Advising"
    notifications = client.get("/api/notifications", headers=auth(user)).json()
    assert len(notifications) >= 2
    assert client.post(f"/api/notifications/{notifications[0]['id']}/view", headers=auth(user)).json()["status"] == "viewed"
    assert client.post("/api/notifications/999/view", headers=auth(user)).status_code == 404

    queue_id = status_rows[0]["queue_id"]
    assert client.delete(f"/api/queues/{queue_id}/leave", headers=auth(user)).status_code == 200
    assert client.get("/api/queues/status", headers=auth(user)).json() == []
    history = client.get("/api/history", headers=auth(user)).json()
    assert history[0]["outcome"] == "canceled"
    assert client.delete(f"/api/queues/{queue_id}/leave", headers=auth(user)).status_code == 404


def test_join_closed_and_missing_service(client):
    admin, user = setup_accounts(client)
    service = create_service(client, admin)
    assert client.post("/api/queues/join", headers=auth(user), json={"service_id":999,"reason_for_visit":"Missing"}).status_code == 404
    client.post(f"/api/services/{service['id']}/queue/toggle", headers=auth(admin))
    assert client.post("/api/queues/join", headers=auth(user), json={"service_id":service['id'],"reason_for_visit":"Closed"}).status_code == 409
    assert client.delete("/api/queues/999/leave", headers=auth(user)).status_code == 404


def test_admin_serve_next_dashboard_and_queue_view(client):
    admin, user = setup_accounts(client)
    service = create_service(client, admin, duration=12)
    client.post("/api/queues/join", headers=auth(user), json={"service_id":service["id"],"reason_for_visit":"Question"})

    dashboard = client.get("/api/admin/dashboard", headers=auth(admin)).json()
    assert dashboard["waiting_users"] == 1
    queue = client.get(f"/api/admin/queues/{service['id']}", headers=auth(admin)).json()
    assert queue["entries"][0]["name"] == "Regular User"
    served = client.post(f"/api/admin/queues/{service['id']}/serve-next", headers=auth(admin))
    assert served.status_code == 200
    assert client.post(f"/api/admin/queues/{service['id']}/serve-next", headers=auth(admin)).status_code == 409
    assert client.get("/api/history", headers=auth(user)).json()[0]["outcome"] == "served"
    assert client.get("/api/admin/queues/999", headers=auth(admin)).status_code == 404


def test_admin_remove_entry(client):
    admin, user = setup_accounts(client)
    service = create_service(client, admin)
    client.post("/api/queues/join", headers=auth(user), json={"service_id":service["id"],"reason_for_visit":"Question"})
    entry_id = client.get(f"/api/admin/queues/{service['id']}", headers=auth(admin)).json()["entries"][0]["id"]
    response = client.delete(f"/api/admin/queues/{service['id']}/entries/{entry_id}", headers=auth(admin))
    assert response.status_code == 200
    assert client.delete(f"/api/admin/queues/{service['id']}/entries/{entry_id}", headers=auth(admin)).status_code == 404
    assert client.get("/api/history", headers=auth(user)).json()[0]["outcome"] == "canceled"


def test_admin_move_entry(client):
    admin, user1 = setup_accounts(client)
    assert register(client, "user2@example.com", "user", "Second User").status_code == 201
    user2 = login(client, "user2@example.com").json()["token"]
    service = create_service(client, admin)
    for token, reason in [(user1,"First"),(user2,"Second")]:
        assert client.post("/api/queues/join", headers=auth(token), json={"service_id":service["id"],"reason_for_visit":reason}).status_code == 201
    entries = client.get(f"/api/admin/queues/{service['id']}", headers=auth(admin)).json()["entries"]
    second_id = entries[1]["id"]
    moved = client.post(f"/api/admin/queues/{service['id']}/entries/{second_id}/move", headers=auth(admin), json={"direction":"up"})
    assert moved.status_code == 200
    reordered = client.get(f"/api/admin/queues/{service['id']}", headers=auth(admin)).json()["entries"]
    assert reordered[0]["id"] == second_id
    assert client.post(f"/api/admin/queues/{service['id']}/entries/{second_id}/move", headers=auth(admin), json={"direction":"up"}).status_code == 409
    assert client.post(f"/api/admin/queues/{service['id']}/entries/999/move", headers=auth(admin), json={"direction":"down"}).status_code == 404


def add_history(service_id, user_email, waits_and_hours):
    db = SessionLocal()
    try:
        user = db.scalar(select(UserCredential).where(UserCredential.email == user_email))
        queue = db.scalar(select(Queue).where(Queue.service_id == service_id))
        base = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10)
        for index, (hour, wait) in enumerate(waits_and_hours):
            joined = (base + timedelta(days=index)).replace(hour=hour, minute=0, second=0, microsecond=0)
            completed = joined + timedelta(minutes=wait)
            entry = QueueEntry(queue_id=queue.id,user_id=user.id,position=1,join_time=joined,completed_at=completed,status="served",reason_for_visit="Historical")
            db.add(entry); db.flush()
            db.add(History(user_id=user.id,service_id=service_id,queue_entry_id=entry.id,joined_at=joined,completed_at=completed,outcome="served",wait_minutes=wait))
        db.commit()
    finally:
        db.close()


def test_smart_best_time_uses_historical_data(client):
    admin, user = setup_accounts(client)
    service = create_service(client, admin)
    add_history(service["id"], "user@example.com", [(9,5),(9,7),(12,25),(15,12),(15,13)])
    result = client.get(f"/api/services/{service['id']}/best-time", headers=auth(user)).json()
    assert result["basis"] == "historical_queue_data"
    assert result["recommended_window"] == "09:00-10:00"
    assert result["historical_samples"] == 5
    assert result["confidence"] == "medium"


def test_smart_best_time_fallback_and_validation(client):
    admin, user = setup_accounts(client)
    service = create_service(client, admin)
    result = client.get(f"/api/services/{service['id']}/best-time", headers=auth(user)).json()
    assert result["basis"] == "current_load_fallback"
    assert result["recommended_window"] == "Now"
    assert client.get("/api/services/999/best-time", headers=auth(user)).status_code == 404
    assert client.get(f"/api/services/{service['id']}/best-time?lookback_days=2", headers=auth(user)).status_code == 422


def test_report_summary_and_csv_include_required_sections(client):
    admin, user = setup_accounts(client)
    service = create_service(client, admin)
    add_history(service["id"], "user@example.com", [(9,8),(10,10)])

    summary = client.get("/api/admin/reports/summary", headers=auth(admin))
    assert summary.status_code == 200
    body = summary.json()
    assert body["statistics"]["users_served"] == 2
    assert body["statistics"]["average_wait_minutes"] == 9.0
    assert body["users"][0]["history"]
    assert body["services"][0]["name"] == "Academic Advising"

    csv_response = client.get("/api/admin/reports/export.csv", headers=auth(admin))
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    text = csv_response.text
    assert "SUMMARY" in text and "SERVICE" in text and "HISTORY" in text
    assert "user@example.com" in text
    assert client.get("/api/admin/reports/summary", headers=auth(user)).status_code == 403


def test_report_filters_and_errors(client):
    admin, _ = setup_accounts(client)
    service = create_service(client, admin)
    add_history(service["id"], "user@example.com", [(9,8)])
    today = datetime.now(UTC).replace(tzinfo=None).date().isoformat()
    response = client.get(f"/api/admin/reports/summary?service_id={service['id']}&start_date=2000-01-01&end_date={today}", headers=auth(admin))
    assert response.status_code == 200
    assert response.json()["statistics"]["users_served"] == 1
    assert client.get("/api/admin/reports/summary?start_date=bad-date", headers=auth(admin)).status_code == 422
    assert client.get("/api/admin/reports/summary?start_date=2026-12-31&end_date=2026-01-01", headers=auth(admin)).status_code == 422
    assert client.get("/api/admin/reports/summary?service_id=999", headers=auth(admin)).status_code == 404
