"""
Voice report endpoints.

Citizens can report waste by speaking. Audio recorded in the browser is
transcribed with ElevenLabs Scribe (same API key already used for voice
notes on WhatsApp) and returned as text. The transcript then flows through
the normal report pipeline, where the AI classifies the waste type,
severity and priority.
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from config import settings
from services.speech import ElevenLabsSpeechToTextProvider, get_speech_provider

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_AUDIO_BYTES = 15 * 1024 * 1024  # 15 MB


def _transcribe_with_elevenlabs(audio_bytes: bytes, mime_type: Optional[str]) -> Optional[str]:
    """Use ElevenLabs Scribe directly when the shared key is configured."""
    if not settings.elevenlabs_api_key:
        return None
    try:
        provider = ElevenLabsSpeechToTextProvider(api_key=settings.elevenlabs_api_key)
        return provider.transcribe(audio_bytes, mime_type)
    except Exception as exc:  # noqa: BLE001 - fall through to the configured provider
        logger.warning("ElevenLabs transcription failed, trying fallback: %s", exc)
        return None


@router.post("/transcribe")
async def transcribe_voice():
    """Disabled: voice reports arrive via WhatsApp voice notes only."""
    raise HTTPException(
        status_code=410,
        detail="Web voice reporting is disabled. Please send a voice note via WhatsApp instead.",
    )
