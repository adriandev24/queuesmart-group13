from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, UTC
from statistics import mean
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from .models import History, Notification, Queue, QueueEntry, Service, UserCredential, UserProfile


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def get_service_queue(db: Session, service_id: int) -> Queue | None:
    return db.scalar(select(Queue).where(Queue.service_id == service_id))


def waiting_entries(db: Session, queue_id: int) -> list[QueueEntry]:
    return list(
        db.scalars(
            select(QueueEntry)
            .where(QueueEntry.queue_id == queue_id, QueueEntry.status == "waiting")
            .order_by(QueueEntry.position, QueueEntry.join_time)
        ).all()
    )


def renumber_queue(db: Session, queue_id: int) -> list[QueueEntry]:
    entries = waiting_entries(db, queue_id)
    for index, entry in enumerate(entries, start=1):
        entry.position = index
    db.flush()
    return entries


def create_notification(db: Session, user_id: int, message: str) -> Notification:
    item = Notification(user_id=user_id, message=message)
    db.add(item)
    db.flush()
    return item


def notify_close_users(db: Session, queue_id: int, service_name: str) -> None:
    for entry in waiting_entries(db, queue_id):
        if entry.position <= 2:
            create_notification(
                db,
                entry.user_id,
                f"You are almost ready for {service_name}. Current position: {entry.position}.",
            )


def complete_entry(db: Session, entry: QueueEntry, service_id: int, outcome: str, message: str) -> History:
    completed_at = utc_now()
    entry.status = outcome
    entry.completed_at = completed_at
    wait_minutes = max(0, int(round((completed_at - entry.join_time).total_seconds() / 60)))
    history = History(
        user_id=entry.user_id,
        service_id=service_id,
        queue_entry_id=entry.id,
        joined_at=entry.join_time,
        completed_at=completed_at,
        outcome=outcome,
        wait_minutes=wait_minutes,
    )
    db.add(history)
    create_notification(db, entry.user_id, message)
    db.flush()
    return history


def service_snapshot(db: Session, service: Service) -> dict:
    queue = get_service_queue(db, service.id)
    waiting_count = 0
    if queue:
        waiting_count = db.scalar(
            select(func.count(QueueEntry.id)).where(
                QueueEntry.queue_id == queue.id,
                QueueEntry.status == "waiting",
            )
        ) or 0
    return {
        "id": service.id,
        "name": service.name,
        "description": service.description,
        "expected_duration": service.expected_duration,
        "priority_level": service.priority_level,
        "queue_status": queue.status if queue else "closed",
        "waiting_count": int(waiting_count),
    }


def best_time_recommendation(db: Session, service: Service, lookback_days: int = 90) -> dict:
    cutoff = utc_now() - timedelta(days=lookback_days)
    histories = list(
        db.scalars(
            select(History).where(
                History.service_id == service.id,
                History.outcome == "served",
                History.joined_at >= cutoff,
            )
        ).all()
    )

    queue = get_service_queue(db, service.id)
    current_waiting = len(waiting_entries(db, queue.id)) if queue else 0

    if histories:
        by_hour: dict[int, list[History]] = defaultdict(list)
        for item in histories:
            by_hour[item.joined_at.hour].append(item)

        candidates = []
        for hour, rows in by_hour.items():
            avg_wait = mean(row.wait_minutes for row in rows)
            volume = len(rows)
            # Lower waits matter most; a small volume penalty favors less crowded windows.
            score = avg_wait + (volume * 0.35)
            candidates.append((score, avg_wait, volume, hour))

        score, avg_wait, sample_count, hour = min(candidates, key=lambda row: (row[0], row[1], row[3]))
        confidence = "high" if len(histories) >= 12 else "medium" if len(histories) >= 5 else "low"
        return {
            "service_id": service.id,
            "service_name": service.name,
            "recommended_window": f"{hour:02d}:00-{(hour + 1) % 24:02d}:00",
            "basis": "historical_queue_data",
            "historical_samples": len(histories),
            "recommended_hour_samples": sample_count,
            "recommended_hour_average_wait": round(avg_wait, 1),
            "current_waiting": current_waiting,
            "confidence": confidence,
            "explanation": (
                "QueueSmart compared completed visits by join hour and selected the hour with the "
                "lowest combined average-wait and traffic score."
            ),
        }

    if current_waiting <= 1:
        window = "Now"
        explanation = "There is little or no current queue load, so joining now is the best rules-based suggestion."
    else:
        delay = min(90, max(15, current_waiting * service.expected_duration))
        future = datetime.now() + timedelta(minutes=delay)
        window = future.strftime("%I:%M %p")
        explanation = (
            "There is not enough completed history yet. QueueSmart uses the current queue length and "
            "expected service duration to suggest a later check-in time."
        )

    return {
        "service_id": service.id,
        "service_name": service.name,
        "recommended_window": window,
        "basis": "current_load_fallback",
        "historical_samples": 0,
        "recommended_hour_samples": 0,
        "recommended_hour_average_wait": None,
        "current_waiting": current_waiting,
        "confidence": "low",
        "explanation": explanation,
    }


