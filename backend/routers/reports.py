"""
Reports API endpoints backed by the local database.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from models import Location, StatusHistory, Team, WasteReport, WORKFLOW_ORDER
from schemas import (
    ReportAssign,
    ReportCreate,
    ReportStatusUpdate,
    Status,
    WasteReportOut,
)
from services.hotspots import find_or_create_hotspot, recompute_importance
from services.messages import notify_status_change
from services.processing import next_ticket_id, process_report

router = APIRouter()


def _append_history(
    report: WasteReport,
    to_status: str,
    notes: Optional[str] = None,
) -> None:
    report.status_history.append(
        StatusHistory(
            id=str(uuid.uuid4()),
            report_id=report.id,
            from_status=report.status,
            to_status=to_status,
            notes=notes,
            created_at=datetime.utcnow(),
        )
    )


@router.get("", response_model=List[WasteReportOut])
def list_reports(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    waste_type: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get all waste reports with optional filtering and pagination."""
    query = db.query(WasteReport)

    if status:
        query = query.filter(WasteReport.status == status)
    if priority:
        query = query.filter(WasteReport.priority == priority)
    if waste_type:
        query = query.filter(WasteReport.waste_type == waste_type)

    query = query.order_by(WasteReport.created_at.desc())
    start = (page - 1) * limit
    return query.offset(start).limit(limit).all()


@router.post("", status_code=410)
def create_report():
    """Disabled: citizen reports arrive via WhatsApp only (see /api/whatsapp/webhook)."""
    raise HTTPException(
        status_code=410,
        detail="Web reporting is disabled. Please report waste via WhatsApp: send a photo + location pin.",
    )


@router.post("/process", status_code=410)
async def process_report_endpoint():
    """Disabled: citizen reports arrive via WhatsApp only (see /api/whatsapp/webhook)."""
    raise HTTPException(
        status_code=410,
        detail="Web reporting is disabled. Please report waste via WhatsApp: send a photo + location pin.",
    )


@router.get("/{report_id}", response_model=WasteReportOut)
def get_report(report_id: str, db: Session = Depends(get_db)):
    """Get a single report by ID."""
    report = db.get(WasteReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.put("/{report_id}/status", response_model=WasteReportOut)
def update_report_status(
    report_id: str,
    payload: ReportStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update report status following the Pending → Verified → Assigned → Cleared workflow."""
    report = db.get(WasteReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    new_status = payload.status.value
    if new_status == report.status:
        return report

    if (
        new_status in WORKFLOW_ORDER
        and report.status in WORKFLOW_ORDER
        and WORKFLOW_ORDER[new_status] < WORKFLOW_ORDER[report.status]
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot move report backwards from '{report.status}' to '{new_status}'.",
        )

    _append_history(report, new_status, payload.notes if payload.notes else None)
    report.status = new_status
    report.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(report)

    try:
        notify_status_change(db, report, new_status)
    except Exception:
        db.rollback()

    return report


@router.put("/{report_id}/assign", response_model=WasteReportOut)
def assign_report(
    report_id: str,
    payload: ReportAssign,
    db: Session = Depends(get_db),
):
    """Assign (or unassign) a report to a team."""
    report = db.get(WasteReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    team_id = payload.team_id.strip() if payload.team_id else ""
    notify_status: Optional[str] = None

    if team_id == "":
        report.assigned_team_id = None
        if report.status == Status.ASSIGNED.value:
            _append_history(report, Status.VERIFIED.value, "Unassigned")
            report.status = Status.VERIFIED.value
            notify_status = Status.VERIFIED.value
        report.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(report)
        if notify_status:
            try:
                notify_status_change(db, report, notify_status)
            except Exception:
                db.rollback()
        return report

    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=400, detail="Invalid team ID")

    report.assigned_team_id = team.id

    if report.status != Status.ASSIGNED.value:
        _append_history(report, Status.ASSIGNED.value)
        report.status = Status.ASSIGNED.value
        notify_status = Status.ASSIGNED.value

    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    if notify_status:
        try:
            notify_status_change(db, report, notify_status)
        except Exception:
            db.rollback()
    return report