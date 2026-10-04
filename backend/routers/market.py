"""
Marketplace API endpoints.

Public/vendor-facing listing browser plus the claim lifecycle that moves
waste from "available" through vendor reservation, collector pickup and
final settlement.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import Claim, Collector, Listing, Vendor, WasteReport
from schemas import WasteReportOut
from services.market import advance_claim, assign_collector, create_claim, market_stats

router = APIRouter()


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #

class PayoutOut(BaseModel):
    id: str
    role: str
    payee_name: Optional[str] = None
    phone: Optional[str] = None
    amount: float
    status: str

    model_config = {"from_attributes": True}


class VendorLite(BaseModel):
    id: str
    business_name: str
    phone: str

    model_config = {"from_attributes": True}


class CollectorLite(BaseModel):
    id: str
    full_name: str
    phone: str

    model_config = {"from_attributes": True}


class ClaimListingSummaryOut(BaseModel):
    id: str
    waste_type: str
    quantity_kg: float
    report_ticket_id: Optional[str] = None
    report_address: Optional[str] = None


class ClaimOut(BaseModel):
    id: str
    listing_id: str
    listing: Optional[ClaimListingSummaryOut] = None
    vendor: Optional[VendorLite] = None
    collector: Optional[CollectorLite] = None
    quantity_kg: float
    price_per_kg: float
    total_value: float
    reporter_commission: float
    collector_payout: float
    platform_fee: float
    status: str
    created_at: str
    payouts: List[PayoutOut] = []

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: str
    report: WasteReportOut
    waste_type: str
    quantity_kg: float
    available_kg: float
    price_per_kg: float
    status: str
    created_at: str
    claims: List[ClaimOut] = []

    model_config = {"from_attributes": True}


class ClaimCreate(BaseModel):
    vendor_id: str
    quantity_kg: float = Field(gt=0)


class CollectorAssign(BaseModel):
    collector_id: str


class ClaimStatusUpdate(BaseModel):
    status: str


# --------------------------------------------------------------------------- #
# Serialization helpers (ORM -> dicts the pydantic models accept)
# --------------------------------------------------------------------------- #

def _claim_out(claim: Claim) -> dict:
    listing = claim.listing
    report = listing.report if listing else None
    listing_summary = None
    if listing is not None:
        listing_summary = {
            "id": listing.id,
            "waste_type": listing.waste_type,
            "quantity_kg": listing.quantity_kg or 0.0,
            "report_ticket_id": report.ticket_id if report else None,
            "report_address": (
                getattr(report.location, "address", None) if report is not None else None
            ),
        }
    return {
        "id": claim.id,
        "listing_id": claim.listing_id,
        "listing": listing_summary,
        "vendor": claim.vendor,
        "collector": claim.collector,
        "quantity_kg": claim.quantity_kg or 0.0,
        "price_per_kg": claim.price_per_kg or 0.0,
        "total_value": claim.total_value or 0.0,
        "reporter_commission": claim.reporter_commission or 0.0,
        "collector_payout": claim.collector_payout or 0.0,
        "platform_fee": claim.platform_fee or 0.0,
        "status": claim.status,
        "created_at": claim.created_at.isoformat(),
        "payouts": claim.payouts or [],
    }


def _listing_out(listing: Listing) -> dict:
    report = listing.report
    report_out = WasteReportOut.model_validate(report).model_dump(mode="json")
    return {
        "id": listing.id,
        "report": report_out,
        "waste_type": listing.waste_type,
        "quantity_kg": listing.quantity_kg or 0.0,
        "available_kg": listing.available_kg or 0.0,
        "price_per_kg": listing.price_per_kg or 0.0,
        "status": listing.status,
        "created_at": listing.created_at.isoformat(),
        "claims": [_claim_out(c) for c in (listing.claims or [])],
    }


# --------------------------------------------------------------------------- #
# Listings
# --------------------------------------------------------------------------- #

@router.get("/listings", response_model=List[ListingOut])
def list_listings(
    waste_type: Optional[str] = None,
    status: Optional[str] = None,
    vendor_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Browse marketplace listings, newest first."""
    query = db.query(Listing)
    if waste_type:
        query = query.filter(Listing.waste_type == waste_type)
    if status:
        query = query.filter(Listing.status == status)

    listings = query.order_by(Listing.created_at.desc()).all()

    if vendor_id:
        # Vendors still see everything, but listings they already claimed are
        # flagged client-side; this filter keeps only listings with a claim
        # from this vendor (their "purchases").
        listings = [l for l in listings if any(c.vendor_id == vendor_id for c in (l.claims or []))]

    return [_listing_out(l) for l in listings]


@router.get("/listings/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: str, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _listing_out(listing)


@router.post("/listings/{listing_id}/claims", response_model=ClaimOut, status_code=201)
def reserve_quantity(listing_id: str, payload: ClaimCreate, db: Session = Depends(get_db)):
    """A vendor reserves part (or all) of a listing's quantity."""
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status == "completed":
        raise HTTPException(status_code=400, detail="This listing is fully delivered")

    vendor = db.get(Vendor, payload.vendor_id)
    if not vendor:
        raise HTTPException(status_code=400, detail="Unknown vendor - please sign up first")
    if vendor.status != "active":
        raise HTTPException(status_code=400, detail="This vendor account is not active")

    try:
        claim = create_claim(db, listing, vendor, payload.quantity_kg)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _claim_out(claim)


# --------------------------------------------------------------------------- #
# Claims
# --------------------------------------------------------------------------- #

@router.get("/claims", response_model=List[ClaimOut])
def list_claims(
    vendor_id: Optional[str] = None,
    collector_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Claim)
    if vendor_id:
        query = query.filter(Claim.vendor_id == vendor_id)
    if collector_id:
        query = query.filter(Claim.collector_id == collector_id)
    if status:
        query = query.filter(Claim.status == status)
    claims = query.order_by(Claim.created_at.desc()).all()
    return [_claim_out(c) for c in claims]


@router.post("/claims/{claim_id}/collector", response_model=ClaimOut)
def take_job(claim_id: str, payload: CollectorAssign, db: Session = Depends(get_db)):
    """A collector claims the pickup job for this reservation."""
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    collector = db.get(Collector, payload.collector_id)
    if not collector:
        raise HTTPException(status_code=400, detail="Unknown collector - please sign up first")
    if collector.status != "active":
        raise HTTPException(status_code=400, detail="This collector account is not active")

    try:
        claim = assign_collector(db, claim, collector)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _claim_out(claim)


@router.put("/claims/{claim_id}/status", response_model=ClaimOut)
def update_claim_status(claim_id: str, payload: ClaimStatusUpdate, db: Session = Depends(get_db)):
    """Advance the claim lifecycle (collecting -> collected -> delivered) or cancel."""
    claim = db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    try:
        claim = advance_claim(db, claim, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _claim_out(claim)


# --------------------------------------------------------------------------- #
# Stats
# --------------------------------------------------------------------------- #

@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Marketplace totals for the dashboard."""
    return market_stats(db)
