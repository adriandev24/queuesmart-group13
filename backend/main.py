from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime, time
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db, init_db
from .logic import (
    best_time_recommendation,
    build_report_data,
    complete_entry,
    create_notification,
    get_service_queue,
    notify_close_users,
    renumber_queue,
    service_snapshot,
    waiting_entries,
)
from .models import History, Notification, Queue, QueueEntry, Service, SessionToken, UserCredential, UserProfile
from .schemas import LoginRequest, MoveRequest, ProfileUpdate, QueueJoinRequest, RegisterRequest, ServiceCreate, ServiceUpdate
from .security import hash_password, new_session_token, verify_password

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="QueueSmart API", version="5.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")
    return token


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> UserCredential:
    token_value = _extract_bearer(authorization)
    session_token = db.get(SessionToken, token_value)
    if not session_token:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.get(UserCredential, session_token.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def require_user(user: UserCredential = Depends(get_current_user)) -> UserCredential:
    if user.role != "user":
        raise HTTPException(status_code=403, detail="Regular-user access required")
    return user


def require_admin(user: UserCredential = Depends(get_current_user)) -> UserCredential:
    if user.role != "administrator":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def _parse_start(date_text: str | None) -> datetime | None:
    if not date_text:
        return None
    try:
        return datetime.combine(datetime.strptime(date_text, "%Y-%m-%d").date(), time.min)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="start_date must use YYYY-MM-DD") from exc


def _parse_end(date_text: str | None) -> datetime | None:
    if not date_text:
        return None
    try:
        return datetime.combine(datetime.strptime(date_text, "%Y-%m-%d").date(), time.max)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="end_date must use YYYY-MM-DD") from exc


def _validate_report_filters(db: Session, start_date: str | None, end_date: str | None, service_id: int | None):
    start = _parse_start(start_date)
    end = _parse_end(end_date)
    today = datetime.now().date()
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="start_date cannot be after end_date")
    if start and start.date() > today:
        raise HTTPException(status_code=422, detail="start_date cannot be in the future")
    if end and end.date() > today:
        raise HTTPException(status_code=422, detail="end_date cannot be in the future")
    if service_id and not db.get(Service, service_id):
        raise HTTPException(status_code=404, detail="Service not found")
    return start, end


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "application": "QueueSmart"}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.scalar(select(UserCredential).where(UserCredential.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="Email is already registered")

    user = UserCredential(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, full_name=payload.full_name))
    db.commit()
    return {"id": user.id, "email": user.email, "role": user.role, "full_name": payload.full_name}


