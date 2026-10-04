"""
Waste marketplace business logic.

Turns verified waste reports into a circular-economy marketplace:

    report (plastic/organic/mixed)  ->  listing (kg available)
        -> matching vendors are alerted (WhatsApp)
        -> vendor reserves the quantity they want (even part of it)
        -> an EcoCollector is assigned to collect, sort and deliver
        -> vendor money is split: reporter commission + collector pay + platform fee

Hazardous / medical / high-priority reports are routed to the community
head instead, so dangerous material never enters the resale loop.

Everything here is best-effort with respect to messaging: a WhatsApp
failure must never break a report, claim or payout.
"""

import logging
import uuid
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from config import settings
from models import (
    Claim,
    Collector,
    CitizenMessage,
    Listing,
    Payout,
    Vendor,
    WasteReport,
)
from services.whatsapp import digits_of, send_text_message

logger = logging.getLogger(__name__)

# Waste types that have a resale value and can enter the marketplace.
SELLABLE_TYPES = ("plastic", "organic", "mixed")

# Rough weight estimates derived from the AI's estimated_size classification.
SIZE_TO_KG = {"small": 15.0, "medium": 60.0, "large": 250.0}

# Default farm-gate prices per kg (FCFA) paid by vendors.
DEFAULT_PRICES_PER_KG = {"plastic": 150.0, "organic": 60.0, "mixed": 100.0}

CLAIM_FLOW = {
    "reserved": 0,
    "collecting": 1,
    "collected": 2,
    "delivered": 3,
    "paid": 4,
    "cancelled": -1,
}

_STATUS_LABELS = {
    "reserved": "reserved",
    "collecting": "collecting",
    "collected": "collected",
    "delivered": "delivered",
    "paid": "paid",
    "cancelled": "cancelled",
}


def _sep() -> str:
    return "\u2500" * 24


def estimate_quantity_kg(estimated_size: Optional[str]) -> float:
    """Estimate the sellable weight of a report from its AI size estimate."""
    return SIZE_TO_KG.get((estimated_size or "").lower(), SIZE_TO_KG["medium"])


def price_for_type(waste_type: str) -> float:
    """Default vendor price per kg for a waste type."""
    return DEFAULT_PRICES_PER_KG.get((waste_type or "").lower(), 0.0)


def is_community_routed(report: WasteReport) -> bool:
    """True when a report must go to the community head, not the marketplace.

    Only dangerous material (hazardous / medical) is kept out of the resale
    loop. A sellable type stays on the marketplace even when it is urgent:
    faster pickup is exactly what an urgent pile needs.
    """
    return (report.waste_type or "").lower() in ("hazardous", "medical")


# --------------------------------------------------------------------------- #
# Report routing: marketplace listing + vendor alerts OR community head
# --------------------------------------------------------------------------- #

def route_report(db: Session, report: WasteReport) -> None:
    """Entry point called after a report is created.

    Sellable reports open a marketplace listing and alert matching vendors.
    Hazardous / medical / high-priority reports are escalated to the
    community head. Safe to call for every report; non-sellable, safe
    reports simply do nothing.
    """
    try:
        if is_community_routed(report):
            _notify_community_head(db, report)
            return
        if (report.waste_type or "").lower() in SELLABLE_TYPES:
            listing = maybe_create_listing(db, report)
            if listing:
                _alert_matching_vendors(db, report, listing)
    except Exception:  # noqa: BLE001 - routing must never break report creation
        logger.exception("Market routing failed for report %s", report.ticket_id)
        db.rollback()


