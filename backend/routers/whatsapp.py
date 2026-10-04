"""
WhatsApp Cloud API webhook.

- GET: Meta's subscription verification handshake (echo hub.challenge).
- POST: inbound events. The endpoint acknowledges immediately and the heavy
  AI / messaging work runs on a background thread with its own DB session, so
  slow processing never blocks the event loop (which otherwise caused
  ClientDisconnect errors on Meta requests). Duplicate/retried deliveries are
  skipped via a short-lived in-memory dedupe keyed on message IDs.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from config import settings
from database import SessionLocal
from models import ProcessedMessage
from services import intake
from services.whatsapp import download_media

logger = logging.getLogger(__name__)

router = APIRouter()

_RECENT: Dict[str, float] = {}
_MAX_RECENT_AGE = 300.0


@router.get("/webhook")
def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token and token == settings.whatsapp_verify_token:
        return Response(content=challenge or "ok", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request):
    raw = await request.body()

    if settings.whatsapp_app_secret:
        signature = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(
            settings.whatsapp_app_secret.encode(), raw, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "ignored"}

    # Acknowledge instantly, then process off the event loop.
    asyncio.get_running_loop().run_in_executor(None, _process_payload_sync, payload)
    return {"status": "ok"}


def _message_ids(payload: dict) -> list:
    ids: list = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            for msg in change.get("value", {}).get("messages", []) or []:
                ids.append(msg.get("id"))
    return ids


def _dedupe(payload: dict) -> bool:
    """True if this delivery was already seen recently (skip it).

    Two layers: a fast in-memory set for retries within seconds/minutes, and a
    persistent table so deliveries survive a backend restart. Without the DB
    layer, Meta's hours-long retries would re-process an old image after a
    restart — the bot would suddenly react to a photo the citizen never sent.
    """
    ids = _message_ids(payload)
    if not ids:
        return False
    now = time.time()
    for key in [k for k, ts in _RECENT.items() if now - ts > _MAX_RECENT_AGE]:
        _RECENT.pop(key, None)
    key = "|".join(str(i) for i in ids)
    if key in _RECENT:
        logger.info("Skipping duplicate webhook delivery (memory) %s", key[:48])
        return True
    _RECENT[key] = now

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=2)
        db.query(ProcessedMessage).filter(ProcessedMessage.created_at < cutoff).delete()
        if db.query(ProcessedMessage).filter(ProcessedMessage.message_id == key).first():
            logger.info("Skipping already-processed delivery %s", key[:48])
            return True
        db.add(ProcessedMessage(message_id=key))
        db.commit()
    except Exception:  # noqa: BLE001 - dedupe must never break the webhook
        logger.warning("Dedupe persistence failed; in-memory only.", exc_info=True)
    finally:
        db.close()
    return False


def _process_payload_sync(payload: dict) -> None:
    db = SessionLocal()
    try:
        if _dedupe(payload):
            return
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                _handle_value(db, change.get("value", {}))
    except Exception:  # noqa: BLE001 - never crash the plain acknowledgement
        logger.exception("Webhook processing failed")
    finally:
        db.close()


def _phone_from_value(value: dict) -> Optional[str]:
    contacts = value.get("contacts") or []
    return contacts[0].get("wa_id") if contacts else None


def _handle_value(db, value: dict) -> None:
    phone = _phone_from_value(value)
    messages = value.get("messages") or []
    if not phone or not messages:
        return

    text = ""
    photo_bytes = None
    image_mime = "image/jpeg"
    audio_bytes = None
    audio_mime = None
    has_location = False
    lat = None
    lng = None
    address = ""

    for msg in messages:
        msg_type = msg.get("type")
        if msg_type == "text":
            text = (text + " " + (msg.get("text", {}).get("body", "") or "")).strip()
        elif msg_type == "image":
            photo_bytes, image_mime = download_media(msg["image"]["id"])
            caption = msg["image"].get("caption") or ""
            if caption:
                text = (text + " " + caption).strip()
        elif msg_type == "audio":
            audio_bytes, audio_mime = download_media(msg["audio"]["id"])
        elif msg_type == "location":
            location = msg.get("location") or {}
            try:
                lat = float(location["latitude"])
                lng = float(location["longitude"])
                has_location = True
            except (KeyError, TypeError, ValueError):
                lat = lng = None
            address = (location.get("address") or location.get("name") or "WhatsApp location").strip()
        elif msg_type == "interactive":
            # Interactive messages (e.g. location or list replies) are rare in
            # this flow; ignore but do not crash.
            continue

    # A location-only pin has no text/image/audio and MUST still be processed.
    if not (text or photo_bytes or audio_bytes or has_location):
        logger.info("WhatsApp event from %s carried nothing actionable.", phone)
        return

    reply = intake.handle_citizen_message(
        db,
        phone=phone,
        text=text,
        photo_bytes=photo_bytes,
        image_mime=image_mime,
        audio_bytes=audio_bytes,
        audio_mime=audio_mime,
        lat=lat,
        lng=lng,
        address=address,
    )
    if reply:
        logger.info("WhatsApp replied to %s: %s", phone, reply[:80])
    else:
        logger.info("WhatsApp event from %s needed no reply.", phone)


@router.get("/config")
def whatsapp_config():
    """Public (non-secret) status used by the frontend indicator."""
    return {
        "channel": intake.channel_mode(),
        "vision_provider": settings.vision_provider,
        "speech_provider": settings.speech_provider,
        "configured": bool(settings.whatsapp_phone_id and settings.whatsapp_access_token),
    }