@app.post("/api/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(UserCredential).where(UserCredential.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token_value = new_session_token()
    db.add(SessionToken(token=token_value, user_id=user.id))
    db.commit()
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    return {
        "token": token_value,
        "role": user.role,
        "email": user.email,
        "full_name": profile.full_name if profile else "",
    }


@app.post("/api/auth/logout")
def logout(
    authorization: Annotated[str | None, Header()] = None,
    user: UserCredential = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token_value = _extract_bearer(authorization)
    token = db.get(SessionToken, token_value)
    if token and token.user_id == user.id:
        db.delete(token)
        db.commit()
    return {"message": "Logged out"}


@app.get("/api/profile")
def get_profile(user: UserCredential = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "full_name": profile.full_name if profile else "",
        "contact_info": profile.contact_info if profile else None,
        "preferences": profile.preferences if profile else None,
    }


@app.put("/api/profile")
def update_profile(
    payload: ProfileUpdate,
    user: UserCredential = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return {"full_name": profile.full_name, "contact_info": profile.contact_info, "preferences": profile.preferences}


@app.get("/api/services")
def list_services(db: Session = Depends(get_db)):
    services = list(db.scalars(select(Service).order_by(Service.name)).all())
    return [service_snapshot(db, service) for service in services]


@app.post("/api/services", status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(Service).where(Service.name == payload.name)):
        raise HTTPException(status_code=409, detail="Service name already exists")
    service = Service(**payload.model_dump())
    db.add(service)
    db.flush()
    db.add(Queue(service_id=service.id, status="open"))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Service could not be created") from exc
    db.refresh(service)
    return service_snapshot(db, service)


@app.put("/api/services/{service_id}")
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if payload.name and db.scalar(select(Service).where(Service.name == payload.name, Service.id != service_id)):
        raise HTTPException(status_code=409, detail="Service name already exists")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return service_snapshot(db, service)


@app.post("/api/services/{service_id}/queue/toggle")
def toggle_queue(
    service_id: int,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    queue = get_service_queue(db, service_id)
    if not queue:
        queue = Queue(service_id=service_id, status="open")
        db.add(queue)
    else:
        queue.status = "closed" if queue.status == "open" else "open"
    db.commit()
    db.refresh(queue)
    return {"service_id": service_id, "queue_status": queue.status}


@app.get("/api/services/{service_id}/estimate")
def wait_estimate(service_id: int, db: Session = Depends(get_db)):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    queue = get_service_queue(db, service_id)
    waiting_count = len(waiting_entries(db, queue.id)) if queue else 0
    return {
        "service_id": service.id,
        "waiting_count": waiting_count,
        "estimated_wait_minutes": waiting_count * service.expected_duration,
    }


@app.get("/api/services/{service_id}/best-time")
def best_time(
    service_id: int,
    lookback_days: int = Query(default=90, ge=7, le=365),
    _user: UserCredential = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return best_time_recommendation(db, service, lookback_days)


@app.post("/api/queues/join", status_code=status.HTTP_201_CREATED)
def join_queue(
    payload: QueueJoinRequest,
    user: UserCredential = Depends(require_user),
    db: Session = Depends(get_db),
):
    service = db.get(Service, payload.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    queue = get_service_queue(db, service.id)
    if not queue or queue.status != "open":
        raise HTTPException(status_code=409, detail="Queue is closed")

    duplicate = db.scalar(
        select(QueueEntry).where(
            QueueEntry.queue_id == queue.id,
            QueueEntry.user_id == user.id,
            QueueEntry.status == "waiting",
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="You are already waiting in this queue")

    position = len(waiting_entries(db, queue.id)) + 1
    entry = QueueEntry(
        queue_id=queue.id,
        user_id=user.id,
        position=position,
        reason_for_visit=payload.reason_for_visit,
    )
    db.add(entry)
    db.flush()
    create_notification(db, user.id, f"You joined {service.name}. Current position: {position}.")
    if position <= 2:
        create_notification(db, user.id, f"You are close to being served for {service.name}.")
    db.commit()
    return {
        "queue_entry_id": entry.id,
        "service_id": service.id,
        "service_name": service.name,
        "position": position,
        "estimated_wait_minutes": position * service.expected_duration,
        "status": entry.status,
    }


@app.delete("/api/queues/{queue_id}/leave")
def leave_queue(
    queue_id: int,
    user: UserCredential = Depends(require_user),
    db: Session = Depends(get_db),
):
    queue = db.get(Queue, queue_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    entry = db.scalar(
        select(QueueEntry).where(
            QueueEntry.queue_id == queue_id,
            QueueEntry.user_id == user.id,
            QueueEntry.status == "waiting",
        )
    )
    if not entry:
        raise HTTPException(status_code=404, detail="No active queue entry found")
    service = db.get(Service, queue.service_id)
    complete_entry(db, entry, queue.service_id, "canceled", f"You left the {service.name} queue.")
    renumber_queue(db, queue_id)
    notify_close_users(db, queue_id, service.name)
    db.commit()
    return {"message": "Queue entry canceled"}


@app.get("/api/queues/status")
def queue_status(user: UserCredential = Depends(require_user), db: Session = Depends(get_db)):
    entries = list(
        db.scalars(
            select(QueueEntry).where(QueueEntry.user_id == user.id, QueueEntry.status == "waiting").order_by(QueueEntry.join_time)
        ).all()
    )
    result = []
    for entry in entries:
        queue = db.get(Queue, entry.queue_id)
        service = db.get(Service, queue.service_id) if queue else None
        result.append(
            {
                "queue_id": entry.queue_id,
                "queue_entry_id": entry.id,
                "service_id": service.id if service else None,
                "service_name": service.name if service else "Unknown service",
                "position": entry.position,
                "status": entry.status,
                "estimated_wait_minutes": entry.position * service.expected_duration if service else 0,
                "joined_at": entry.join_time.isoformat(),
            }
        )
    return result


@app.get("/api/notifications")
def notifications(user: UserCredential = Depends(require_user), db: Session = Depends(get_db)):
    rows = list(
        db.scalars(
            select(Notification).where(Notification.user_id == user.id).order_by(Notification.timestamp.desc())
        ).all()
    )
    return [
        {"id": row.id, "message": row.message, "timestamp": row.timestamp.isoformat(), "status": row.status}
        for row in rows
    ]


@app.post("/api/notifications/{notification_id}/view")
def view_notification(
    notification_id: int,
    user: UserCredential = Depends(require_user),
    db: Session = Depends(get_db),
):
    row = db.get(Notification, notification_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.status = "viewed"
    db.commit()
    return {"id": row.id, "status": row.status}


@app.get("/api/history")
def history(user: UserCredential = Depends(require_user), db: Session = Depends(get_db)):
    rows = list(db.scalars(select(History).where(History.user_id == user.id).order_by(History.completed_at.desc())).all())
    result = []
    for row in rows:
        service = db.get(Service, row.service_id)
        result.append(
            {
                "id": row.id,
                "service_name": service.name if service else "Unknown service",
                "joined_at": row.joined_at.isoformat(),
                "completed_at": row.completed_at.isoformat(),
                "wait_minutes": row.wait_minutes,
                "outcome": row.outcome,
            }
        )
    return result


@app.get("/api/admin/dashboard")
def admin_dashboard(_admin: UserCredential = Depends(require_admin), db: Session = Depends(get_db)):
    services = list(db.scalars(select(Service).order_by(Service.name)).all())
    snapshots = [service_snapshot(db, service) for service in services]
    return {
        "service_count": len(snapshots),
        "open_queues": sum(row["queue_status"] == "open" for row in snapshots),
        "waiting_users": sum(row["waiting_count"] for row in snapshots),
        "services": snapshots,
    }


@app.get("/api/admin/queues/{service_id}")
def admin_queue(service_id: int, _admin: UserCredential = Depends(require_admin), db: Session = Depends(get_db)):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    queue = get_service_queue(db, service_id)
    if not queue:
        return {"service": service.name, "queue_id": None, "status": "closed", "entries": []}
    entries = waiting_entries(db, queue.id)
    output = []
    for entry in entries:
        customer = db.get(UserCredential, entry.user_id)
        profile = db.scalar(select(UserProfile).where(UserProfile.user_id == entry.user_id))
        output.append(
            {
                "id": entry.id,
                "position": entry.position,
                "user_id": entry.user_id,
                "name": profile.full_name if profile else customer.email,
                "email": customer.email if customer else "",
                "reason_for_visit": entry.reason_for_visit,
                "joined_at": entry.join_time.isoformat(),
            }
        )
    return {"service": service.name, "queue_id": queue.id, "status": queue.status, "entries": output}


@app.post("/api/admin/queues/{service_id}/serve-next")
def serve_next(service_id: int, _admin: UserCredential = Depends(require_admin), db: Session = Depends(get_db)):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    queue = get_service_queue(db, service_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")
    entries = waiting_entries(db, queue.id)
    if not entries:
        raise HTTPException(status_code=409, detail="No users are waiting")
    entry = entries[0]
    complete_entry(db, entry, service_id, "served", f"You were served for {service.name}.")
    renumber_queue(db, queue.id)
    notify_close_users(db, queue.id, service.name)
    db.commit()
    return {"served_entry_id": entry.id, "message": "Next user served"}


@app.delete("/api/admin/queues/{service_id}/entries/{entry_id}")
def remove_entry(
    service_id: int,
    entry_id: int,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = db.get(Service, service_id)
    queue = get_service_queue(db, service_id)
    entry = db.get(QueueEntry, entry_id)
    if not service or not queue or not entry or entry.queue_id != queue.id or entry.status != "waiting":
        raise HTTPException(status_code=404, detail="Waiting queue entry not found")
    complete_entry(db, entry, service_id, "canceled", f"An administrator removed you from {service.name}.")
    renumber_queue(db, queue.id)
    notify_close_users(db, queue.id, service.name)
    db.commit()
    return {"message": "Queue entry removed"}


@app.post("/api/admin/queues/{service_id}/entries/{entry_id}/move")
def move_entry(
    service_id: int,
    entry_id: int,
    payload: MoveRequest,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
):
    service = db.get(Service, service_id)
    queue = get_service_queue(db, service_id)
    if not service or not queue:
        raise HTTPException(status_code=404, detail="Service queue not found")
    entries = waiting_entries(db, queue.id)
    index = next((i for i, entry in enumerate(entries) if entry.id == entry_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Waiting queue entry not found")

    target = index - 1 if payload.direction == "up" else index + 1
    if target < 0 or target >= len(entries):
        raise HTTPException(status_code=409, detail="Queue entry cannot move farther in that direction")
    entries[index].position, entries[target].position = entries[target].position, entries[index].position
    db.flush()
    renumber_queue(db, queue.id)
    notify_close_users(db, queue.id, service.name)
    db.commit()
    return {"message": "Queue order updated"}


@app.get("/api/admin/reports/summary")
def report_summary(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    service_id: int | None = Query(default=None, gt=0),
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
):
    start, end = _validate_report_filters(db, start_date, end_date, service_id)
    return build_report_data(db, start, end, service_id)


@app.get("/api/admin/reports/export.csv")
def export_report_csv(
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    service_id: int | None = Query(default=None, gt=0),
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
):
    start, end = _validate_report_filters(db, start_date, end_date, service_id)
    report = build_report_data(db, start, end, service_id)

    buffer = io.StringIO()
    fields = [
        "record_type",
        "user_email",
        "user_name",
        "service_name",
        "service_description",
        "priority_level",
        "expected_duration",
        "queue_status",
        "current_waiting",
        "joined_at",
        "completed_at",
        "outcome",
        "wait_minutes",
        "participation_count",
        "total_participations",
        "users_served",
        "canceled",
        "average_wait_minutes",
        "unique_customers",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    stats = report["statistics"]
    writer.writerow(
        {
            "record_type": "SUMMARY",
            "current_waiting": stats["current_waiting"],
            "total_participations": stats["total_participations"],
            "users_served": stats["users_served"],
            "canceled": stats["canceled"],
            "average_wait_minutes": stats["average_wait_minutes"],
            "unique_customers": stats["unique_customers"],
        }
    )
    for service in report["services"]:
        writer.writerow(
            {
                "record_type": "SERVICE",
                "service_name": service["name"],
                "service_description": service["description"],
                "priority_level": service["priority_level"],
                "expected_duration": service["expected_duration"],
                "queue_status": service["queue_status"],
                "current_waiting": service["current_waiting"],
                "users_served": service["served"],
                "canceled": service["canceled"],
            }
        )
    for customer in report["users"]:
        if not customer["history"]:
            writer.writerow(
                {
                    "record_type": "CUSTOMER",
                    "user_email": customer["email"],
                    "user_name": customer["full_name"],
                    "participation_count": customer["participation_count"],
                }
            )
        for item in customer["history"]:
            writer.writerow(
                {
                    "record_type": "HISTORY",
                    "user_email": customer["email"],
                    "user_name": customer["full_name"],
                    "service_name": item["service"],
                    "joined_at": item["joined_at"],
                    "completed_at": item["completed_at"],
                    "outcome": item["outcome"],
                    "wait_minutes": item["wait_minutes"],
                    "participation_count": customer["participation_count"],
                }
            )

    filename = f"queuesmart_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    data = buffer.getvalue().encode("utf-8")
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
