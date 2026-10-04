"""
ElevenLabs text-to-speech.

Generates an MP3 voice note from text so the WhatsApp channel can reply
to citizens with a spoken update. Provides graceful no-key handling so
the rest of the pipeline never breaks when it is not configured.
"""

import logging
from typing import Optional

import requests

from config import settings

logger = logging.getLogger(__name__)

ELEVENLABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


def text_to_speech(text: str) -> Optional[bytes]:
    """Synthesize text to MP3 bytes using ElevenLabs, or None on failure."""
    if not settings.elevenlabs_api_key:
        logger.info("ELEVENLABS_API_KEY not configured; skipping TTS.")
        return None
    if not text.strip():
        return None

    url = f"{ELEVENLABS_URL}/{settings.elevenlabs_voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text.strip(),
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.content
    except Exception as exc:  # noqa: BLE001 - voice notes are best-effort
        logger.error("ElevenLabs TTS failed: %s", exc)
        if isinstance(exc, requests.HTTPError):
            logger.error("Response: %s", exc.response.text if exc.response is not None else "")
        return None


def voice_note_enabled() -> bool:
    """True when the API key is configured so voice replies are possible."""
    return bool(settings.elevenlabs_api_key)