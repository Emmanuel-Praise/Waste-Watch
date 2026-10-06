"""
Seed the local database on first start.

Demo report seeding is intentionally disabled: the app starts empty and only
real WhatsApp reports build the dashboard. Staff login accounts (admin +
council) ARE created here so the dashboard login works out of the box.

Override the default passwords via environment variables:
  ADMIN_EMAIL / ADMIN_PASSWORD, COUNCIL_EMAIL / COUNCIL_PASSWORD
"""

import logging
import os

from database import SessionLocal
from models import User
from services.auth import hash_password

logger = logging.getLogger(__name__)


def _ensure_account(
    *,
    email: str,
    password: str,
    name: str,
    role: str,
) -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email.strip().lower()).first()
        if existing:
            # Never overwrite an existing password; only repair a missing hash
            # (e.g. databases created before login existed).
            if not existing.password_hash:
                existing.password_hash = hash_password(password)
                db.commit()
                logger.info("Set initial password for %s (%s).", email, role)
            if (existing.role or "") != role:
                existing.role = role
                db.commit()
            return
        db.add(
            User(
                name=name,
                email=email.strip().lower(),
                role=role,
                phone=None,
                password_hash=hash_password(password),
            )
        )
        db.commit()
        logger.info("Created %s account %s.", role, email)
    finally:
        db.close()


def seed_if_empty() -> None:
    _ensure_account(
        email=os.getenv("ADMIN_EMAIL", "admin@bamenda.cm"),
        password=os.getenv("ADMIN_PASSWORD", "admin123"),
        name="Council Admin",
        role="admin",
    )
    _ensure_account(
        email=os.getenv("COUNCIL_EMAIL", "council@bamenda.cm"),
        password=os.getenv("COUNCIL_PASSWORD", "council123"),
        name="Council Operator",
        role="council",
    )
    logger.info("Dashboard starts empty - only real WhatsApp reports appear.")
