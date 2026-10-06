"""
Dashboard authentication endpoints (email + password, bearer sessions).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AuthToken, User
from services.auth import authenticate, issue_token, require_user

router = APIRouter()


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str

    model_config = {"from_attributes": True}


class LoginOut(BaseModel):
    token: str
    user: UserOut


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """Log in as council staff. Returns a bearer token for dashboard calls."""
    user = authenticate(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    row = issue_token(db, user)
    return {"token": row.token, "user": user}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user)):
    """Return the currently logged-in staff member."""
    return user


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    """Revoke the current session token (safe to call when already logged out)."""
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else ""
    if token:
        db.query(AuthToken).filter(AuthToken.token == token).delete()
        db.commit()
    return {"status": "logged_out", "timestamp": datetime.utcnow().isoformat()}
