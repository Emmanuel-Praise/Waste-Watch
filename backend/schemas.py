"""
Pydantic schemas for the API layer.

Response schemas read from ORM objects (from_attributes); request
schemas validate incoming payloads.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class WasteType(str, Enum):
    PLASTIC = "plastic"
    ORGANIC = "organic"
    MIXED = "mixed"
    HAZARDOUS = "hazardous"
    MEDICAL = "medical"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Status(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    ASSIGNED = "assigned"
    CLEARED = "cleared"


class LocationIn(BaseModel):
    lat: float
    lng: float
    address: str


class LocationOut(LocationIn):
    model_config = ConfigDict(from_attributes=True)


class VisionAnalysis(BaseModel):
    waste_type: WasteType
    severity_score: int
    hazard_level: str
    estimated_size: str
    visible_hazards: List[str] = []
    description: str
    recommended_action: str
    confidence: float


class HotspotOut(BaseModel):
    id: str
    lat: float
    lng: float
    address: Optional[str] = None
    report_count: int
    importance: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class TeamOut(BaseModel):
    id: str
    name: str
    area: Optional[str] = None
    active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StatusHistoryOut(BaseModel):
    id: str
    report_id: str
    from_status: Optional[str] = None
    to_status: str
    changed_by: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WasteReportOut(BaseModel):
    id: str
    ticket_id: str
    location: LocationOut
    waste_type: str
    severity: str
    priority: str
    description: str
    image_url: Optional[str] = None
    status: str
    assigned_team_id: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    status_history: List[StatusHistoryOut] = []

    severity_score: Optional[int] = None
    hazard_level: Optional[str] = None
    estimated_size: Optional[str] = None
    visible_hazards: Optional[List[str]] = None
    recommended_action: Optional[str] = None
    confidence: Optional[float] = None
    hotspot_id: Optional[str] = None
    related_reports: int = 1

    model_config = ConfigDict(from_attributes=True)


class ReportCreate(BaseModel):
    location: LocationIn
    waste_type: WasteType
    severity: Priority
    priority: Priority
    description: str
    image_url: Optional[str] = None


class ReportStatusUpdate(BaseModel):
    status: Status
    notes: Optional[str] = None


class ReportAssign(BaseModel):
    team_id: str


class CitizenMessageOut(BaseModel):
    id: str
    report_id: Optional[str] = None
    phone: Optional[str] = None
    kind: str
    text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CitizenReportOut(BaseModel):
    report: Optional[WasteReportOut] = None
    response: str


class DashboardStatsOut(BaseModel):
    total: int
    pending: int
    verified: int
    assigned: int
    cleared: int
    by_priority: dict
    by_type: dict