def _history_query(start_date: datetime | None, end_date: datetime | None, service_id: int | None):
    query = select(History)
    if start_date:
        query = query.where(History.completed_at >= start_date)
    if end_date:
        query = query.where(History.completed_at <= end_date)
    if service_id:
        query = query.where(History.service_id == service_id)
    return query.order_by(History.completed_at.desc())


def build_report_data(
    db: Session,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    service_id: int | None = None,
) -> dict:
    histories = list(db.scalars(_history_query(start_date, end_date, service_id)).all())
    history_by_user: dict[int, list[History]] = defaultdict(list)
    for row in histories:
        history_by_user[row.user_id].append(row)

    users = list(db.scalars(select(UserCredential).where(UserCredential.role == "user").order_by(UserCredential.email)).all())
    services_query = select(Service).order_by(Service.name)
    if service_id:
        services_query = services_query.where(Service.id == service_id)
    services = list(db.scalars(services_query).all())
    service_map = {service.id: service for service in db.scalars(select(Service)).all()}
    profile_map = {profile.user_id: profile for profile in db.scalars(select(UserProfile)).all()}

    user_rows = []
    for user in users:
        rows = history_by_user.get(user.id, [])
        if service_id and not rows:
            continue
        user_rows.append(
            {
                "user_id": user.id,
                "email": user.email,
                "full_name": profile_map.get(user.id).full_name if profile_map.get(user.id) else "",
                "participation_count": len(rows),
                "history": [
                    {
                        "service": service_map[item.service_id].name if item.service_id in service_map else f"Service {item.service_id}",
                        "joined_at": item.joined_at.isoformat(),
                        "completed_at": item.completed_at.isoformat(),
                        "outcome": item.outcome,
                        "wait_minutes": item.wait_minutes,
                    }
                    for item in rows
                ],
            }
        )

    service_rows = []
    for service in services:
        queue = get_service_queue(db, service.id)
        waiting = len(waiting_entries(db, queue.id)) if queue else 0
        service_history = [item for item in histories if item.service_id == service.id]
        service_rows.append(
            {
                "service_id": service.id,
                "name": service.name,
                "description": service.description,
                "expected_duration": service.expected_duration,
                "priority_level": service.priority_level,
                "queue_status": queue.status if queue else "closed",
                "current_waiting": waiting,
                "served": sum(item.outcome == "served" for item in service_history),
                "canceled": sum(item.outcome == "canceled" for item in service_history),
            }
        )

    served = [item for item in histories if item.outcome == "served"]
    stats = {
        "total_participations": len(histories),
        "users_served": len(served),
        "canceled": sum(item.outcome == "canceled" for item in histories),
        "average_wait_minutes": round(mean(item.wait_minutes for item in served), 1) if served else 0.0,
        "unique_customers": len({item.user_id for item in histories}),
        "current_waiting": sum(row["current_waiting"] for row in service_rows),
    }

    return {
        "filters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "service_id": service_id,
        },
        "statistics": stats,
        "users": user_rows,
        "services": service_rows,
    }
