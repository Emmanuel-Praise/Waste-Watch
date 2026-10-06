"""
SQLAlchemy ORM models for the waste management system.

Designed for SQLite during development and PostgreSQL/Supabase-ready
for later steps (UUID-as-string columns, enums stored as strings so
PostGIS geometry can be layered onto the locations table).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="operator")
    phone = Column(String(30), nullable=True)
    # PBKDF2 password hash for dashboard login (NULL = login disabled,
    # e.g. auto-created WhatsApp citizens who never log in).
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuthToken(Base):
    """Dashboard login sessions. Tokens are random, expire after 30 days,
    and are revoked on logout."""

    __tablename__ = "auth_tokens"

    token = Column(String(64), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", lazy="joined")


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    area = Column(String(255), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Location(Base):
    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=_uuid)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    address = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Hotspot(Base):
    __tablename__ = "hotspots"

    id = Column(String(36), primary_key=True, default=_uuid)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    address = Column(String(255), nullable=True)
    report_count = Column(Integer, nullable=False, default=1)
    importance = Column(String(20), nullable=False, default="low")
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    reports = relationship("WasteReport", back_populates="hotspot", lazy="selectin")


class WasteReport(Base):
    __tablename__ = "waste_reports"

    id = Column(String(36), primary_key=True, default=_uuid)
    ticket_id = Column(String(20), unique=True, nullable=False)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=False)
    waste_type = Column(String(20), nullable=False)
    severity = Column(String(20), nullable=False)
    priority = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    assigned_team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    severity_score = Column(Integer, nullable=True)
    hazard_level = Column(String(20), nullable=True)
    estimated_size = Column(String(20), nullable=True)
    visible_hazards = Column(JSON, nullable=True)
    recommended_action = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    hotspot_id = Column(String(36), ForeignKey("hotspots.id"), nullable=True)

    location = relationship("Location", lazy="joined")
    assigned_team = relationship("Team", lazy="joined")
    hotspot = relationship("Hotspot", back_populates="reports", lazy="joined")
    status_history = relationship(
        "StatusHistory",
        back_populates="report",
        order_by="StatusHistory.created_at",
        lazy="selectin",
    )

    @property
    def related_reports(self) -> int:
        if self.hotspot and self.hotspot.report_count:
            return self.hotspot.report_count
        return 1


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(String(36), primary_key=True, default=_uuid)
    report_id = Column(String(36), ForeignKey("waste_reports.id"), nullable=False)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    changed_by = Column(String(36), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    report = relationship("WasteReport", back_populates="status_history")


class CitizenMessage(Base):
    __tablename__ = "citizen_messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    report_id = Column(String(36), ForeignKey("waste_reports.id"), nullable=True)
    phone = Column(String(30), nullable=True)
    kind = Column(String(30), nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    report = relationship("WasteReport", lazy="joined")


class PendingIntake(Base):
    """A citizen submission awaiting photo verification before a report is created."""

    __tablename__ = "pending_intakes"

    id = Column(String(36), primary_key=True, default=_uuid)
    phone = Column(String(30), nullable=False, index=True)
    image_path = Column(String(500), nullable=True)
    description = Column(Text, nullable=False, default="")
    address = Column(String(255), nullable=False, default="")
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    attempt_count = Column(Integer, nullable=False, default=1)
    # Conversation state: idle | asking_intent | collecting | awaiting_location
    state = Column(String(30), nullable=False, default="idle")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BrandNotified(Base):
    """Tracks which citizens already received the Waste Watch brand card, so we
    only send the logo image once per person instead of on every reply."""

    __tablename__ = "brand_notified"

    phone = Column(String(30), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Vendor(Base):
    """A waste vendor / recycler who buys sorted materials from the platform.

    Signs up with an ID card and declares which waste types they are
    interested in. When a matching report arrives, the vendor is alerted.
    """

    __tablename__ = "vendors"

    id = Column(String(36), primary_key=True, default=_uuid)
    business_name = Column(String(255), nullable=False)
    owner_name = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=False, index=True)
    id_number = Column(String(100), nullable=True)
    id_card_url = Column(String(500), nullable=True)
    waste_types = Column(JSON, nullable=False, default=list)  # e.g. ["plastic", "organic"]
    zone = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active | suspended
    created_at = Column(DateTime, default=datetime.utcnow)


class Collector(Base):
    """A citizen looking for work who collects, sorts and delivers waste to
    vendors. The platform pays them for each completed job."""

    __tablename__ = "collectors"

    id = Column(String(36), primary_key=True, default=_uuid)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=False, index=True)
    id_number = Column(String(100), nullable=True)
    id_card_url = Column(String(500), nullable=True)
    zone = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active | suspended
    jobs_completed = Column(Integer, nullable=False, default=0)
    total_earnings = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Listing(Base):
    """A sellable waste listing generated automatically from a report.

    The whole quantity does not have to be sold at once: a vendor can buy
    only part (e.g. just the plastic from a mixed pile). Whatever remains
    stays available for community pickup.
    """

    __tablename__ = "listings"

    id = Column(String(36), primary_key=True, default=_uuid)
    report_id = Column(String(36), ForeignKey("waste_reports.id"), nullable=False, unique=True)
    waste_type = Column(String(20), nullable=False)
    quantity_kg = Column(Float, nullable=False, default=0.0)
    available_kg = Column(Float, nullable=False, default=0.0)
    price_per_kg = Column(Float, nullable=False, default=0.0)
    # available | partially_claimed | reserved | completed
    status = Column(String(30), nullable=False, default="available")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    report = relationship("WasteReport", lazy="joined")
    claims = relationship(
        "Claim", back_populates="listing", order_by="Claim.created_at", lazy="selectin"
    )


class Claim(Base):
    """A vendor's reservation of part (or all) of a listing, and its
    collection lifecycle through an assigned collector."""

    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, default=_uuid)
    listing_id = Column(String(36), ForeignKey("listings.id"), nullable=False)
    vendor_id = Column(String(36), ForeignKey("vendors.id"), nullable=False)
    collector_id = Column(String(36), ForeignKey("collectors.id"), nullable=True)
    quantity_kg = Column(Float, nullable=False)
    price_per_kg = Column(Float, nullable=False, default=0.0)
    total_value = Column(Float, nullable=False, default=0.0)
    reporter_commission = Column(Float, nullable=False, default=0.0)
    collector_payout = Column(Float, nullable=False, default=0.0)
    platform_fee = Column(Float, nullable=False, default=0.0)
    # reserved | collecting | collected | delivered | paid | cancelled
    status = Column(String(20), nullable=False, default="reserved")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    listing = relationship("Listing", back_populates="claims", lazy="joined")
    vendor = relationship("Vendor", lazy="joined")
    collector = relationship("Collector", lazy="joined")
    payouts = relationship("Payout", back_populates="claim", lazy="selectin")


class Payout(Base):
    """The money ledger for a claim: reporter commission, collector pay and
    the platform fee. Rows become 'paid' when the claim is delivered."""

    __tablename__ = "payouts"

    id = Column(String(36), primary_key=True, default=_uuid)
    claim_id = Column(String(36), ForeignKey("claims.id"), nullable=False)
    role = Column(String(20), nullable=False)  # reporter | collector | platform
    payee_name = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="pending")  # pending | paid
    created_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="payouts")


class ProcessedMessage(Base):
    """Persisted WhatsApp message IDs already acted on.

    Meta re-delivers webhook events it thinks we missed (surviving even a
    backend restart), and the in-memory dedupe would forget them. Persisting
    the IDs here means an old image/text/location is never acted on twice —
    the bot never "suddenly" reacts to a photo the citizen didn't just send.
    """

    __tablename__ = "processed_messages"

    message_id = Column(String(200), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)


WASTE_TYPES = ["plastic", "organic", "mixed", "hazardous", "medical"]
PRIORITIES = ["low", "medium", "high", "critical"]
STATUSES = ["pending", "verified", "assigned", "cleared"]
ROLES = ["admin", "council", "operator", "team", "citizen"]
HAZARD_LEVELS = ["low", "medium", "high", "critical"]
SIZES = ["small", "medium", "large"]

WORKFLOW_ORDER = {status: index for index, status in enumerate(STATUSES)}