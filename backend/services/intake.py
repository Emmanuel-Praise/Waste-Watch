"""
Shared citizen intake flow.

Builds a report from citizen inputs (photo / voice note / message /
location) using the Step 2 processing pipeline, persists any image, and
sends the ticket response. Used by both the dev simulator and the
WhatsApp webhook so the behavior is identical everywhere.
"""

import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from config import BASE_DIR, MEDIA_DIR, settings
from database import SessionLocal
from models import BrandNotified, CitizenMessage, PendingIntake, User, WasteReport
from schemas import LocationIn
from services.llm import generate_text
from services.messages import format_verification_request, send_ticket_response
from services.processing import process_report
from services.speech import get_speech_provider
from services.vision import get_vision_provider
from services.whatsapp import digits_of, send_image, send_text_message

logger = logging.getLogger(__name__)

DEFAULT_CITIZEN_PHONE = "+237670000001"

_IMAGE_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def lookup_citizen(db: Session, phone: str) -> Optional[User]:
    """Find a citizen by phone, comparing digit-only values for robustness."""
    digits = digits_of(phone)
    if not digits:
        return None
    for user in db.query(User).filter(User.phone.isnot(None)).all():
        if digits_of(user.phone) == digits:
            return user
    return None


def get_or_create_citizen(db: Session, phone: str) -> User:
    """Resolve the citizen by phone, creating a minimal user on first use."""
    existing = lookup_citizen(db, phone)
    if existing:
        return existing

    digits = digits_of(phone) or digits_of(DEFAULT_CITIZEN_PHONE)
    stored_phone = f"+{digits}" if not digits.startswith("+") else digits
    user = User(
        name=f"Citizen {stored_phone}",
        email=f"{digits}@citizen.bamenda.cm",
        role="citizen",
        phone=stored_phone,
    )
    db.add(user)
    db.flush()
    return user


def transcribe_audio(audio_bytes: bytes, mime_type: Optional[str]) -> str:
    """Transcribe a voice note. Returns '' on failure — never invents text.

    Previously this fell back to a canned mock transcript on provider errors,
    which could make the bot "hear" content the citizen never said. Empty
    transcripts are treated as "unclear" by the caller instead.
    """
    try:
        text = get_speech_provider().transcribe(audio_bytes, mime_type)
        return (text or "").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Speech provider failed: %s", exc)
        return ""


def persist_image(image_bytes: bytes, mime_type: str) -> Optional[str]:
    """Save an incoming image to the media directory; return its public URL path."""
    extension = _IMAGE_EXTENSIONS.get((mime_type or "").lower(), "jpg")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{extension}"
    path = MEDIA_DIR / filename
    path.write_bytes(image_bytes)
    return f"/media/{filename}"


def create_citizen_report(
    db: Session,
    *,
    lat: float,
    lng: float,
    address: str,
    phone: str,
    message: str = "",
    photo_bytes: Optional[bytes] = None,
    audio_bytes: Optional[bytes] = None,
    audio_mime: Optional[str] = None,
    image_mime: str = "image/jpeg",
) -> "tuple[Optional[WasteReport], str]":
    """Run the full citizen intake -> AI verification -> ticket response flow.

    Returns (report, ticket_response_text). When the AI cannot clearly
    confirm waste (low confidence, or severity 1 = "no waste visible"),
    returns (None, ask_for_photo_text) instead of creating a report, so a
    citizen must provide better evidence before a (possibly fake) report
    is logged.
    """
    citizen = get_or_create_citizen(db, phone)

    description = message or ""
    if audio_bytes:
        transcript = transcribe_audio(audio_bytes, audio_mime)
        description = (transcript + (f" {description}" if description else "")).strip()

    location = LocationIn(
        lat=lat,
        lng=lng,
        address=(address or "").strip() or f"{lat:.4f}, {lng:.4f}",
    )

    analysis = _analyze(
        image_bytes=photo_bytes,
        text=description or None,
        address=location.address,
    )

    if _is_unverifiable(analysis):
        return _request_photo_evidence(
            db,
            citizen=citizen,
            location=location,
            description=description,
            photo_bytes=photo_bytes,
            image_mime=image_mime,
            initial_analysis=analysis,
        )

    return _finalize_report(
        db,
        citizen=citizen,
        location=location,
        description=description,
        photo_bytes=photo_bytes,
        image_mime=image_mime,
        analysis=analysis,
        voice_note=bool(audio_bytes),
    )


