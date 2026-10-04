"""
Citizen notification service.

Builds the human-readable messages sent back to a citizen and routes
them through a MessageChannel. The dev LogMessageChannel persists
messages to the citizen_messages table (the simulator/log), so a real
WhatsApp channel can be added in a later step without touching the
rest of the application.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models import CitizenMessage, User, WasteReport
from services.whatsapp import send_text_message, to_e164

logger = logging.getLogger(__name__)

PRIORITY_LABELS = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
STATUS_LABELS = {"pending": "Pending", "verified": "Verified", "assigned": "Assigned", "cleared": "Cleared"}
WASTE_LABELS = {"plastic": "Plastic", "organic": "Organic", "mixed": "Mixed", "hazardous": "Hazardous", "medical": "Medical"}

_STATUS_EMOJI = {
    "pending": "\u23f3",
    "verified": "\u2705",
    "assigned": "\U0001F69B",
    "cleared": "\U0001F389",
}

_SEP = "\u2500" * 24

STATUS_MESSAGES = {
    "pending": (
        "\U0001F4DD *{}* is in the queue and pending review.\n"
        "We'll verify it soon and keep you posted."
    ),
    "verified": (
        "\u2705 Great news! *{}* has been verified.\n"
        "A cleanup team is being assigned next."
    ),
    "assigned": (
        "\U0001F69B *{}* \u2013 a cleanup crew is on the way!"
    ),
    "cleared": (
        "\U0001F389 *{}* has been cleared!\n"
        "Thank you for reporting \u2013 Bamenda is cleaner because of you.\U0001F64F"
    ),
}


class MessageChannel:
    """Interface any delivery channel (WhatsApp, SMS, log) must implement."""

    def send(self, phone: str, text: str) -> str:
        """Deliver text to a phone and return the delivered text."""
        raise NotImplementedError


class LogMessageChannel(MessageChannel):
    """
    Development channel: writes the message to the citizen_messages
    table so it appears in the simulator/log. Replaced by a real
    WhatsApp channel in a later step.
    """

    def __init__(self, db: Session):
        self.db = db

    def send(self, phone: str, text: str) -> str:
        entry = CitizenMessage(
            id=str(uuid.uuid4()),
            report_id=None,
            phone=phone,
            kind="generic",
            text=text,
            created_at=datetime.utcnow(),
        )
        self.db.add(entry)
        self.db.commit()
        return text


def _citizen_phone(db: Session, report: WasteReport) -> Optional[str]:
    """Return the citizen's phone number for a report, if known."""
    if not report.created_by:
        return None
    user = db.get(User, report.created_by)
    if user and user.phone:
        return user.phone
    return None


def _deliver_via_whatsapp(phone: str, text: str) -> None:
    """Send a message through the Cloud API when the WhatsApp channel is enabled."""
    channel = (settings.message_channel or "log").lower()
    if channel == "whatsapp":
        ok = send_text_message(to_e164(phone), text)
        logger.info("WhatsApp delivery to %s: %s", to_e164(phone), "ok" if ok else "failed")
    else:
        logger.info("Message channel '%s': message logged for %s (no WhatsApp send)", channel, phone)


