"""Database configuration for QueueSmart."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


_DEFAULT_DB = Path(__file__).resolve().parent / "queuesmart.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB}")
engine: Engine
SessionLocal: sessionmaker[Session]


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def configure_database(database_url: str | None = None) -> Engine:
    """Configure the application engine and session factory.

    Tests call this function with a temporary SQLite database. The application uses
    backend/queuesmart.db by default so data survives server restarts.
    """
    global engine, SessionLocal, DATABASE_URL

    if "engine" in globals():
        engine.dispose()

    DATABASE_URL = database_url or os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB}")
    connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
    engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)

    if DATABASE_URL.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return engine


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(seed: bool = True) -> None:
    """Create all tables and optionally insert repeatable demo data."""
    from . import models  # noqa: F401 - registers model metadata

    Base.metadata.create_all(bind=engine)
    if seed:
        from .seed import seed_database

        with SessionLocal() as session:
            seed_database(session)


def reset_db(seed: bool = True) -> None:
    """Drop and recreate all tables. Intended for tests and local development."""
    from . import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    init_db(seed=seed)


configure_database()