def maybe_create_listing(db: Session, report: WasteReport) -> Optional[Listing]:
    """Create the marketplace listing for a report (idempotent)."""
    existing = db.query(Listing).filter(Listing.report_id == report.id).first()
    if existing:
        return existing

    quantity = estimate_quantity_kg(report.estimated_size)
    if quantity <= 0:
        return None

    listing = Listing(
        id=str(uuid.uuid4()),
        report_id=report.id,
        waste_type=report.waste_type,
        quantity_kg=quantity,
        available_kg=quantity,
        price_per_kg=price_for_type(report.waste_type),
        status="available",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    logger.info(
        "Listing created for %s: %.0f kg %s at %.0f FCFA/kg",
        report.ticket_id, quantity, report.waste_type, listing.price_per_kg,
    )
    return listing


def _report_address(report: WasteReport) -> str:
    loc = getattr(report, "location", None)
    return (getattr(loc, "address", "") or "") if loc is not None else ""


def _record(db: Session, *, phone: str, kind: str, text: str, report: WasteReport) -> None:
    """Persist an outbound business message and try WhatsApp delivery."""
    db.add(
        CitizenMessage(
            id=str(uuid.uuid4()),
            report_id=report.id,
            phone=phone,
            kind=kind,
            text=text,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    channel = (settings.message_channel or "log").lower()
    if channel == "whatsapp" and digits_of(phone):
        try:
            send_text_message(digits_of(phone), text)
        except Exception as exc:  # noqa: BLE001 - alerts are best effort
            logger.warning("Market alert delivery to %s failed: %s", phone, exc)


def _alert_matching_vendors(db: Session, report: WasteReport, listing: Listing) -> None:
    """Notify every active vendor interested in this waste type."""
    vendors: Iterable[Vendor] = db.query(Vendor).filter(Vendor.status == "active").all()
    waste = (report.waste_type or "").lower()
    address = _report_address(report)
    for vendor in vendors:
        interested = [str(t).lower() for t in (vendor.waste_types or [])]
        if waste not in interested:
            continue
        text = (
            "\U0001F4B0 *Waste Watch \u00b7 New Stock Available*\n"
            + _sep()
            + f"\n\u267B\ufe0f *Type:* {waste.title()} waste\n"
            f"\u2696\ufe0f *Quantity:* ~{listing.quantity_kg:.0f} kg\n"
            f"\U0001F4B8 *Price:* {listing.price_per_kg:.0f} FCFA/kg\n"
        )
        if address:
            text += f"\U0001F4CD *Location:* {address}\n"
        text += f"\U0001F3AB *Report:* {report.ticket_id}\n\n"
        text += (
            "Reserve all or only the quantity you need on the Waste Watch "
            "marketplace. The rest stays available for community pickup."
        )
        try:
            _record(db, phone=vendor.phone, kind="vendor_alert", text=text, report=report)
        except Exception:  # noqa: BLE001
            logger.exception("Vendor alert failed for %s", vendor.business_name)


def _notify_community_head(db: Session, report: WasteReport) -> None:
    """Escalate hazardous / medical / high-priority reports to the community head."""
    address = _report_address(report)
    text = (
        "\U0001F6A8 *Waste Watch \u00b7 Community Escalation*\n"
        + _sep()
        + f"\n\U0001F3AB *Ticket:* {report.ticket_id}\n"
        f"\u267B\ufe0f *Type:* {(report.waste_type or '?').title()} waste\n"
        f"\u26A0\ufe0f *Hazard:* {(report.hazard_level or '?').title()}\n"
        f"\U0001F525 *Priority:* {(report.priority or '?').title()}\n"
    )
    if address:
        text += f"\U0001F4CD *Location:* {address}\n"
    text += "\n"
    text += (report.recommended_action or "Please organise a community response.").strip()

    phone = settings.community_head_phone
    kind = "community_head"
    if not phone:
        logger.info(
            "COMMUNITY_HEAD_PHONE not configured; escalation for %s recorded in log only.",
            report.ticket_id,
        )
        phone = "community-head"
    try:
        _record(db, phone=phone, kind=kind, text=text, report=report)
    except Exception:  # noqa: BLE001
        logger.exception("Community head escalation failed for %s", report.ticket_id)


# --------------------------------------------------------------------------- #
# Claim lifecycle
# --------------------------------------------------------------------------- #

def _recompute_listing_status(db: Session, listing: Listing) -> None:
    """Refresh a listing's status from its remaining quantity and claims."""
    claims = db.query(Claim).filter(Claim.listing_id == listing.id).all()
    active = [c for c in claims if c.status not in ("cancelled",)]
    delivered = [c for c in active if c.status in ("delivered", "paid")]

    if listing.available_kg <= 0 and active:
        listing.status = "reserved"
    elif listing.available_kg < listing.quantity_kg:
        listing.status = "partially_claimed"
    else:
        listing.status = "available"

    if active and len(delivered) == len(active) and listing.available_kg <= 0:
        listing.status = "completed"
    db.commit()


def create_claim(db: Session, listing: Listing, vendor: Vendor, quantity_kg: float) -> Claim:
    """A vendor reserves part (or all) of a listing's quantity."""
    quantity = round(max(0.1, min(quantity_kg, listing.available_kg)), 1)
    if quantity <= 0:
        raise ValueError("No quantity left on this listing")

    total_value = round(quantity * listing.price_per_kg, 2)
    commission = round(total_value * settings.reporter_commission_pct / 100.0, 2)
    payout = round(total_value * settings.collector_payout_pct / 100.0, 2)
    fee = round(total_value - commission - payout, 2)

    claim = Claim(
        id=str(uuid.uuid4()),
        listing_id=listing.id,
        vendor_id=vendor.id,
        quantity_kg=quantity,
        price_per_kg=listing.price_per_kg,
        total_value=total_value,
        reporter_commission=commission,
        collector_payout=payout,
        platform_fee=fee,
        status="reserved",
    )
    db.add(claim)
    db.flush()

    listing.available_kg = round(max(0.0, listing.available_kg - quantity), 1)
    _recompute_listing_status(db, listing)
    db.commit()
    db.refresh(claim)

    # Tell the reporter they earned a commission.
    _notify_reporter_commission(db, claim)
    return claim


def _notify_reporter_commission(db: Session, claim: Claim) -> None:
    report = claim.listing.report if claim.listing else None
    if not report or not report.created_by:
        return
    from models import User

    user = db.get(User, report.created_by)
    if not user or not user.phone:
        return
    text = (
        "\U0001F4B0 *Waste Watch \u00b7 You Earned a Commission!*\n"
        + _sep()
        + f"\n\U0001F3AB *Ticket:* {report.ticket_id}\n"
        f"\U0001F4B0 *Commission:* {claim.reporter_commission:.0f} FCFA\n\n"
        "A vendor reserved part of your reported waste. Once it is collected "
        "and delivered, your commission is released. Thank you for reporting!"
    )
    try:
        _record(db, phone=user.phone, kind="commission", text=text, report=report)
    except Exception:  # noqa: BLE001
        logger.exception("Commission notification failed for %s", report.ticket_id)


def assign_collector(db: Session, claim: Claim, collector: Collector) -> Claim:
    """A collector takes the job: pick up, sort and deliver to the vendor."""
    if claim.status != "reserved":
        raise ValueError(f"Claim is already '{claim.status}'")
    claim.collector_id = collector.id
    claim.status = "collecting"
    db.commit()
    db.refresh(claim)
    return claim


def advance_claim(db: Session, claim: Claim, new_status: str) -> Claim:
    """Move a claim forward through its lifecycle (or cancel it)."""
    new_status = _STATUS_LABELS.get(new_status, new_status)
    if new_status == "cancelled":
        return _cancel_claim(db, claim)

    current = CLAIM_FLOW.get(claim.status, -1)
    target = CLAIM_FLOW.get(new_status)
    if target is None:
        raise ValueError(f"Unknown claim status '{new_status}'")
    if target != current + 1:
        raise ValueError(f"Cannot move claim from '{claim.status}' to '{new_status}'")

    claim.status = new_status
    if new_status == "delivered":
        _settle_claim(db, claim)
    db.commit()
    db.refresh(claim)
    return claim


def _cancel_claim(db: Session, claim: Claim) -> Claim:
    """Cancel a reservation and return its quantity to the listing."""
    if claim.status in ("delivered", "paid"):
        raise ValueError("A delivered claim can no longer be cancelled")
    claim.status = "cancelled"
    listing = claim.listing
    if listing:
        listing.available_kg = round(min(listing.quantity_kg, listing.available_kg + claim.quantity_kg), 1)
        _recompute_listing_status(db, listing)
    db.commit()
    db.refresh(claim)
    return claim


def _settle_claim(db: Session, claim: Claim) -> None:
    """Release money when the collector delivers to the vendor."""
    listing = claim.listing
    report: Optional[WasteReport] = listing.report if listing else None

    existing = db.query(Payout).filter(Payout.claim_id == claim.id).all()
    if not existing:
        reporter_name = reporter_phone = None
        if report and report.created_by:
            from models import User

            user = db.get(User, report.created_by)
            if user:
                reporter_name, reporter_phone = user.name, user.phone

        rows = [
            Payout(
                id=str(uuid.uuid4()),
                claim_id=claim.id,
                role="reporter",
                payee_name=reporter_name,
                phone=reporter_phone,
                amount=claim.reporter_commission,
                status="pending",
            ),
            Payout(
                id=str(uuid.uuid4()),
                claim_id=claim.id,
                role="collector",
                payee_name=claim.collector.full_name if claim.collector else None,
                phone=claim.collector.phone if claim.collector else None,
                amount=claim.collector_payout,
                status="pending",
            ),
            Payout(
                id=str(uuid.uuid4()),
                claim_id=claim.id,
                role="platform",
                payee_name="Waste Watch",
                phone=None,
                amount=claim.platform_fee,
                status="paid",
            ),
        ]
        for row in rows:
            db.add(row)
        db.flush()

    for payout in db.query(Payout).filter(Payout.claim_id == claim.id).all():
        if payout.role in ("reporter", "collector"):
            payout.status = "paid"

    if claim.collector:
        claim.collector.jobs_completed = (claim.collector.jobs_completed or 0) + 1
        claim.collector.total_earnings = round(
            (claim.collector.total_earnings or 0.0) + claim.collector_payout, 2
        )

    if listing:
        _recompute_listing_status(db, listing)

    db.flush()

    # Notify reporter + collector + vendor of the settled deal.
    if report:
        try:
            for payout in db.query(Payout).filter(Payout.claim_id == claim.id).all():
                if payout.role == "reporter" and payout.phone:
                    _record(
                        db,
                        phone=payout.phone,
                        kind="commission_paid",
                        text=(
                            "\U0001F389 *Waste Watch \u00b7 Commission Paid!*\n"
                            + _sep()
                            + f"\n\U0001F3AB *Ticket:* {report.ticket_id}\n"
                            f"\U0001F4B0 *Amount:* {payout.amount:.0f} FCFA\n\n"
                            "Thank you for reporting \u2013 Bamenda is cleaner and "
                            "waste is being recycled because of you!"
                        ),
                        report=report,
                    )
        except Exception:  # noqa: BLE001
            logger.exception("Settlement notification failed for claim %s", claim.id)


def vendor_alerts(db: Session, vendor_id: str) -> List[dict]:
    """Recent marketplace alerts sent to a vendor (for the vendor portal)."""
    rows = (
        db.query(CitizenMessage)
        .filter(CitizenMessage.kind == "vendor_alert", CitizenMessage.phone.isnot(None))
        .order_by(CitizenMessage.created_at.desc())
        .limit(20)
        .all()
    )
    digits = None
    vendor = db.get(Vendor, vendor_id)
    if vendor:
        digits = digits_of(vendor.phone)
    alerts = []
    for row in rows:
        if digits and digits_of(row.phone or "") == digits:
            alerts.append({"id": row.id, "text": row.text, "created_at": row.created_at.isoformat()})
    return alerts


def market_stats(db: Session) -> dict:
    """High-level marketplace numbers for the dashboard."""
    listings = db.query(Listing).all()
    claims = db.query(Claim).all()
    payouts = db.query(Payout).filter(Payout.status == "paid", Payout.role != "platform").all()

    total_kg = sum(l.quantity_kg or 0 for l in listings)
    available_kg = sum(l.available_kg or 0 for l in listings)
    sold_kg = sum(c.quantity_kg or 0 for c in claims if c.status in ("delivered", "paid"))
    reserved_kg = sum(c.quantity_kg or 0 for c in claims if c.status in ("reserved", "collecting", "collected"))
    paid_out = sum(p.amount or 0 for p in payouts)
    gmv = sum(c.total_value or 0 for c in claims if c.status in ("delivered", "paid"))

    return {
        "listings": len(listings),
        "total_kg": round(total_kg, 1),
        "available_kg": round(available_kg, 1),
        "reserved_kg": round(reserved_kg, 1),
        "sold_kg": round(sold_kg, 1),
        "active_claims": sum(1 for c in claims if c.status in ("reserved", "collecting", "collected")),
        "completed_claims": sum(1 for c in claims if c.status in ("delivered", "paid")),
        "gmv_fcfa": round(gmv, 0),
        "paid_out_fcfa": round(paid_out, 0),
        "vendors": db.query(Vendor).filter(Vendor.status == "active").count(),
        "collectors": db.query(Collector).filter(Collector.status == "active").count(),
    }
