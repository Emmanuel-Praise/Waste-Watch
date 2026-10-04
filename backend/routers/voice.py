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
async def transcribe_voice(
    file: UploadFile = File(...),
    language: str = Form(""),
):
    """Transcribe a recorded voice message and return the text."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio file too large (max 15 MB)")

    mime_type = file.content_type or "audio/webm"
    transcript: Optional[str] = None
    provider_used = "elevenlabs"

    # Voice reports prefer ElevenLabs (per product decision) when the key is set.
    if settings.voice_prefer_elevenlabs:
        transcript = _transcribe_with_elevenlabs(audio_bytes, mime_type)

    if not transcript:
        try:
            provider = get_speech_provider()
            transcript = provider.transcribe(audio_bytes, mime_type)
            provider_used = type(provider).__name__.replace("SpeechToTextProvider", "").lower()
        except Exception as exc:  # noqa: BLE001
            logger.error("Voice transcription failed entirely: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Voice transcription is temporarily unavailable. Please type "
                    "your report instead - it works exactly the same."
                ),
            )

    transcript = (transcript or "").strip()
    if not transcript:
        raise HTTPException(
            status_code=422,
            detail="We couldn't hear anything in that recording. Please try again a bit closer to the microphone.",
        )

    return {
        "transcript": transcript,
        "provider": provider_used,
        "language": language or None,
    }
