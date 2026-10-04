"""
WhatsApp Cloud API integration.

Handles outgoing text messages and media downloads through the Meta
WhatsApp Cloud API, and exposes a MessageChannel implementation that the
notification service can use to deliver citizen updates.
"""

import logging
from typing import Optional, Tuple

import requests

from config import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com"


def digits_of(phone: Optional[str]) -> str:
    """Extract the digits from a phone string (handles '+', spaces, etc.)."""
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def to_e164(phone: str) -> str:
    """Return a phone as E.164 digits (no '+') for the WhatsApp API."""
    return digits_of(phone)


def _headers() -> dict:
    if not settings.whatsapp_access_token:
        raise RuntimeError("WHATSAPP_ACCESS_TOKEN is not configured")
    return {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }


def send_text_message(to: str, text: str) -> bool:
    """Send a free-form WhatsApp text message to a phone number (E.164 digits)."""
    if not settings.whatsapp_phone_id:
        logger.error("WHATSAPP_PHONE_ID not configured; cannot send WhatsApp message.")
        return False

    url = f"{GRAPH_URL}/{settings.whatsapp_api_version}/{settings.whatsapp_phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    try:
        response = requests.post(url, headers=_headers(), json=payload, timeout=30)
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001 - logging and carrying on is intentional
        logger.error("Failed to send WhatsApp message to %s: %s", to, exc)
        if isinstance(exc, requests.HTTPError):
            logger.error("Response: %s", exc.response.text if exc.response is not None else "")
        return False


class WhatsAppMessageChannel:
    """MessageChannel-compatible object delivering through the Cloud API."""

    def send(self, phone: str, text: str) -> bool:
        return send_text_message(phone[:-1] if phone.startswith("+") else phone, text)


def send_image(to: str, image_bytes: bytes, mime_type: str = "image/jpeg", caption: str = "") -> bool:
    """Upload an image and deliver it as a WhatsApp image message (branding cards)."""
    if not settings.whatsapp_phone_id or not image_bytes:
        return False
    try:
        upload = requests.post(
            f"{GRAPH_URL}/{settings.whatsapp_api_version}/{settings.whatsapp_phone_id}/media",
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            files={
                "file": ("brand.jpg", image_bytes, mime_type),
                "type": (None, mime_type),
                "messaging_product": (None, "whatsapp"),
            },
            timeout=60,
        )
        upload.raise_for_status()
        media_id = upload.json().get("id")
        if not media_id:
            logger.error("WhatsApp media upload returned no media id.")
            return False

        image_payload = {"id": media_id}
        if caption:
            image_payload["caption"] = caption
        response = requests.post(
            f"{GRAPH_URL}/{settings.whatsapp_api_version}/{settings.whatsapp_phone_id}/messages",
            headers=_headers(),
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "image",
                "image": image_payload,
            },
            timeout=30,
        )
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001 - best effort branded delivery
        logger.error("Failed to send WhatsApp image to %s: %s", to, exc)
        if isinstance(exc, requests.HTTPError):
            logger.error("Response: %s", exc.response.text if exc.response is not None else "")
        return False


def send_voice_note(to: str, audio_bytes: bytes, mime_type: str = "audio/mpeg") -> bool:
    """Upload audio media and deliver it as a WhatsApp voice note."""
    if not settings.whatsapp_phone_id or not audio_bytes:
        return False
    try:
        upload = requests.post(
            f"{GRAPH_URL}/{settings.whatsapp_api_version}/{settings.whatsapp_phone_id}/media",
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            files={
                "file": ("voice.mp3", audio_bytes, mime_type),
                "type": (None, mime_type),
                "messaging_product": (None, "whatsapp"),
            },
            timeout=60,
        )
        upload.raise_for_status()
        media_id = upload.json().get("id")
        if not media_id:
            logger.error("WhatsApp media upload returned no media id.")
            return False

        response = requests.post(
            f"{GRAPH_URL}/{settings.whatsapp_api_version}/{settings.whatsapp_phone_id}/messages",
            headers=_headers(),
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "audio",
                "audio": {"id": media_id},
            },
            timeout=30,
        )
        response.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001 - best effort voice delivery
        logger.error("Failed to send WhatsApp voice note to %s: %s", to, exc)
        return False


def download_media(media_id: str) -> Tuple[Optional[bytes], str]:
    """
    Download WhatsApp media by its media id.

    Returns (file_bytes, mime_type). Returns (None, "") on failure so
    the caller can degrade gracefully.
    """
    if not settings.whatsapp_access_token:
        return None, ""
    try:
        meta = requests.get(
            f"{GRAPH_URL}/{settings.whatsapp_api_version}/{media_id}",
            headers=_headers(),
            timeout=30,
        )
        meta.raise_for_status()
        data = meta.json()
        url = data.get("url")
        mime_type = data.get("mime_type", "")
        if not url:
            return None, mime_type

        media = requests.get(url, headers=_headers(), timeout=90)
        media.raise_for_status()
        return media.content, mime_type
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to download WhatsApp media %s: %s", media_id, exc)
        return None, ""


def get_media_mime_types() -> Tuple[str, str]:
    """Return (image_mime, audio_mime) used for testing/media handling."""
    return "image/jpeg", "audio/ogg"