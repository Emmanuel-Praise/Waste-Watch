"""
Dashboard login sessions.

Email + password login for council staff (admin and council roles).
Passwords use stdlib PBKDF2-SHA256 (no extra dependencies); sessions are
random bearer tokens stored in the `auth_tokens` table with a 30-day
expiry. WhatsApp citizens never log in — their rows have no password.
"""

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models import AuthToken, User

logger = logging.getLogger(__name__)

TOKEN_TTL = timedelta(days=30)
_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """Hash a password with a random salt (stdlib PBKDF2-SHA256)."""
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS).hex()
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    """Check a password against a stored hash (constant-time compare)."""
    if not password or not stored:
        return False
    try:
        _algo, iters, salt, digest = stored.split("$", 3)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iters)
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def issue_token(db: Session, user: User) -> AuthToken:
    """Create a new session token for a user, pruning expired ones."""
    db.query(AuthToken).filter(AuthToken.expires_at < datetime.utcnow()).delete()
    row = AuthToken(
        token=secrets.token_urlsafe(32),
        user_id=user.id,
        expires_at=datetime.utcnow() + TOKEN_TTL,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def authenticate(db: Session, email: str, password: str) -> Optional[User]:
    """Return the user when email + password match an active staff account."""
    user = (
        db.query(User)
        .filter(User.email == (email or "").strip().lower())
        .first()
    )
    if not user or not user.password_hash:
        return None
    if (user.role or "") not in ("admin", "council", "operator"):
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def user_from_token(db: Session, token: str) -> Optional[User]:
    """Resolve a bearer token to its user (None when unknown/expired)."""
    if not token:
        return None
    row = db.query(AuthToken).filter(AuthToken.token == token).first()
    if not row or row.expires_at < datetime.utcnow():
        return None
    user = db.get(User, row.user_id)
    if not user or (user.role or "") not in ("admin", "council", "operator"):
        return None
    return user


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency: any logged-in staff member (admin/council/operator)."""
    user = user_from_token(db, _bearer(request))
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to access the dashboard.")
    return user


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency: admin role only (vendor approvals, staff actions)."""
    user = user_from_token(db, _bearer(request))
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to access the dashboard.")
    if (user.role or "") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user
