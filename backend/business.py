from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from .security import hash_password, verify_password
from .store import InMemoryStore


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {key: user[key] for key in ("id", "full_name", "email", "role")}


def public_service(service: dict[str, Any], queue_length: int = 0) -> dict[str, Any]:
    return {**service, "queue_length": queue_length}


def register_user(data: Any, db: InMemoryStore) -> tuple[dict[str, Any], str]:
    if db.find_user_by_email(str(data.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user = {
        "id": db._next_user_id,
        "full_name": data.full_name,
        "email": str(data.email).lower(),
        "password_hash": hash_password(data.password),
        "role": data.role,
    }
    db._next_user_id += 1
    db.users.append(user)
    token = db.create_session(user["id"])
    return public_user(user), token


def login_user(data: Any, db: InMemoryStore) -> tuple[dict[str, Any], str]:
    user = db.find_user_by_email(str(data.email))
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user["role"] != data.role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The selected role does not match this account")
    token = db.create_session(user["id"])
    return public_user(user), token


def list_services(db: InMemoryStore) -> list[dict[str, Any]]:
    return [public_service(service, len(db.ordered_queue(service["id"]))) for service in db.services]


def create_service(data: Any, db: InMemoryStore) -> dict[str, Any]:
    if any(service["name"].lower() == data.name.lower() for service in db.services):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A service with this name already exists")
    service = {
        "id": db._next_service_id,
        "name": data.name,
        "description": data.description,
        "expected_duration": data.expected_duration,
        "priority_level": data.priority_level,
        "is_open": True,
    }
    db._next_service_id += 1
    db.services.append(service)
    return public_service(service, 0)


def update_service(service_id: int, data: Any, db: InMemoryStore) -> dict[str, Any]:
    service = db.find_service(service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    duplicate = next(
        (item for item in db.services if item["id"] != service_id and item["name"].lower() == data.name.lower()),
        None,
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A service with this name already exists")
    service.update(
        name=data.name,
        description=data.description,
        expected_duration=data.expected_duration,
        priority_level=data.priority_level,
    )
    return public_service(service, len(db.ordered_queue(service_id)))


def estimate_wait(service_id: int, db: InMemoryStore) -> dict[str, int]:
    service = db.find_service(service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    position = len(db.ordered_queue(service_id)) + 1
    return {"position": position, "estimated_wait": position * service["expected_duration"]}


def _decorate_queue(service_id: int, db: InMemoryStore) -> list[dict[str, Any]]:
    service = db.find_service(service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    result = []
    for position, entry in enumerate(db.ordered_queue(service_id), start=1):
        user = db.find_user(entry["user_id"])
        result.append(
            {
                **entry,
                "position": position,
                "estimated_wait": position * service["expected_duration"],
                "user_name": user["full_name"] if user else "Unknown User",
                "service_name": service["name"],
            }
        )
    return result


def join_queue(user: dict[str, Any], data: Any, db: InMemoryStore) -> dict[str, Any]:
    service = db.find_service(data.service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    if not service["is_open"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This queue is currently closed")
    if any(entry["user_id"] == user["id"] and entry["status"] == "waiting" for entry in db.queue_entries):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You are already waiting in a queue")

    entry = {
        "id": db._next_queue_id,
        "user_id": user["id"],
        "service_id": service["id"],
        "reason": data.reason,
        "priority": service["priority_level"],
        "joined_at": db.now_iso(),
        "status": "waiting",
    }
    db._next_queue_id += 1
    db.queue_entries.append(entry)

    queue = _decorate_queue(service["id"], db)
    decorated = next(item for item in queue if item["id"] == entry["id"])
    db.add_notification(
        user["id"],
        f"You joined the {service['name']} queue at position {decorated['position']}.",
        "joined",
    )
    if decorated["position"] <= 3:
        db.add_notification(
            user["id"],
            f"You are close to being served in the {service['name']} queue.",
            "almost_ready",
        )
    return decorated


def user_queue_status(user: dict[str, Any], db: InMemoryStore) -> dict[str, Any] | None:
    active = next(
        (entry for entry in db.queue_entries if entry["user_id"] == user["id"] and entry["status"] == "waiting"),
        None,
    )
    if not active:
        return None
    return next(item for item in _decorate_queue(active["service_id"], db) if item["id"] == active["id"])


def _elapsed_minutes(start_iso: str) -> int:
    started = datetime.fromisoformat(start_iso)
    now = datetime.now(timezone.utc)
    return max(0, int((now - started).total_seconds() // 60))


def leave_queue(user: dict[str, Any], service_id: int, db: InMemoryStore) -> dict[str, Any]:
    entry = next(
        (
            item for item in db.queue_entries
            if item["user_id"] == user["id"] and item["service_id"] == service_id and item["status"] == "waiting"
        ),
        None,
    )
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active queue entry not found")
    service = db.find_service(service_id)
    entry["status"] = "left_queue"
    history = {
        "id": db._next_history_id,
        "user_id": user["id"],
        "service_id": service_id,
        "service_name": service["name"],
        "joined_at": entry["joined_at"],
        "completed_at": db.now_iso(),
        "outcome": "left_queue",
        "wait_minutes": _elapsed_minutes(entry["joined_at"]),
    }
    db._next_history_id += 1
    db.history.append(history)
    db.add_notification(user["id"], f"You left the {service['name']} queue.", "left_queue")
    return history


def queue_for_admin(service_id: int, db: InMemoryStore) -> list[dict[str, Any]]:
    return _decorate_queue(service_id, db)


def serve_next(service_id: int, db: InMemoryStore) -> dict[str, Any]:
    service = db.find_service(service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    ordered = db.ordered_queue(service_id)
    if not ordered:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No users are waiting in this queue")

    entry = ordered[0]
    user = db.find_user(entry["user_id"])
    entry["status"] = "served"
    history = {
        "id": db._next_history_id,
        "user_id": entry["user_id"],
        "service_id": service_id,
        "service_name": service["name"],
        "joined_at": entry["joined_at"],
        "completed_at": db.now_iso(),
        "outcome": "served",
        "wait_minutes": _elapsed_minutes(entry["joined_at"]),
    }
    db._next_history_id += 1
    db.history.append(history)
    db.add_notification(entry["user_id"], f"You were served by {service['name']}.", "served")

    updated_queue = _decorate_queue(service_id, db)
    for waiting in updated_queue:
        if waiting["position"] <= 3:
            existing = any(
                note["user_id"] == waiting["user_id"]
                and note["type"] == "almost_ready"
                and service["name"] in note["message"]
                for note in db.notifications
            )
            if not existing:
                db.add_notification(
                    waiting["user_id"],
                    f"You are close to being served in the {service['name']} queue.",
                    "almost_ready",
                )

    return {
        "served_user": user["full_name"] if user else "Unknown User",
        "history": history,
        "remaining_queue": updated_queue,
    }


def user_notifications(user: dict[str, Any], db: InMemoryStore) -> list[dict[str, Any]]:
    return sorted(
        [note for note in db.notifications if note["user_id"] == user["id"]],
        key=lambda note: note["created_at"],
        reverse=True,
    )


def user_history(user: dict[str, Any], db: InMemoryStore) -> list[dict[str, Any]]:
    return sorted(
        [item for item in db.history if item["user_id"] == user["id"]],
        key=lambda item: item["completed_at"],
        reverse=True,
    )


def user_dashboard(user: dict[str, Any], db: InMemoryStore) -> dict[str, Any]:
    return {
        "user": public_user(user),
        "queue_status": user_queue_status(user, db),
        "services": list_services(db),
        "notifications": user_notifications(user, db)[:3],
    }


def admin_dashboard(db: InMemoryStore) -> dict[str, Any]:
    services = list_services(db)
    waits = [service["queue_length"] * service["expected_duration"] for service in services]
    return {
        "open_services": sum(1 for service in services if service["is_open"]),
        "total_waiting": sum(service["queue_length"] for service in services),
        "longest_wait": max(waits, default=0),
        "services": services,
    }