def _analyze(
    *,
    image_bytes: Optional[bytes],
    text: Optional[str],
    address: Optional[str],
) -> "VisionAnalysis":
    """Run the vision provider with a mock fallback on total failure."""
    provider = get_vision_provider()
    try:
        return provider.analyze(image_bytes=image_bytes, text=text, address=address)
    except Exception as exc:  # noqa: BLE001 - intake must never crash
        logger.warning("Vision provider failed, using mock fallback: %s", exc)
        from services.vision import MockVisionProvider

        return MockVisionProvider().analyze(image_bytes=image_bytes, text=text, address=address)


def _is_unverifiable(analysis) -> bool:
    """True when the model could not confidently see / confirm waste."""
    if getattr(analysis, "severity_score", 0) == 1:
        return True  # system prompt maps "no clear waste" to severity 1
    confidence = getattr(analysis, "confidence", None)
    if confidence is None:
        return True
    return confidence < settings.verification_threshold


def _finalize_report(
    db: Session,
    *,
    citizen: User,
    location: LocationIn,
    description: str,
    photo_bytes: Optional[bytes],
    image_mime: str,
    analysis,
    voice_note: bool = False,
) -> "tuple[WasteReport, str]":
    """Create the report, deliver the ticket card and the branded logo."""
    _clear_pending(db, citizen.phone)

    report = process_report(
        db,
        location=location,
        description=description,
        image_bytes=photo_bytes,
        created_by=citizen.id,
        analysis=analysis,
    )

    if photo_bytes:
        image_url = persist_image(photo_bytes, image_mime)
        if image_url:
            report.image_url = image_url
            db.commit()

    # Send (or log) the ticket acknowledgment to the citizen.
    response = send_ticket_response(db, report)
    if channel_mode() == "whatsapp":
        send_branded_info(citizen.phone)

    # When the citizen used a voice note and ElevenLabs is configured, reply
    # with a spoken version of the same acknowledgment. Best-effort only.
    if voice_note and channel_mode() == "whatsapp" and response:
        from services.elevenlabs import text_to_speech, voice_note_enabled
        from services.whatsapp import send_voice_note

        if voice_note_enabled():
            mp3 = text_to_speech(response)
            if mp3:
                send_voice_note(digits_of(citizen.phone), mp3)

    db.refresh(report)
    return report, response


def _request_photo_evidence(
    db: Session,
    *,
    citizen: User,
    location: LocationIn,
    description: str,
    photo_bytes: Optional[bytes],
    image_mime: str,
    initial_analysis,
) -> "tuple[Optional[WasteReport], str]":
    """Gate: ask for a clearer photo; re-check it; accept after max attempts."""
    image_path = None
    if photo_bytes:
        image_path = persist_image(photo_bytes, image_mime)

    existing = (
        db.query(PendingIntake).filter(PendingIntake.phone == citizen.phone).first()
    )
    if existing is None:
        db.add(
            PendingIntake(
                phone=citizen.phone,
                image_path=image_path,
                description=description,
                address=location.address,
                lat=location.lat,
                lng=location.lng,
                attempt_count=1,
            )
        )
        db.commit()
        attempt = 1
    else:
        existing.attempt_count += 1
        attempt = existing.attempt_count
        if image_path:
            existing.image_path = image_path
        existing.description = description or existing.description
        existing.address = location.address
        existing.lat, existing.lng = location.lat, location.lng
        db.commit()

    # A new photo arrived: re-evaluate it before pestering the citizen again.
    if photo_bytes and attempt <= settings.verification_max_attempts + 1:
        reviewed = _analyze(
            image_bytes=photo_bytes,
            text=f"Follow-up photo of a possible waste site. Citizen note: {description or 'see photo'}".strip(),
            address=location.address,
        )
        if not _is_unverifiable(reviewed):
            return _finalize_report(
                db,
                citizen=citizen,
                location=location,
                description=description,
                photo_bytes=photo_bytes,
                image_mime=image_mime,
                analysis=reviewed,
                voice_note=False,
            )
        initial_analysis = reviewed

    if attempt > settings.verification_max_attempts:
        # Citizen could not provide better evidence; log it anyway at low
        # confidence so a real but badly-photographed dump is not lost.
        logger.info(
            "Photo evidence insufficient for %s after %s attempts; creating low-confidence report.",
            citizen.phone,
            attempt,
        )
        return _finalize_report(
            db,
            citizen=citizen,
            location=location,
            description=description,
            photo_bytes=photo_bytes,
            image_mime=image_mime,
            analysis=initial_analysis,
            voice_note=False,
        )

    text = format_verification_request(attempt)
    if channel_mode() == "whatsapp":
        send_branded_info(citizen.phone)
    reply_guidance(db, citizen.phone, text)
    return None, text


