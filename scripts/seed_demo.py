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

MOCK_USERS = [
    ("maya@queuesmart.local", "Student123!", "Maya Chen"),
    ("jordan@queuesmart.local", "Student123!", "Jordan Patel"),
    ("taylor@queuesmart.local", "Student123!", "Taylor Brooks"),
    ("casey@queuesmart.local", "Student123!", "Casey Rivera"),
]


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


def add_history_once(db, user, service, queue, joined, wait_minutes, outcome="served"):
    existing = db.scalar(
        select(QueueEntry).where(
            QueueEntry.queue_id == queue.id,
            QueueEntry.user_id == user.id,
            QueueEntry.join_time == joined,
        )
    )
    if existing:
        return

    completed = joined + timedelta(minutes=wait_minutes)
    entry = QueueEntry(
        queue_id=queue.id,
        user_id=user.id,
        position=1,
        join_time=joined,
        completed_at=completed,
        status=outcome,
        reason_for_visit="Mock reporting visit",
    )
    db.add(entry)
    db.flush()
    db.add(
        History(
            user_id=user.id,
            service_id=service.id,
            queue_entry_id=entry.id,
            joined_at=joined,
            completed_at=completed,
            outcome=outcome,
            wait_minutes=wait_minutes,
        )
    )


def add_waiting_entry_once(db, user, service, reason):
    queue = db.scalar(select(Queue).where(Queue.service_id == service.id))
    existing = db.scalar(
        select(QueueEntry).where(
            QueueEntry.queue_id == queue.id,
            QueueEntry.user_id == user.id,
            QueueEntry.status == "waiting",
        )
    )
    if existing:
        return

    position = (
        db.query(QueueEntry)
        .where(QueueEntry.queue_id == queue.id, QueueEntry.status == "waiting")
        .count()
        + 1
    )
    db.add(
        QueueEntry(
            queue_id=queue.id,
            user_id=user.id,
            position=position,
            reason_for_visit=reason,
        )
    )


def seed():
    init_db()
    db = SessionLocal()
    try:
        admin = get_or_create_user(db, ADMIN_EMAIL, ADMIN_PASSWORD, "QueueSmart Administrator", "administrator")
        student = get_or_create_user(db, USER_EMAIL, USER_PASSWORD, "Demo Student", "user")
        mock_users = [
            get_or_create_user(db, email, password, full_name, "user")
            for email, password, full_name in MOCK_USERS
        ]
        advising = get_or_create_service(db, "Academic Advising", "Degree planning and academic advising support", 15, "high")
        financial = get_or_create_service(db, "Financial Aid", "Financial aid questions and document review", 12, "medium")
        helpdesk = get_or_create_service(db, "IT Help Desk", "Account, device, and campus technology support", 10, "medium")
        registrar = get_or_create_service(db, "Registrar", "Transcript requests, enrollment verification, and records support", 8, "medium")
        tutoring = get_or_create_service(db, "Tutoring Center", "Course tutoring and study support appointments", 20, "low")

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

        queues = {
            service.id: db.scalar(select(Queue).where(Queue.service_id == service.id))
            for service in [advising, financial, helpdesk, registrar, tutoring]
        }
        mock_patterns = [
            (mock_users[0], advising, [(1, 9, 7, "served"), (5, 11, 19, "served"), (9, 14, 12, "canceled")]),
            (mock_users[0], financial, [(2, 10, 15, "served"), (8, 13, 24, "served")]),
            (mock_users[1], helpdesk, [(1, 8, 6, "served"), (4, 15, 10, "served"), (10, 16, 14, "canceled")]),
            (mock_users[1], tutoring, [(3, 12, 18, "served"), (7, 10, 11, "served")]),
            (mock_users[2], registrar, [(2, 9, 5, "served"), (6, 14, 8, "served"), (11, 11, 9, "served")]),
            (mock_users[2], advising, [(4, 13, 21, "served"), (12, 15, 13, "served")]),
            (mock_users[3], financial, [(3, 9, 10, "served"), (7, 12, 20, "served"), (13, 16, 16, "served")]),
            (mock_users[3], helpdesk, [(5, 10, 7, "served"), (9, 15, 9, "served")]),
            (student, tutoring, [(6, 11, 16, "served"), (14, 13, 22, "served")]),
            (student, registrar, [(8, 10, 6, "served"), (15, 14, 7, "canceled")]),
        ]
        base = datetime.now(UTC).replace(tzinfo=None, minute=0, second=0, microsecond=0) - timedelta(days=21)
        for user, service, visits in mock_patterns:
            queue = queues[service.id]
            for day_offset, hour, wait, outcome in visits:
                joined = (base + timedelta(days=day_offset)).replace(hour=hour)
                add_history_once(db, user, service, queue, joined, wait, outcome)

        add_waiting_entry_once(db, mock_users[0], advising, "Need help choosing spring classes")
        add_waiting_entry_once(db, mock_users[1], advising, "Degree plan review")
        add_waiting_entry_once(db, mock_users[2], financial, "Scholarship paperwork question")
        add_waiting_entry_once(db, mock_users[3], helpdesk, "Laptop login issue")
        add_waiting_entry_once(db, student, tutoring, "Calculus review session")

        db.commit()
        print("QueueSmart demo data is ready.")
        print(f"Administrator: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"User:          {USER_EMAIL} / {USER_PASSWORD}")
        print("Mock student accounts all use password: Student123!")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
