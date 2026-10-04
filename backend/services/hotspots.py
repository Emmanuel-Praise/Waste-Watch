"""
Geographic duplicate / hotspot detection.

A new report is checked against existing active hotspots. If one exists
within the configured radius, the report is associated with it instead
of creating a disconnected duplicate incident. Multiple reports raise the
hotspot's importance. The current scan is a simple in-application loop;
it can be replaced with PostGIS spatial queries later.
"""

import math
import uuid
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from models import Hotspot, WasteReport
from services.priority import PRIORITY_RANK

EARTH_RADIUS_M = 6371000.0
DEFAULT_RADIUS_M = 150.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in meters between two coordinates."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def find_nearby_hotspot(
    db: Session,
    lat: float,
    lng: float,
    radius_m: float = DEFAULT_RADIUS_M,
) -> Optional[Hotspot]:
    """Return the nearest active hotspot within the radius, if any."""
    best: Optional[Hotspot] = None
    best_distance = float("inf")
    for hotspot in db.query(Hotspot).filter(Hotspot.status == "active").all():
        distance = haversine_m(lat, lng, hotspot.lat, hotspot.lng)
        if distance <= radius_m and distance < best_distance:
            best = hotspot
            best_distance = distance
    return best


def recompute_importance(db: Session, hotspot: Hotspot) -> None:
    """Set hotspot importance to the highest priority among its reports."""
    priorities = [
        r.priority
        for r in db.query(WasteReport.priority).filter(WasteReport.hotspot_id == hotspot.id).all()
    ]
    if priorities:
        hotspot.importance = max(priorities, key=lambda p: PRIORITY_RANK.get(p, 0))


def find_or_create_hotspot(
    db: Session,
    lat: float,
    lng: float,
    address: Optional[str] = None,
    radius_m: float = DEFAULT_RADIUS_M,
) -> Tuple[Hotspot, bool]:
    """Link a new report location to an existing hotspot or create a new one."""
    existing = find_nearby_hotspot(db, lat, lng, radius_m)
    if existing:
        existing.report_count = int(existing.report_count or 1) + 1
        existing.status = "active"
        return existing, False

    hotspot = Hotspot(
        id=str(uuid.uuid4()),
        lat=lat,
        lng=lng,
        address=address,
        report_count=1,
        importance="low",
        status="active",
    )
    db.add(hotspot)
    return hotspot, True