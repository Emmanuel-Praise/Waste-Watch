"""
Partner (business network) API endpoints.

Vendors (buyers of sorted materials) and EcoCollectors (citizens earning
from collection work) both sign up here with an ID card. The signup is
deliberately lightweight: name + phone + waste interests / zone, with an
optional ID document photo stored in the media directory.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import MEDIA_DIR
from database import get_db
from models import Claim, Collector, Vendor, WASTE_TYPES
from services.whatsapp import digits_of

router = APIRouter()

_ID_IMAGE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}


def _persist_id_card(image_bytes: bytes, mime_type: str) -> Optional[str]:
    extension = _ID_IMAGE_EXTENSIONS.get((mime_type or "").lower(), "jpg")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"id-{uuid.uuid4().hex}.{extension}"
    (MEDIA_DIR / filename).write_bytes(image_bytes)
    return f"/media/{filename}"


def _normalize_types(raw: str) -> List[str]:
    types = [t.strip().lower() for t in (raw or "").split(",") if t.strip()]
    valid = set(WASTE_TYPES)
    return [t for t in types if t in valid] or ["plastic"]


def _normalize_phone(raw: str) -> str:
    digits = digits_of(raw)
    if not digits:
        raise HTTPException(status_code=400, detail="A valid phone number is required")
    return f"+{digits}" if not digits.startswith("+") else digits


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class VendorOut(BaseModel):
    id: str
    business_name: str
    owner_name: str
    phone: str
    id_number: Optional[str] = None
    id_card_url: Optional[str] = None
    waste_types: List[str] = []
    zone: Optional[str] = None
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class CollectorOut(BaseModel):
    id: str
    full_name: str
    phone: str
    id_number: Optional[str] = None
    id_card_url: Optional[str] = None
    zone: Optional[str] = None
    status: str
    jobs_completed: int
    total_earnings: float
    created_at: str

    model_config = {"from_attributes": True}


class ClaimSummary(BaseModel):
    id: str
    listing_id: str
    quantity_kg: float
    total_value: float
    collector_payout: float
    reporter_commission: float
    status: str
    created_at: str
    waste_type: Optional[str] = None
    location: Optional[str] = None

    model_config = {"from_attributes": True}


def _vendor_out(vendor: Vendor) -> dict:
    return {
        "id": vendor.id,
        "business_name": vendor.business_name,
        "owner_name": vendor.owner_name,
        "phone": vendor.phone,
        "id_number": vendor.id_number,
        "id_card_url": vendor.id_card_url,
        "waste_types": vendor.waste_types or [],
        "zone": vendor.zone,
        "status": vendor.status,
        "created_at": vendor.created_at.isoformat(),
    }


def _collector_out(collector: Collector) -> dict:
    return {
        "id": collector.id,
        "full_name": collector.full_name,
        "phone": collector.phone,
        "id_number": collector.id_number,
        "id_card_url": collector.id_card_url,
        "zone": collector.zone,
        "status": collector.status,
        "jobs_completed": collector.jobs_completed or 0,
        "total_earnings": collector.total_earnings or 0.0,
        "created_at": collector.created_at.isoformat(),
    }


def _claim_summary(claim: Claim) -> dict:
    listing = claim.listing
    report = listing.report if listing else None
    location = getattr(report.location, "address", None) if report else None
    return {
        "id": claim.id,
        "listing_id": claim.listing_id,
        "quantity_kg": claim.quantity_kg or 0.0,
        "total_value": claim.total_value or 0.0,
        "collector_payout": claim.collector_payout or 0.0,
        "reporter_commission": claim.reporter_commission or 0.0,
        "status": claim.status,
        "created_at": claim.created_at.isoformat(),
        "waste_type": listing.waste_type if listing else None,
        "location": location,
    }


# --------------------------------------------------------------------------- #
# Vendors
# --------------------------------------------------------------------------- #

@router.post("/vendors", status_code=410)
async def register_vendor():
    """Disabled: vendor signup happens via WhatsApp ('sell ...'). Dashboard is read-only."""
    raise HTTPException(
        status_code=410,
        detail="Web vendor signup is disabled. Please sign up via WhatsApp: send 'sell <business> | <owner> | <zone> | <plastic,organic,mixed>'.",
    )


@router.get("/vendors", response_model=List[VendorOut])
def list_vendors(db: Session = Depends(get_db)):
    vendors = db.query(Vendor).order_by(Vendor.created_at.desc()).all()
    return [_vendor_out(v) for v in vendors]


@router.get("/vendors/{vendor_id}", response_model=VendorOut)
def get_vendor(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return _vendor_out(vendor)


@router.get("/vendors/{vendor_id}/claims", response_model=List[ClaimSummary])
def vendor_claims(vendor_id: str, db: Session = Depends(get_db)):
    claims = (
        db.query(Claim)
        .filter(Claim.vendor_id == vendor_id)
        .order_by(Claim.created_at.desc())
        .all()
    )
    return [_claim_summary(c) for c in claims]


# --------------------------------------------------------------------------- #
# Collectors
# --------------------------------------------------------------------------- #

@router.post("/collectors", status_code=410)
async def register_collector():
    """Disabled: collector signup happens via WhatsApp ('earn ...'). Dashboard is read-only."""
    raise HTTPException(
        status_code=410,
        detail="Web collector signup is disabled. Please sign up via WhatsApp: send 'earn <full name> | <zone>'.",
    )


@router.get("/collectors", response_model=List[CollectorOut])
def list_collectors(db: Session = Depends(get_db)):
    collectors = db.query(Collector).order_by(Collector.created_at.desc()).all()
    return [_collector_out(c) for c in collectors]


@router.get("/collectors/{collector_id}", response_model=CollectorOut)
def get_collector(collector_id: str, db: Session = Depends(get_db)):
    collector = db.get(Collector, collector_id)
    if not collector:
        raise HTTPException(status_code=404, detail="Collector not found")
    return _collector_out(collector)


@router.get("/collectors/{collector_id}/jobs", response_model=List[ClaimSummary])
def collector_jobs(collector_id: str, db: Session = Depends(get_db)):
    claims = (
        db.query(Claim)
        .filter(Claim.collector_id == collector_id)
        .order_by(Claim.created_at.desc())
        .all()
    )
    return [_claim_summary(c) for c in claims]
