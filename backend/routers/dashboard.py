"""
Dashboard API endpoints backed by the local database.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Team, WasteReport
from schemas import DashboardStatsOut, TeamOut

router = APIRouter()


@router.get("/stats", response_model=DashboardStatsOut)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics."""
    reports = db.query(WasteReport).all()

    by_status = {"pending": 0, "verified": 0, "assigned": 0, "cleared": 0}
    by_priority = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    by_type = {"plastic": 0, "organic": 0, "mixed": 0, "hazardous": 0, "medical": 0}

    for report in reports:
        if report.status in by_status:
            by_status[report.status] += 1
        if report.priority in by_priority:
            by_priority[report.priority] += 1
        if report.waste_type in by_type:
            by_type[report.waste_type] += 1

    return DashboardStatsOut(
        total=len(reports),
        pending=by_status["pending"],
        verified=by_status["verified"],
        assigned=by_status["assigned"],
        cleared=by_status["cleared"],
        by_priority=by_priority,
        by_type=by_type,
    )


@router.get("/teams", response_model=List[TeamOut])
def get_dashboard_teams(db: Session = Depends(get_db)):
    """Get all active teams."""
    return db.query(Team).filter(Team.active.is_(True)).order_by(Team.name).all()