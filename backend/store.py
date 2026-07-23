from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .security import hash_password

PRIORITY_WEIGHT = {"high": 0, "medium": 1, "low": 2}


class InMemoryStore:
    """In-memory collections used instead of a persistent database."""

    def __init__(self) -> None:
        self.reset()

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def reset(self) -> None:
        self.users: list[dict[str, Any]] = [
            {
                "id": 1,
                "full_name": "Demo User",
                "email": "user@queuesmartapp.com",
                "password_hash": hash_password("UserPass123"),
                "role": "user",
            },
            {
                "id": 2,
                "full_name": "Demo Administrator",
                "email": "admin@queuesmartapp.com",
                "password_hash": hash_password("AdminPass123"),
                "role": "administrator",
            },
            {
                "id": 3,
                "full_name": "Maya Thompson",
                "email": "maya@queuesmartapp.com",
                "password_hash": hash_password("MayaPass123"),
                "role": "user",
            },
            {
                "id": 4,
                "full_name": "Omar Carter",
                "email": "omar@queuesmartapp.com",
                "password_hash": hash_password("OmarPass123"),
                "role": "user",
            },
            {
                "id": 5,
                "full_name": "Lina Park",
                "email": "lina@queuesmartapp.com",
                "password_hash": hash_password("LinaPass123"),
                "role": "user",
            },
        ]
        self.services: list[dict[str, Any]] = [
            {
                "id": 1,
                "name": "Campus Advising",
                "description": "Meet with an academic advisor about courses and degree planning.",
                "expected_duration": 8,
                "priority_level": "medium",
                "is_open": True,
            },
            {
                "id": 2,
                "name": "Financial Aid Desk",
                "description": "Get help with financial aid documents, awards, and account questions.",
                "expected_duration": 11,
                "priority_level": "high",
                "is_open": True,
            },
            {
                "id": 3,
                "name": "ID Card Office",
                "description": "Replace, activate, or troubleshoot a campus identification card.",
                "expected_duration": 6,
                "priority_level": "medium",
                "is_open": True,
            },
            {
                "id": 4,
                "name": "Tech Help Counter",
                "description": "Receive support for account access and common campus technology issues.",
                "expected_duration": 10,
                "priority_level": "low",
                "is_open": True,
            },
        ]
        joined = self.now_iso()
        self.queue_entries: list[dict[str, Any]] = [
            {
                "id": 1,
                "user_id": 3,
                "service_id": 1,
                "reason": "Degree plan question",
                "priority": "high",
                "joined_at": joined,
                "status": "waiting",
            },
            {
                "id": 2,
                "user_id": 4,
                "service_id": 1,
                "reason": "Transfer credit review",
                "priority": "medium",
                "joined_at": joined,
                "status": "waiting",
            },
            {
                "id": 3,
                "user_id": 5,
                "service_id": 1,
                "reason": "Graduation check",
                "priority": "low",
                "joined_at": joined,
                "status": "waiting",
            },
        ]
        self.notifications: list[dict[str, Any]] = [
            {
                "id": 1,
                "user_id": 1,
                "message": "Welcome to QueueSmart. Choose an open service to join a queue.",
                "type": "info",
                "created_at": self.now_iso(),
            }
        ]
        self.history: list[dict[str, Any]] = [
            {
                "id": 1,
                "user_id": 1,
                "service_id": 3,
                "service_name": "ID Card Office",
                "joined_at": "2026-07-02T14:10:00+00:00",
                "completed_at": "2026-07-02T14:18:00+00:00",
                "outcome": "served",
                "wait_minutes": 8,
            },
            {
                "id": 2,
                "user_id": 1,
                "service_id": 2,
                "service_name": "Financial Aid Desk",
                "joined_at": "2026-06-29T15:00:00+00:00",
                "completed_at": "2026-06-29T15:15:00+00:00",
                "outcome": "served",
                "wait_minutes": 15,
            },
            {
                "id": 3,
                "user_id": 1,
                "service_id": 4,
                "service_name": "Tech Help Counter",
                "joined_at": "2026-06-21T16:00:00+00:00",
                "completed_at": "2026-06-21T16:04:00+00:00",
                "outcome": "left_queue",
                "wait_minutes": 4,
            },
        ]
        self.sessions: dict[str, int] = {}
        self._next_user_id = 6
        self._next_service_id = 5
        self._next_queue_id = 4
        self._next_notification_id = 2
        self._next_history_id = 4

    def snapshot(self) -> dict[str, Any]:
        return {
            "users": deepcopy(self.users),
            "services": deepcopy(self.services),
            "queue_entries": deepcopy(self.queue_entries),
            "notifications": deepcopy(self.notifications),
            "history": deepcopy(self.history),
        }

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        normalized = email.lower()
        return next((u for u in self.users if u["email"].lower() == normalized), None)

    def find_user(self, user_id: int) -> dict[str, Any] | None:
        return next((u for u in self.users if u["id"] == user_id), None)

    def find_service(self, service_id: int) -> dict[str, Any] | None:
        return next((s for s in self.services if s["id"] == service_id), None)

    def create_session(self, user_id: int) -> str:
        token = uuid4().hex
        self.sessions[token] = user_id
        return token

    def ordered_queue(self, service_id: int) -> list[dict[str, Any]]:
        entries = [
            entry for entry in self.queue_entries
            if entry["service_id"] == service_id and entry["status"] == "waiting"
        ]
        return sorted(
            entries,
            key=lambda entry: (PRIORITY_WEIGHT[entry["priority"]], entry["joined_at"], entry["id"]),
        )

    def add_notification(self, user_id: int, message: str, notification_type: str) -> dict[str, Any]:
        notification = {
            "id": self._next_notification_id,
            "user_id": user_id,
            "message": message,
            "type": notification_type,
            "created_at": self.now_iso(),
        }
        self._next_notification_id += 1
        self.notifications.append(notification)
        return notification


store = InMemoryStore()
