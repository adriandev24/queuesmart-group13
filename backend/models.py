from datetime import datetime, UTC
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


class UserCredential(Base):
    __tablename__ = "user_credentials"
    __table_args__ = (
        CheckConstraint("length(email) BETWEEN 3 AND 254", name="ck_user_email_length"),
        CheckConstraint("role IN ('user', 'administrator')", name="ck_user_role"),
        Index("ix_user_credentials_email", "email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint("length(full_name) BETWEEN 2 AND 80", name="ck_profile_name_length"),
        CheckConstraint("contact_info IS NULL OR length(contact_info) <= 120", name="ck_profile_contact_length"),
        CheckConstraint("preferences IS NULL OR length(preferences) <= 250", name="ck_profile_preferences_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_credentials.id", ondelete="CASCADE"), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(80), nullable=False)
    contact_info: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferences: Mapped[str | None] = mapped_column(String(250), nullable=True)

    user = relationship("UserCredential", back_populates="profile")


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 2 AND 100", name="ck_service_name_length"),
        CheckConstraint("length(description) BETWEEN 5 AND 250", name="ck_service_description_length"),
        CheckConstraint("expected_duration BETWEEN 1 AND 120", name="ck_service_duration"),
        CheckConstraint("priority_level IN ('low', 'medium', 'high')", name="ck_service_priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    expected_duration: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_level: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class Queue(Base):
    __tablename__ = "queues"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed')", name="ck_queue_status"),
        Index("ix_queues_service_id", "service_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)


class QueueEntry(Base):
    __tablename__ = "queue_entries"
    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_queue_entry_position"),
        CheckConstraint("status IN ('waiting', 'served', 'canceled')", name="ck_queue_entry_status"),
        CheckConstraint("length(reason_for_visit) BETWEEN 2 AND 200", name="ck_queue_entry_reason_length"),
        UniqueConstraint("queue_id", "user_id", "join_time", name="uq_queue_entry_join"),
        Index("ix_queue_entries_queue_id", "queue_id"),
        Index("ix_queue_entries_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    queue_id: Mapped[int] = mapped_column(ForeignKey("queues.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_credentials.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    join_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="waiting")
    reason_for_visit: Mapped[str] = mapped_column(String(200), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("length(message) BETWEEN 1 AND 300", name="ck_notification_message_length"),
        CheckConstraint("status IN ('sent', 'viewed')", name="ck_notification_status"),
        Index("ix_notifications_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_credentials.id", ondelete="CASCADE"), nullable=False)
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="sent")


class History(Base):
    __tablename__ = "history"
    __table_args__ = (
        CheckConstraint("outcome IN ('served', 'canceled')", name="ck_history_outcome"),
        CheckConstraint("wait_minutes >= 0", name="ck_history_wait_minutes"),
        Index("ix_history_user_id", "user_id"),
        Index("ix_history_service_id", "service_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_credentials.id", ondelete="CASCADE"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="RESTRICT"), nullable=False)
    queue_entry_id: Mapped[int] = mapped_column(ForeignKey("queue_entries.id", ondelete="CASCADE"), nullable=False, unique=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    wait_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SessionToken(Base):
    __tablename__ = "session_tokens"
    __table_args__ = (Index("ix_session_tokens_user_id", "user_id"),)

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_credentials.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
