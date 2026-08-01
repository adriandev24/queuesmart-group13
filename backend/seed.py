"""Repeatable demo data for local development and grading."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Queue, Service, UserCredential, UserProfile
from .security import hash_password


def seed_database(db: Session) -> None:
    if db.scalar(select(UserCredential.id).limit(1)) is None:
        admin = UserCredential(
            email="admin@queuesmart.example",
            password_hash=hash_password("Admin123!"),
            role="administrator",
            profile=UserProfile(full_name="QueueSmart Administrator", contact_info="713-555-0100", preferences="Email updates"),
        )
        user = UserCredential(
            email="user@queuesmart.example",
            password_hash=hash_password("User123!"),
            role="user",
            profile=UserProfile(full_name="Demo Student", contact_info="713-555-0101", preferences="In-app notifications"),
        )
        db.add_all([admin, user])

    if db.scalar(select(Service.id).limit(1)) is None:
        services = [
            Service(name="Campus Advising", description="Academic advising and degree planning.", expected_duration=9, priority_level="medium"),
            Service(name="Financial Aid Desk", description="Help with financial aid documents and questions.", expected_duration=18, priority_level="high"),
            Service(name="ID Card Office", description="Student identification card services.", expected_duration=8, priority_level="medium"),
            Service(name="Tech Help Counter", description="Technical support for student accounts and devices.", expected_duration=13, priority_level="low"),
        ]
        for service in services:
            service.queues.append(Queue(status="open"))
        db.add_all(services)

    db.commit()