def _clear_pending(db: Session, phone: str) -> None:
    """Remove any pending verification rows for a citizen."""
    db.query(PendingIntake).filter(PendingIntake.phone == phone).delete()
    db.commit()


def get_pending(db: Session, phone: str) -> Optional["PendingIntake"]:
    """Return the pending evidence row (photo / text / location) for a citizen."""
    citizen = lookup_citizen(db, phone)
    if not citizen:
        return None
    return db.query(PendingIntake).filter(PendingIntake.phone == citizen.phone).first()


def store_evidence(
    db: Session,
    phone: str,
    *,
    photo_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
    description: str = "",
    address: str = "",
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> "PendingIntake":
    """Accumulate a citizen's partial submission so nothing sent is lost.

    Persists any new photo, merges the description, and records location when
    provided. Gate attempts are left untouched here.
    """
    citizen = get_or_create_citizen(db, phone)
    image_path = persist_image(photo_bytes, image_mime) if photo_bytes else None

    row = db.query(PendingIntake).filter(PendingIntake.phone == citizen.phone).first()
    if row is not None and row.updated_at:
        age_minutes = (datetime.utcnow() - row.updated_at).total_seconds() / 60.0
        if age_minutes > settings.pending_expiry_minutes:
            logger.info("Expiring stale pending intake for %s (%.0fm old).", phone, age_minutes)
            db.delete(row)
            db.commit()
            row = None
    if row is None:
        row = PendingIntake(
            phone=citizen.phone,
            image_path=image_path,
            description=description or "",
            address=address or "",
            lat=lat if lat is not None else 0.0,
            lng=lng if lng is not None else 0.0,
            attempt_count=0,
        )
        db.add(row)
    if image_path:
        row.image_path = image_path
    if description:
        row.description = (row.description + " " + description).strip() if row.description else description
    if address:
        row.address = address
    if lat is not None and lng is not None:
        row.lat, row.lng = lat, lng
    db.commit()
    return row


def pending_photo(row: Optional["PendingIntake"]) -> Optional[Tuple[bytes, str]]:
    """Reload the bytes + mime of a pending photo from disk, if one was stored."""
    if not row or not row.image_path:
        return None
    filename = Path(row.image_path).name
    path = MEDIA_DIR / filename
    if not path.exists():
        return None
    if path.suffix.lower() == ".png":
        mime = "image/png"
    elif path.suffix.lower() == ".webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    return path.read_bytes(), mime


_GREETING_WORDS = ("hello", "hi ", "hey", "good morning", "good afternoon", "good evening", "help", "bonjour", "salut")
_WASTE_WORDS = (
    "waste", "trash", "garbage", "rubbish", "litter", "dump", "pile", "plastic",
    "bottle", "bag", "debris", "smell", "stink", "rotten", "dirty", "bin", "cameroon", "bamenda",
)


def _looks_like_greeting(text: str) -> bool:
    return any(word in text for word in _GREETING_WORDS)


def _looks_like_waste_report(text: str) -> bool:
    return any(word in text for word in _WASTE_WORDS)


# Explicit requests for Waste Watch's other programs (marketplace, EcoCollector,
# Waste Vendor). Word-boundary matching avoids false hits inside words like
# "learn" or "network", while still catching "marketplace" and "collector".
_SERVICE_RE = re.compile(
    r"\b(?:market(?:place)?|vendor|collector|earn|sell|buy|recycl\w*|job|work|"
    r"service|offer|sign\s?up|register|what (?:can|could) you)\b",
    re.IGNORECASE,
)


def _looks_like_service_request(text: str) -> bool:
    return bool(_SERVICE_RE.search(text or ""))


_YES_START = re.compile(
    r"^(yes|yeah|yep|yup|sure|ok|okay|affirmative|correct|right|please|go ahead|why not|"
    r"i (do|want|wanna|would like)|i'd like|yeah sure|yes please|fine|alright)\b"
)
_NO_START = re.compile(
    r"^(no|nope|nah|never|nothing|none|not now|not really|no thanks|no thank you|"
    r"i don't want|i dont want|i don't need|i dont need|skip|stop|cancel|later|maybe later|bye|goodbye|"
    r"that's all|thats all|that's it|thats it|all good)\b"
)


def _looks_like_yes(text: str) -> bool:
    return bool(_YES_START.match(text.strip().lower()))


def _looks_like_no(text: str) -> bool:
    return bool(_NO_START.match(text.strip().lower()))


# Classic Whisper hallucination markers — cheap voice notes full of static,
# silence, or an intro jingle often produce exactly these phrases.
_HALLUCINATION_MARKERS = (
    "subscribe to",
    "please subscribe",
    "like and subscribe",
    "thanks for watching",
    "thank you for watching",
    "visit my website",
    "my patreon",
    "like the video",
    "this video is",
    "click the link",
    "comment below",
)


def _transcript_clear(transcript: str) -> bool:
    """A voice transcript we can actually use as a report description."""
    text = (transcript or "").strip()
    if not text:
        return False
    if len(text) > 600:
        return False
    low = text.lower()
    if any(marker in low for marker in _HALLUCINATION_MARKERS):
        return False
    # A real report needs at least a few meaningful words.
    return len(text.split()) >= 3


def _set_state(db: Session, pending: Optional["PendingIntake"], state: str) -> None:
    if pending is None:
        return
    pending.state = state
    db.commit()


def _ask_intent_message() -> str:
    return (
        "*Waste Watch* \u2013 Bamenda Municipality\U0001F44B\n\n"
        "Hello! Here's what we can help you with:\n\n"
        "\u267B\ufe0f *Report waste* \u2013 you earn *10%* when it sells\n"
        "\U0001F69B *EcoCollector* \u2013 earn *55%* per job collecting waste\n"
        "\U0001F3ED *Waste Vendor* \u2013 buy sorted material, get stock alerts\n"
        "\U0001F6D2 *Marketplace* \u2013 live listings with per-kg prices\n\n"
        "Reply *report*, *earn*, *sell* or *market* \u2013 or *no* if you don't "
        "need anything right now."
    )


def _collect_photo_message() -> str:
    return (
        "*Waste Watch*\U0001F4F8\n\n"
        "Great! Send me:\n"
        "1. A *photo* of the waste\n"
        "2. A short *description* (optional)\n\n"
        "Then attach your *location* pin and we'll create your report."
    )


def _await_location_message() -> str:
    return (
        "*Waste Watch*\U0001F4CD\n\n"
        "Almost there! Send your *location* pin (paperclip icon -> *Location*) "
        "and we'll map it and create your report."
    )


def _voice_unclear_message() -> str:
    return (
        "*Waste Watch*\U0001F3A4\n\n"
        "I received your voice note, but I couldn't understand it clearly. "
        "Please *type* your message, or send a *photo* of the waste with your "
        "location pin so I can help you report it.\U0001F64F"
    )


def _adieu_message() -> str:
    return (
        "*Waste Watch* \U0001F3C1\n\n"
        "No problem \u2013 have a great day!\n\n"
        "Remember, Waste Watch offers more than reporting:\n"
        "\U0001F69B *EcoCollector* \u2013 earn *55%* of every delivery job\n"
        "\U0001F3ED *Vendor program* \u2013 buy sorted material, get stock alerts\n"
        "\U0001F6D2 *Marketplace* \u2013 live listings with per-kg prices\n\n"
        "Just message *report*, *earn* or *sell* anytime and we'll get you started."
    )


def _ack_for_image(analysis) -> str:
    """A human line telling citizens what the AI sees in their photo."""
    if getattr(analysis, "severity_score", 0) == 1:
        return (
            "I'm reviewing your photo, but I can't clearly make out waste yet. "
            "A photo a bit closer to the pile, in daylight, will help."
        )
    waste_type = str(getattr(analysis, "waste_type", "mixed"))
    severity = getattr(analysis, "severity_score", 0)
    description = (analysis.description or "").strip()
    ack = f"I can see what looks like {waste_type.lower()} waste (severity {severity}/5)."
    if description:
        ack += f"\n\nMy quick read: {description[:160]}"
    return ack


def _welcome_message() -> str:
    return (
        "*Waste Watch - Bamenda Municipality*\n\n"
        "Welcome! This is the municipal waste reporting and recycling line.\n\n"
        "We offer:\n"
        "\u267B\ufe0f *Report waste* \u2013 photo + location, AI-verified; you earn "
        "*10%* commission when it sells\n"
        "\U0001F69B *EcoCollector* \u2013 earn *55%* of each delivery job\n"
        "\U0001F3ED *Waste Vendor* \u2013 buy sorted materials, get stock alerts\n"
        "\U0001F6D2 *Marketplace* \u2013 live listings with per-kg prices\n\n"
        "To report waste in 3 steps:\n"
        "1. Send a *photo* of the waste\n"
        "2. Add a short *description*\n"
        "3. Attach your *location* pin (paperclip icon -> Location)\n\n"
        "We verify the photo with AI, create your ticket, and keep you updated "
        "here. Say *earn* or *sell* any time for our other programs. "
        "Thank you for helping keep Bamenda clean!"
    )


def _services_overview() -> str:
    """Compact list of everything Waste Watch offers (service-request reply)."""
    return (
        "*Waste Watch \u2013 what we offer*\U0001F3AB\n\n"
        "\u267B\ufe0f *Report waste* \u2013 photo + location, AI-verified, ticket "
        "opened. You earn a *10% commission* when a vendor buys it.\n\n"
        "\U0001F69B *EcoCollector* \u2013 earn *55%* of every job: collect, sort and "
        "deliver waste.\n\n"
        "\U0001F3ED *Waste Vendor* \u2013 businesses buy sorted plastic, organic and "
        "mixed materials and get alerted whenever new stock is reported.\n\n"
        "\U0001F6D2 *Marketplace* \u2013 browse live listings with per-kg prices and "
        "reserve the quantity you need.\n\n"
        "Tell me what you'd like: reply *report*, *earn*, *sell* or *market*."
    )


_NEED_LINES = {
    "photo": "Please also send a photo of the waste.",
    "location": "Please also send your location pin (paperclip icon -> Location).",
    "description": "Please also add a short description (e.g. \"plastic pile behind the market\").",
}

_HANGING_TAILS = (" of the", " a photo of", " the", " your location", " to", " and", " please send", " send")


def _trim_hanging_tail(text: str) -> str:
    """Remove a dangling connector fragment if the model's reply got cut."""
    lowered = text.lower()
    for tail in _HANGING_TAILS:
        if lowered.endswith(tail):
            return text[: -len(tail)].rstrip()
    return text


def _ai_reply(
    *,
    citizen_text: str,
    guidance: str,
    needs: Sequence[str] = (),
    fallback: str,
) -> str:
    """Let the text model write the reply by actually reading the citizen's words.

    The model gets the citizen's message plus the practical steps the flow still
    needs, so replies stay contextual instead of canned. If the model is
    unavailable, or a required item is missing from its reply, a targeted
    request line is appended (or the template fallback is used).
    """
    context = citizen_text.strip() or "(no text was attached to this message)"
    reply = generate_text(
        context=context,
        instructions=guidance,
    )
    reply = (reply or "").strip()
    if not reply:
        return fallback
    reply = _trim_hanging_tail(reply)
    lower = reply.lower()
    for need in needs:
        if need not in lower:
            reply = reply.rstrip() + "\n\n" + _NEED_LINES.get(need, f"Please send your {need}.")
    return reply


def handle_citizen_message(
    db: Session,
    *,
    phone: str,
    text: str = "",
    photo_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
    audio_bytes: Optional[bytes] = None,
    audio_mime: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    address: str = "",
) -> Optional[str]:
    """Route any inbound citizen message into the right next step.

    Looks at whatever was sent (image, text/voice transcript, location),
    reuses previously stored evidence, and replies appropriately:
    - Reports must have both a photo/description AND a location; the missing
      bit is requested. Photos are analyzed by the AI if a location is still
      missing. Returns the reply text (already sent), or None if nothing to send.
    """
    citizen = get_or_create_citizen(db, phone)
    digits = digits_of(citizen.phone)

    description = text or ""
    voice_unclear = False
    if audio_bytes:
        # The mock provider is a dev placeholder that returns canned sample
        # transcripts — never treat its content as the citizen's actual words,
        # otherwise the bot "invents" reports (e.g. "hospital waste").
        if (settings.speech_provider or "mock").lower() == "mock":
            logger.warning("Speech provider is 'mock'; ignoring audio content.")
            transcript = ""
        else:
            transcript = transcribe_audio(audio_bytes, audio_mime)
        if _transcript_clear(transcript):
            description = (transcript + (f" {description}" if description else "")).strip()
        elif not (text or photo_bytes):
            voice_unclear = True

    if voice_unclear:
        reply = _voice_unclear_message()
        if channel_mode() == "whatsapp":
            send_branded_info(digits)
        reply_guidance(db, citizen.phone, reply)
        return reply

    store_evidence(
        db,
        citizen.phone,
        photo_bytes=photo_bytes,
        image_mime=image_mime,
        description=description,
        address=address,
        lat=lat,
        lng=lng,
    )
    pending = get_pending(db, citizen.phone)
    combined = ((pending.description if pending else "") + " " + description).strip()
    state = (pending.state if pending else None) or "idle"

    stored = pending_photo(pending) if pending else None
    current_photo = photo_bytes
    photo = photo_bytes or (stored[0] if stored else None)
    mime = image_mime if photo_bytes is not None else (stored[1] if stored else image_mime)

    has_location = lat is not None and lng is not None
    if has_location:
        loc_lat, loc_lng, loc_address = lat, lng, address
    elif pending and pending.lat and pending.lng:
        loc_lat, loc_lng, loc_address = pending.lat, pending.lng, pending.address or ""
    else:
        loc_lat = loc_lng = None
        loc_address = ""

    # ---- We have a location: try to create (and verify) the report. ----
    if loc_lat is not None and loc_lng is not None:
        if description and _looks_like_greeting(description.lower()):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "FACT: the citizen sent only the greeting above; their "
                    "location is saved but they have NOT sent a photo yet. Do "
                    "not claim you can see any waste.\n\n"
                    "Greet them warmly, confirm their location is saved, and ask "
                    "them to send a photo and a short description of the waste so "
                    "you can create their report."
                ),
                needs=("photo", "description"),
                fallback=(
                    _welcome_message()
                    + "\n\nYour location is saved. Send a photo and a short "
                    "description of the waste when you're ready and we'll create "
                    "your report."
                ),
            )
            _set_state(db, pending, "collecting")
            if channel_mode() == "whatsapp":
                send_branded_info(digits)
            reply_guidance(db, citizen.phone, reply)
            return reply

        if photo or description:
            _notify_waiting(
                citizen.phone,
                "*Waste Watch* — reviewing your report now, one moment please…",
            )
            report, response = create_citizen_report(
                db,
                lat=loc_lat,
                lng=loc_lng,
                address=loc_address,
                phone=citizen.phone,
                message=combined,
                photo_bytes=photo,
                audio_bytes=None,
                audio_mime=None,
                image_mime=mime,
            )
            return response

        # Only a location arrived: request photo + description.
        reply = _ai_reply(
            citizen_text="(sent only a location pin, no photo or description)",
            guidance=(
                "The citizen sent their location but no photo or description yet. "
                "Thank them and confirm you saved the location, then ask them to "
                "send a photo of the waste and a short description so you can "
                "create the report."
            ),
            needs=("photo",),
            fallback=(
                "*Waste Watch - Bamenda Municipality*\n\n"
                "We received your location. To create the report we still need to "
                "see the waste.\n\n"
                "Please send:\n"
                "1. A *photo* of the waste\n"
                "2. And/or a short description (e.g. \"plastic pile behind the market\")\n\n"
                "We'll attach them to this location automatically."
            ),
        )
        _set_state(db, pending, "collecting")
        if channel_mode() == "whatsapp":
            send_branded_info(digits)
        reply_guidance(db, citizen.phone, reply)
        return reply

    # ---- No location yet: guided conversation state machine. ----
    #
    # idle  -> greeting        -> greet + ask "report waste?" (asking_intent)
    #       -> "yes"/waste text -> ask for photo (collecting)
    #       -> "no"            -> friendly close
    # asking_intent -> "yes"   -> ask for photo (collecting)
    #               -> "no"    -> friendly close
    #               -> other   -> re-ask the question
    # collecting    -> photo   -> (handled above) ask location
    #               -> description -> ask photo + location (stay)
    # awaiting_location -> whatever -> ask for the location pin (stay)
    if current_photo:
        _notify_waiting(
            citizen.phone,
            "*Waste Watch* — got your photo, checking it now, one moment…",
        )
        analysis = _analyze(image_bytes=current_photo, text=combined or None, address=None)
        ack = _ack_for_image(analysis)
        reply = _ai_reply(
            citizen_text=(combined or "sent a photo of waste") + f"\n\n[AI sight note: {ack}]",
            guidance=(
                "The citizen sent a photo. Using the AI sight note above, thank "
                "them in your own words and briefly mention what appears to be in "
                "the photo, then ask them to send their location pin so you can "
                "map it and create the report."
            ),
            needs=("location",),
            fallback=(
                "*Waste Watch \u2013 Bamenda Municipality*\n\n"
                f"{ack}\n\n"
                "To map this, now send your *location* pin (paperclip icon -> "
                "*Location*). We'll combine it with this photo automatically."
            ),
        )
        if channel_mode() == "whatsapp":
            send_branded_info(digits)
        reply_guidance(db, citizen.phone, reply)
        _set_state(db, pending, "awaiting_location")
        return reply

    if not description:
        return None

    if state == "asking_intent":
        if _looks_like_yes(description):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "The citizen wants to report waste. Tell them to send a photo "
                    "of the waste (best evidence) plus a short description, then "
                    "their location pin."
                ),
                needs=("photo", "location"),
                fallback=_collect_photo_message(),
            )
            _set_state(db, pending, "collecting")
        elif _looks_like_no(description):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "The citizen does not want to report waste right now. Be "
                    "friendly, thank them, and remind them Waste Watch can still "
                    "help them earn money as an EcoCollector (55% of each job) or "
                    "sell sorted materials as a Waste Vendor - they can reply "
                    "'earn' or 'sell' anytime."
                ),
                fallback=_adieu_message(),
            )
            _clear_pending(db, citizen.phone)
        elif _looks_like_service_request(description):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "The citizen is interested in one of Waste Watch's other "
                    "services (EcoCollector earning program, Waste Vendor program "
                    "or the marketplace), not a new report. Briefly introduce "
                    "those services - reporting gives a 10% commission, "
                    "EcoCollectors earn 55% per job, Vendors buy sorted material "
                    "with new-stock alerts, and the marketplace has live per-kg "
                    "prices - then ask which one they'd like to start with."
                ),
                fallback=_services_overview(),
            )
            _set_state(db, pending, "idle")
        else:
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "You just asked what the citizen would like to do and did not "
                    "understand their answer. Gently re-list the options: report "
                    "waste, earn as an EcoCollector, sell as a Vendor, or browse "
                    "the marketplace."
                ),
                fallback=_ask_intent_message(),
            )
            _set_state(db, pending, "asking_intent")
    elif state == "collecting":
        if _looks_like_no(description):
            reply = _ai_reply(
                citizen_text=description,
                guidance="The citizen is backing out of the report. Let them go kindly; say they can resume anytime with a photo.",
                fallback=_adieu_message(),
            )
            _clear_pending(db, citizen.phone)
        elif _looks_like_greeting(description.lower()):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "FACT: the citizen sent only a greeting; no photo yet. "
                    "Acknowledge briefly and remind them we are still waiting for "
                    "the photo of the waste and their location pin."
                ),
                needs=("photo", "location"),
                fallback=_collect_photo_message(),
            )
        else:
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "FACT: the citizen described waste but has NOT sent a photo or "
                    "location yet. Acknowledge their words, then ask for the photo "
                    "of the waste and their location pin."
                ),
                needs=("photo", "location"),
                fallback=_collect_photo_message(),
            )
            _set_state(db, pending, "collecting")
    elif state == "awaiting_location":
        if _looks_like_no(description):
            reply = _ai_reply(
                citizen_text=description,
                guidance="The citizen is backing out of the report. Let them go kindly.",
                fallback=_adieu_message(),
            )
            _clear_pending(db, citizen.phone)
        else:
            reply = _ai_reply(
                citizen_text=description or "sent nothing new",
                guidance=(
                    "FACT: the citizen's photo is saved but they have NOT sent a "
                    "location pin yet. Remind them to attach their location pin so "
                    "the report can be created. Do not describe any waste beyond "
                    "what the photo showed."
                ),
                needs=("location",),
                fallback=_await_location_message(),
            )
    else:  # idle / fresh conversation
        if _looks_like_greeting(description.lower()):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "FACT: the citizen sent only this greeting text - no photo, no "
                    "location. Greet them warmly and briefly introduce what Waste "
                    "Watch offers: report waste (10% commission when it sells), "
                    "the EcoCollector earning program (55% per job), the Waste "
                    "Vendor program (buy sorted material, get new-stock alerts) "
                    "and the marketplace. Then ask what they would like to do."
                ),
                fallback=_ask_intent_message(),
            )
            _set_state(db, pending, "asking_intent")
        elif _looks_like_no(description):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "The citizen does not want to report waste. Wish them a good "
                    "day, and mention that Waste Watch also lets them earn as an "
                    "EcoCollector (55% per job) or sell sorted materials as a "
                    "Vendor if that ever interests them."
                ),
                fallback=_adieu_message(),
            )
            _clear_pending(db, citizen.phone)
        elif _looks_like_service_request(description):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "The citizen is asking about Waste Watch's services - likely "
                    "the EcoCollector earning program, the Waste Vendor program, "
                    "the marketplace, or reporting waste. Introduce all four "
                    "clearly and briefly: report waste (10% commission), "
                    "EcoCollector (55% per job), Vendor (buy sorted material with "
                    "new-stock alerts), Marketplace (live listings with per-kg "
                    "prices). Then ask which one they would like to start with."
                ),
                fallback=_services_overview(),
            )
        elif _looks_like_yes(description) or _looks_like_waste_report(description.lower()):
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "The citizen wants to report waste. Ask them to send a photo "
                    "of the waste (best evidence) plus a short description, then "
                    "their location pin."
                ),
                needs=("photo", "location"),
                fallback=_collect_photo_message(),
            )
            _set_state(db, pending, "collecting")
        else:
            reply = _ai_reply(
                citizen_text=description,
                guidance=(
                    "FACT: the citizen sent only this text - no photo, no "
                    "location. Reply naturally. This line handles Waste Watch for "
                    "Bamenda Municipality. Tell them what we offer: report waste "
                    "(10% commission), EcoCollector earnings (55% per job), the "
                    "Vendor program, and the marketplace. If their message is "
                    "about waste, guide them to send a photo and location. If it "
                    "is not about waste, introduce the services and ask which "
                    "they would like."
                ),
                fallback=_ask_intent_message(),
            )
            _set_state(db, pending, "asking_intent")

    if channel_mode() == "whatsapp":
        send_branded_info(digits)
    reply_guidance(db, citizen.phone, reply)
    return reply


