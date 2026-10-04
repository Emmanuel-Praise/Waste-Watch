"""
Report processing workflow.

Turns an incoming message/image + location into a structured, prioritized
report in the database:

    image / message / location
    -> AI analysis
    -> severity
    -> priority
    -> hotspot association
    -> database

This module is independent of the API layer so the same workflow can be
triggered from an HTTP route today and from WhatsApp in a later step.
"""

import logging
import os
import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models import Location as LocationRow
from models import StatusHistory, WasteReport
from schemas import LocationIn
from services.hotspots import find_or_create_hotspot, recompute_importance
from services.priority import compute_priority, severity_label
from services.vision import get_vision_provider

logger = logging.getLogger(__name__)

TICKET_PREFIX = os.getenv("TICKET_PREFIX", "WST") or "WST"


def next_ticket_id(db: Session) -> str:
    """Generate the next sequential {PREFIX}-### ticket id."""
    tickets = [r.ticket_id for r in db.query(WasteReport.ticket_id).all() if r.ticket_id]
    numbers = []
    for ticket in tickets:
        match = re.search(r"(\d+)", ticket)
        if match:
            numbers.append(int(match.group(1)))
    next_number = max(numbers, default=0) + 1
    return f"{TICKET_PREFIX}-{next_number:03d}"


def process_report(
    db: Session,
    *,
    location: LocationIn,
    description: str = "",
    image_bytes: Optional[bytes] = None,
    created_by: Optional[str] = None,
    analysis: Optional["VisionAnalysis"] = None,
) -> WasteReport:
    """Run the full processing workflow and persist a new report.

    When `analysis` is provided it is used directly; otherwise the vision
    provider is called. This lets the intake gate analyze once and reuse
    the result (and its confidence) without a second provider call.
    """
    if analysis is None:
        provider = get_vision_provider()
        try:
            analysis = provider.analyze(
                image_bytes=image_bytes,
                text=description or None,
                address=location.address,
            )
        except Exception as exc:  # noqa: BLE001 - a provider failure must not break intake
            logger.warning("Vision provider failed, using mock fallback: %s", exc)
            from services.vision import MockVisionProvider

            analysis = MockVisionProvider().analyze(
                image_bytes=image_bytes,
                text=description or None,
                address=location.address,
            )

    severity = severity_label(analysis.severity_score)

    hotspot, _created = find_or_create_hotspot(
        db,
        lat=location.lat,
        lng=location.lng,
        address=location.address,
    )

    priority = compute_priority(
        severity_score=analysis.severity_score,
        hazard_level=analysis.hazard_level,
        waste_type=analysis.waste_type.value,
        address=location.address,
        report_count=hotspot.report_count,
    )

    location_row = LocationRow(
        id=str(uuid.uuid4()),
        lat=location.lat,
        lng=location.lng,
        address=location.address,
    )
    db.add(location_row)
    db.flush()

    report = WasteReport(
        id=str(uuid.uuid4()),
        ticket_id=next_ticket_id(db),
        location_id=location_row.id,
        waste_type=analysis.waste_type.value,
        severity=severity,
        priority=priority,
        description=description or analysis.description,
        image_url=None,
        status="pending",
        created_by=created_by,
        severity_score=analysis.severity_score,
        hazard_level=analysis.hazard_level,
        estimated_size=analysis.estimated_size,
        visible_hazards=analysis.visible_hazards,
        recommended_action=analysis.recommended_action,
        confidence=analysis.confidence,
        hotspot_id=hotspot.id,
    )
    db.add(report)
    db.flush()

    report.status_history.append(
        StatusHistory(
            id=str(uuid.uuid4()),
            report_id=report.id,
            from_status=None,
            to_status="pending",
            notes="Report received via processing workflow",
            created_at=datetime.utcnow(),
        )
    )

    recompute_importance(db, hotspot)
    hotspot.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(report)

    # Business layer: open a marketplace listing + alert matching vendors,
    # or escalate hazardous / high-priority reports to the community head.
    from services.market import route_report

    route_report(db, report)

    return report