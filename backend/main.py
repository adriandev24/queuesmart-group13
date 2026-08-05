"""QueueSmart FastAPI application with SQLite persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db, init_db
from .models import (
    History,
    Notification,
    Queue,
    QueueEntry,
    Service,
    UserCredential,
)
from .schemas import (
    MoveQueueEntryRequest,
    ProfileUpdateRequest,
    QueueJoinRequest,
    ServiceCreateRequest,
    ServiceUpdateRequest,
)

app = FastAPI(title="QueueSmart API", version="4.0.0")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def current_user(
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    db: Session = Depends(get_db),
) -> UserCredential:
    if not x_user_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User email required")
    user = db.scalar(select(UserCredential).where(UserCredential.email == x_user_email.lower()))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user email")
    return user


def require_user(user: UserCredential = Depends(current_user)) -> UserCredential:
    if user.role != "user":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User role required")
    return user


def require_admin(user: UserCredential = Depends(current_user)) -> UserCredential:
    if user.role != "administrator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator role required")
    return user


def _queue_for_service(db: Session, service_id: int) -> Queue | None:
    return db.scalar(select(Queue).where(Queue.service_id == service_id).order_by(Queue.created_at.desc(), Queue.id.desc()))


def _waiting_entries(db: Session, queue_id: int) -> list[QueueEntry]:
    return list(
        db.scalars(
            select(QueueEntry)
            .where(QueueEntry.queue_id == queue_id, QueueEntry.status == "waiting")
            .order_by(QueueEntry.position.asc(), QueueEntry.join_time.asc(), QueueEntry.id.asc())
        )
    )


def _renumber_queue(db: Session, queue_id: int) -> None:
    for index, entry in enumerate(_waiting_entries(db, queue_id), start=1):
        entry.position = index


def _service_dict(db: Session, service: Service) -> dict:
    queue = _queue_for_service(db, service.id)
    waiting = 0
    queue_status = "closed"
    queue_id = None
    if queue:
        waiting = db.scalar(
            select(func.count(QueueEntry.id)).where(QueueEntry.queue_id == queue.id, QueueEntry.status == "waiting")
        ) or 0
        queue_status = queue.status
        queue_id = queue.id
    return {
        "id": service.id,
        "name": service.name,
        "description": service.description,
        "expected_duration": service.expected_duration,
        "priority_level": service.priority_level,
        "queue_id": queue_id,
        "queue_status": queue_status,
        "waiting_count": waiting,
        "created_at": _iso(service.created_at),
    }


def _entry_status_dict(db: Session, entry: QueueEntry) -> dict:
    queue = db.get(Queue, entry.queue_id)
    service = db.get(Service, queue.service_id) if queue else None
    return {
        "entry_id": entry.id,
        "queue_id": entry.queue_id,
        "service_id": service.id if service else None,
        "service_name": service.name if service else "Unknown service",
        "position": entry.position,
        "estimated_wait": entry.position * service.expected_duration if service else 0,
        "status": entry.status,
        "join_time": _iso(entry.join_time),
        "reason_for_visit": entry.reason_for_visit,
    }


def _create_history(db: Session, entry: QueueEntry, outcome: str) -> History:
    queue = db.get(Queue, entry.queue_id)
    completed = entry.completed_at or now_utc()
    joined = entry.join_time
    # SQLite may return a naive datetime even when timezone=True.
    if joined.tzinfo is None:
        joined = joined.replace(tzinfo=timezone.utc)
    if completed.tzinfo is None:
        completed = completed.replace(tzinfo=timezone.utc)
    wait_minutes = max(0, int((completed - joined).total_seconds() // 60))
    record = History(
        user_id=entry.user_id,
        service_id=queue.service_id,
        queue_entry_id=entry.id,
        joined_at=entry.join_time,
        completed_at=entry.completed_at or completed,
        outcome=outcome,
        wait_minutes=wait_minutes,
    )
    db.add(record)
    return record


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(select(1))
    return {"status": "ok", "database": "connected", "storage": "SQLite"}


@app.get("/api/profile")
def get_profile(user: UserCredential = Depends(current_user)) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "full_name": user.profile.full_name,
        "contact_info": user.profile.contact_info,
        "preferences": user.profile.preferences,
    }


@app.put("/api/profile")
def update_profile(
    payload: ProfileUpdateRequest,
    user: UserCredential = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    profile = db.get(UserProfile, user.profile.id)
    profile.full_name = payload.full_name
    profile.contact_info = payload.contact_info
    profile.preferences = payload.preferences
    db.commit()
    return get_profile(user)


@app.get("/api/services")
def list_services(db: Session = Depends(get_db)) -> list[dict]:
    priority_order = {"high": 0, "medium": 1, "low": 2}
    services = list(db.scalars(select(Service).order_by(Service.name.asc())))
    services.sort(key=lambda service: (priority_order[service.priority_level], service.name.lower()))
    return [_service_dict(db, service) for service in services]


@app.post("/api/services", status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreateRequest,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = Service(**payload.model_dump())
    service.queues.append(Queue(status="open"))
    db.add(service)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Service name must be unique") from exc
    db.refresh(service)
    return _service_dict(db, service)


@app.put("/api/services/{service_id}")
def update_service(
    service_id: int,
    payload: ServiceUpdateRequest,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    for field, value in payload.model_dump().items():
        setattr(service, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Service name must be unique") from exc
    return _service_dict(db, service)


@app.post("/api/services/{service_id}/queue/toggle")
def toggle_queue(
    service_id: int,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    queue = _queue_for_service(db, service_id)
    if queue is None:
        queue = Queue(service_id=service_id, status="open")
        db.add(queue)
    else:
        queue.status = "closed" if queue.status == "open" else "open"
    db.commit()
    return _service_dict(db, service)


@app.get("/api/services/{service_id}/estimate")
def estimate_wait(service_id: int, db: Session = Depends(get_db)) -> dict:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    queue = _queue_for_service(db, service_id)
    waiting = len(_waiting_entries(db, queue.id)) if queue else 0
    next_position = waiting + 1
    return {
        "service_id": service.id,
        "service_name": service.name,
        "position": next_position,
        "estimated_wait": next_position * service.expected_duration,
        "queue_status": queue.status if queue else "closed",
    }


@app.post("/api/queues/join", status_code=status.HTTP_201_CREATED)
def join_queue(
    payload: QueueJoinRequest,
    user: UserCredential = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    service = db.get(Service, payload.service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    active = db.scalar(
        select(QueueEntry).where(QueueEntry.user_id == user.id, QueueEntry.status == "waiting")
    )
    if active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already waiting in a queue")
    queue = _queue_for_service(db, service.id)
    if queue is None or queue.status != "open":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Queue is closed")
    position = len(_waiting_entries(db, queue.id)) + 1
    entry = QueueEntry(
        queue_id=queue.id,
        user_id=user.id,
        position=position,
        reason_for_visit=payload.reason_for_visit,
        status="waiting",
    )
    db.add(entry)
    db.flush()
    db.add(Notification(user_id=user.id, message=f"You joined {service.name} at position {position}."))
    if position <= 3:
        db.add(Notification(user_id=user.id, message=f"Almost ready: you are close to being served by {service.name}."))
    db.commit()
    db.refresh(entry)
    return _entry_status_dict(db, entry)


@app.delete("/api/queues/{queue_id}/leave")
def leave_queue(
    queue_id: int,
    user: UserCredential = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    entry = db.scalar(
        select(QueueEntry).where(
            QueueEntry.queue_id == queue_id,
            QueueEntry.user_id == user.id,
            QueueEntry.status == "waiting",
        )
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active queue entry not found")
    entry.status = "canceled"
    entry.completed_at = now_utc()
    queue = db.get(Queue, queue_id)
    service = db.get(Service, queue.service_id)
    _create_history(db, entry, "canceled")
    db.add(Notification(user_id=user.id, message=f"You left the {service.name} queue."))
    db.flush()
    _renumber_queue(db, queue_id)
    db.commit()
    return {"message": "Queue entry canceled", "entry_id": entry.id}


@app.get("/api/queues/status")
def queue_status(
    user: UserCredential = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    entry = db.scalar(
        select(QueueEntry).where(QueueEntry.user_id == user.id, QueueEntry.status == "waiting")
    )
    if entry is None:
        return {"active": False}
    return {"active": True, **_entry_status_dict(db, entry)}


@app.get("/api/notifications")
def notifications(
    user: UserCredential = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    records = list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.timestamp.desc(), Notification.id.desc())
        )
    )
    return [
        {"id": item.id, "message": item.message, "timestamp": _iso(item.timestamp), "status": item.status}
        for item in records
    ]


@app.post("/api/notifications/{notification_id}/view")
def view_notification(
    notification_id: int,
    user: UserCredential = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    item = db.get(Notification, notification_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    item.status = "viewed"
    db.commit()
    return {"id": item.id, "status": item.status}


@app.get("/api/history")
def history(
    user: UserCredential = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    records = list(
        db.scalars(
            select(History)
            .where(History.user_id == user.id)
            .order_by(History.completed_at.desc(), History.id.desc())
        )
    )
    return [
        {
            "id": record.id,
            "service_name": record.service.name,
            "joined_at": _iso(record.joined_at),
            "completed_at": _iso(record.completed_at),
            "outcome": record.outcome,
            "wait_minutes": record.wait_minutes,
        }
        for record in records
    ]


@app.get("/api/admin/dashboard")
def admin_dashboard(
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    services = list_services(db)
    open_queues = sum(1 for service in services if service["queue_status"] == "open")
    total_waiting = sum(service["waiting_count"] for service in services)
    longest_wait = max(
        (service["waiting_count"] * service["expected_duration"] for service in services),
        default=0,
    )
    return {
        "open_queues": open_queues,
        "total_waiting": total_waiting,
        "longest_estimated_wait": longest_wait,
        "services": services,
    }


@app.get("/api/admin/queues/{service_id}")
def admin_queue(
    service_id: int,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    queue = _queue_for_service(db, service_id)
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found")
    entries = _waiting_entries(db, queue.id)
    return {
        "queue_id": queue.id,
        "service_id": service.id,
        "service_name": service.name,
        "status": queue.status,
        "entries": [
            {
                "entry_id": entry.id,
                "user_id": entry.user_id,
                "full_name": entry.user.profile.full_name,
                "email": entry.user.email,
                "position": entry.position,
                "join_time": _iso(entry.join_time),
                "reason_for_visit": entry.reason_for_visit,
            }
            for entry in entries
        ],
    }


@app.post("/api/admin/queues/{service_id}/serve-next")
def serve_next(
    service_id: int,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    queue = _queue_for_service(db, service_id)
    if queue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue not found")
    entries = _waiting_entries(db, queue.id)
    if not entries:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No users are waiting")
    entry = entries[0]
    entry.status = "served"
    entry.completed_at = now_utc()
    _create_history(db, entry, "served")
    db.add(Notification(user_id=entry.user_id, message=f"You were served by {service.name}."))
    db.flush()
    _renumber_queue(db, queue.id)
    db.commit()
    return {"message": "Next user served", "entry_id": entry.id, "user_id": entry.user_id}


@app.delete("/api/admin/queue-entries/{entry_id}")
def remove_queue_entry(
    entry_id: int,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    entry = db.get(QueueEntry, entry_id)
    if entry is None or entry.status != "waiting":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waiting queue entry not found")
    entry.status = "canceled"
    entry.completed_at = now_utc()
    queue = db.get(Queue, entry.queue_id)
    service = db.get(Service, queue.service_id)
    _create_history(db, entry, "canceled")
    db.add(Notification(user_id=entry.user_id, message=f"An administrator removed you from {service.name}."))
    db.flush()
    _renumber_queue(db, entry.queue_id)
    db.commit()
    return {"message": "Queue entry removed", "entry_id": entry.id}


@app.post("/api/admin/queue-entries/{entry_id}/move")
def move_queue_entry(
    entry_id: int,
    payload: MoveQueueEntryRequest,
    _admin: UserCredential = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    entry = db.get(QueueEntry, entry_id)
    if entry is None or entry.status != "waiting":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Waiting queue entry not found")
    entries = _waiting_entries(db, entry.queue_id)
    entries.remove(entry)
    target_index = min(payload.position - 1, len(entries))
    entries.insert(target_index, entry)
    for index, item in enumerate(entries, start=1):
        item.position = index
    db.commit()
    return {"entry_id": entry.id, "position": entry.position}


init_db(seed=True)