def load_brand_image(max_size: int = 800) -> Optional[Tuple[bytes, str]]:
    """Load the Waste Watch branding image (downscaled for WhatsApp)."""
    path = Path(settings.brand_image_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists():
        return None
    raw = path.read_bytes()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(raw))
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size))
        out = io.BytesIO()
        img.save(out, format="PNG" if mime == "image/png" else "JPEG")
        return out.getvalue(), mime
    except Exception as exc:  # noqa: BLE001 - send the original if we cannot shrink it
        logger.warning("Could not downscale brand image: %s", exc)
        return raw, mime


def send_branded_info(phone: str) -> bool:
    """Send the Waste Watch logo card to a citizen, but only ONCE per person.

    Repeated replies keep the chat clean instead of re-attaching the logo
    image every time. Best-effort, WhatsApp only.
    """
    if channel_mode() != "whatsapp":
        return False
    digits = digits_of(phone)
    if not digits:
        return False

    db = SessionLocal()
    try:
        if db.query(BrandNotified).filter_by(phone=digits).first():
            logger.debug("Brand card already sent to %s; skipping.", digits)
            return False

        loaded = load_brand_image()
        if not loaded:
            logger.info("Brand image not found (%s); skipping logo card.", settings.brand_image_path)
            return False
        image_bytes, mime = loaded
        caption = "Waste Watch - Bamenda Municipality"
        ok = send_image(digits, image_bytes, mime, caption=caption)
        if ok:
            db.add(BrandNotified(phone=digits))
            db.commit()
            logger.info("Brand card sent to %s.", digits)
        return ok
    except Exception as exc:  # noqa: BLE001 - never fail the whole reply for branding
        logger.warning("Could not send brand card to %s: %s", digits, exc)
        return False
    finally:
        db.close()


def channel_mode() -> str:
    """Return the configured message delivery mode."""
    return (settings.message_channel or "log").lower()


def reply_guidance(db: Session, phone: str, text: str) -> None:
    """Send a guidance/help reply to a citizen (logged; WhatsApp when enabled)."""
    stored_phone = get_or_create_citizen(db, phone).phone
    db.add(
        CitizenMessage(
            id=str(uuid.uuid4()),
            phone=stored_phone,
            kind="generic",
            text=text,
            created_at=datetime.utcnow(),
        )
    )
    db.commit()
    if channel_mode() == "whatsapp":
        send_text_message(digits_of(phone), text)


def send_whatsapp(phone: str, text: str) -> bool:
    """Best-effort WhatsApp delivery; also used by webhook guidance replies."""
    return send_text_message(phone, text)


def _notify_waiting(phone: str, text: str) -> None:
    """Send an instant progress note before heavy AI work (WhatsApp only)."""
    if channel_mode() != "whatsapp":
        return
    try:
        send_text_message(digits_of(phone), text)
    except Exception as exc:  # noqa: BLE001 - ack is best-effort
        logger.warning("Could not send progress note to %s: %s", phone, exc)