def _record_message(
    db: Session,
    *,
    phone: str,
    report: WasteReport,
    kind: str,
    text: str,
) -> str:
    entry = CitizenMessage(
        id=str(uuid.uuid4()),
        report_id=report.id,
        phone=phone,
        kind=kind,
        text=text,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    db.commit()
    _deliver_via_whatsapp(phone, text)
    return text


def format_ticket_response(report: WasteReport) -> str:
    """Build the polished WhatsApp 'card' acknowledgment for a citizen."""
    severity = report.severity_score if report.severity_score is not None else 0
    waste = WASTE_LABELS.get(report.waste_type, report.waste_type.title() if report.waste_type else "Unknown")
    hazard = (report.hazard_level or "low").strip().lower().title()
    status = STATUS_LABELS.get(report.status, report.status.title() if report.status else "Pending")
    status_emoji = _STATUS_EMOJI.get(report.status, "\U0001F4CC")

    lines = [
        "\U0001F5D1\ufe0f *Waste Watch \u00b7 Report Received*",
        _SEP,
        f"\U0001F3AB *Ticket:* {report.ticket_id}",
        "",
        f"\u267B\ufe0f *Waste type:* {waste}",
        f"\u26A0\ufe0f *Severity:* {severity}/5 \u00b7 *Hazard:* {hazard}",
        f"{status_emoji} *Status:* {status}",
    ]

    loc = getattr(report, "location", None)
    address = (getattr(loc, "address", None) or "").strip() if loc is not None else ""
    if address:
        lines.append(f"\U0001F4CD *Location:* {address}")

    action = (report.recommended_action or "").strip()
    if action:
        lines.append("")
        lines.append(f"\U0001F9ED *Recommended action:*")
        lines.append(action)

    lines.append("")
    lines.append(_SEP)

    waste_low = (report.waste_type or "").lower()
    if waste_low in ("plastic", "organic", "mixed"):
        lines.append(
            "💰 This waste is sellable - it's now live on the *marketplace*. "
            "If a vendor reserves it, *you earn a 10% commission*, paid "
            "automatically when it's delivered. Want to earn more? Join the "
            "*EcoCollector* program - you keep *55%* per delivery job."
        )
        lines.append("")
    elif waste_low in ("hazardous", "medical"):
        lines.append(
            "⚠️ Hazardous / medical waste never enters the marketplace - we "
            "escalated it to the community head and response teams for safe "
            "handling."
        )
        lines.append("")

    lines.append(
        "We'll update you right here on this chat as your report is verified "
        "and assigned.\nThank you for helping keep Bamenda clean!\U0001F31F"
    )
    return "\n".join(lines)


def format_status_notification(report: WasteReport, new_status: str) -> str:
    """Build a friendly status-change notification for a citizen."""
    emoji = _STATUS_EMOJI.get(new_status, "\U0001F4CC")
    label = STATUS_LABELS.get(new_status, new_status.title() if new_status else "Updated")
    if new_status in STATUS_MESSAGES:
        body = STATUS_MESSAGES[new_status].format(report.ticket_id)
    else:
        body = f"{emoji} *Update \u00b7 {report.ticket_id}*: status is now {label}."
    card = [
        emoji + " *Waste Watch \u00b7 Status Update*",
        _SEP,
        body,
        "",
        _SEP,
        f"\U0001F3AB {report.ticket_id}",
    ]
    return "\n".join(card)


def format_verification_request(attempt: int) -> str:
    """Text asking a citizen for a clearer photo when the AI could not see waste."""
    header = f"\U0001F5D1\ufe0f *Waste Watch \u00b7 {'One More Photo Please' if attempt >= 2 else 'Photo Needed'}*\n{_SEP}\n"
    if attempt >= 2:
        return header + (
            "\u26A0\ufe0f We still couldn't clearly see the waste in your photo.\n\n"
            "\U0001F449 Please send one more photo:\n"
            "1. A few steps *further back* so the whole pile is in frame\n"
            "2. In better *light*\n\n"
            "If you can't get another photo, your report will be logged as a "
            "low-priority review anyway."
        )
    return header + (
        "\U0001F4F8 Thanks for reporting! We couldn't clearly make out the "
        "waste in your photo yet.\n\n"
        "\U0001F449 Please send a new photo so we can confirm it:\n"
        "1. Stand a few steps *back* so the whole pile is visible\n"
        "2. Take it during *daylight*\n"
        "3. Send it together with your \U0001F4CD *location pin*\n\n"
        "Once we can see the waste clearly, we'll create your report right away.\U0001F44D"
    )


def send_ticket_response(db: Session, report: WasteReport) -> str:
    """Send the ticket acknowledgment to the report's citizen (if one is known)."""
    phone = _citizen_phone(db, report)
    if not phone:
        return ""
    text = format_ticket_response(report)
    return _record_message(db, phone=phone, report=report, kind="ticket_response", text=text)


def notify_status_change(db: Session, report: WasteReport, new_status: str) -> Optional[str]:
    """
    Send a status-change notification to the report's citizen.

    Safe to call from the dashboard API: returns None and makes no
    changes when the report has no known citizen phone.
    """
    phone = _citizen_phone(db, report)
    if not phone:
        return None
    text = format_status_notification(report, new_status)
    return _record_message(db, phone=phone, report=report, kind="status_notification", text=text)