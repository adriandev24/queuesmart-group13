"""Populate QueueSmart with deterministic demo data for the live final-project demo."""
from datetime import datetime, timedelta, UTC
from pathlib import Path
import sys
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal, init_db
from backend.models import History, Queue, QueueEntry, Service, UserCredential, UserProfile
from backend.security import hash_password

ADMIN_EMAIL = "admin@queuesmart.local"
ADMIN_PASSWORD = "Admin123!"
USER_EMAIL = "student@queuesmart.local"
USER_PASSWORD = "Student123!"


def get_or_create_user(db, email, password, full_name, role):
    user = db.scalar(select(UserCredential).where(UserCredential.email == email))
    if user:
        return user
    user = UserCredential(email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, full_name=full_name))
    db.flush()
    return user


def get_or_create_service(db, name, description, duration, priority):
    service = db.scalar(select(Service).where(Service.name == name))
    if service:
        return service
    service = Service(name=name, description=description, expected_duration=duration, priority_level=priority)
    db.add(service)
    db.flush()
    db.add(Queue(service_id=service.id, status="open"))
    db.flush()
    return service


def seed():
    init_db()
    db = SessionLocal()
    try:
        admin = get_or_create_user(db, ADMIN_EMAIL, ADMIN_PASSWORD, "QueueSmart Administrator", "administrator")
        student = get_or_create_user(db, USER_EMAIL, USER_PASSWORD, "Demo Student", "user")
        advising = get_or_create_service(db, "Academic Advising", "Degree planning and academic advising support", 15, "high")
        financial = get_or_create_service(db, "Financial Aid", "Financial aid questions and document review", 12, "medium")
        helpdesk = get_or_create_service(db, "IT Help Desk", "Account, device, and campus technology support", 10, "medium")

        # Add completed visits only once. These rows intentionally cover several hours so the
        # smart recommendation has meaningful historical evidence during the demo.
        if db.scalar(select(History).limit(1)) is None:
            services = [advising, financial, helpdesk]
            patterns = {
                advising.id: [(9, 8), (9, 10), (11, 22), (13, 18), (15, 11), (15, 9)],
                financial.id: [(9, 14), (10, 12), (12, 25), (14, 10), (14, 8), (16, 13)],
                helpdesk.id: [(8, 7), (10, 12), (12, 18), (15, 6), (15, 8), (16, 11)],
            }
            base = datetime.now(UTC).replace(tzinfo=None, minute=0, second=0, microsecond=0) - timedelta(days=18)
            for service in services:
                queue = db.scalar(select(Queue).where(Queue.service_id == service.id))
                for idx, (hour, wait) in enumerate(patterns[service.id]):
                    joined = (base + timedelta(days=idx * 2)).replace(hour=hour)
                    completed = joined + timedelta(minutes=wait)
                    entry = QueueEntry(
                        queue_id=queue.id,
                        user_id=student.id,
                        position=1,
                        join_time=joined,
                        completed_at=completed,
                        status="served",
                        reason_for_visit="Historical demo visit",
                    )
                    db.add(entry)
                    db.flush()
                    db.add(
                        History(
                            user_id=student.id,
                            service_id=service.id,
                            queue_entry_id=entry.id,
                            joined_at=joined,
                            completed_at=completed,
                            outcome="served",
                            wait_minutes=wait,
                        )
                    )
        db.commit()
        print("QueueSmart demo data is ready.")
        print(f"Administrator: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"User:          {USER_EMAIL} / {USER_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
