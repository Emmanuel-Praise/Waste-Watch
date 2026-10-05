"""
Database setup and session management.

Uses SQLite by default for local development. Set the DATABASE_URL
environment variable to point at PostgreSQL/Supabase in later steps.
The Location model is structured so PostGIS geometry can be added
without restructuring the application.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bamenda.db")

# On Render with SQLite the DB file lives on a persistent disk
# (e.g. sqlite:////opt/render/project/src/backend/data/bamenda.db).
# Make sure its parent folder exists before the engine touches the file.
if DATABASE_URL.startswith("sqlite"):
    _path = DATABASE_URL.split("sqlite:///", 1)[-1]
    if _path and _path != ":memory:":
        try:
            os.makedirs(os.path.dirname(os.path.abspath(_path)), exist_ok=True)
        except OSError:
            pass

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Lightweight, idempotent column additions for SQLite (create_all cannot alter
# an existing table). New columns are added here as the schema evolves.
_SQLITE_COLUMN_MIGRATIONS = [
    ("pending_intakes", "state", "VARCHAR(30) DEFAULT 'idle'"),
]


def _migrate_sqlite():
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        for table, column, definition in _SQLITE_COLUMN_MIGRATIONS:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
            except Exception:  # column already present (or table missing)
                pass


def init_db():
    from models import (  # noqa: F401
        BrandNotified,
        CitizenMessage,
        Hotspot,
        Location,
        PendingIntake,
        ProcessedMessage,
        StatusHistory,
        Team,
        User,
        WasteReport,
    )
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()