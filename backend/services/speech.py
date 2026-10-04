"""
Speech-to-text service.

Provides a pluggable SpeechToTextProvider interface so a real speech API
can be connected later without touching the rest of the application. The
default implementation is a deterministic mock that needs no credentials,
letting the full audio -> text -> report path be tested today.
"""

import hashlib
import logging
import re
from abc import ABC, abstractmethod
from typing import List, Optional

import requests

from config import settings

logger = logging.getLogger(__name__)

# Audio-event tags ElevenLabs Scribe can splice in, e.g. "[pause]" "[music]".
_TAG_RE = re.compile(r"\[(?:[a-z_ ]+)\]")

SAMPLE_TRANSCRIPTS: List[str] = [
    "There is a pile of plastic bottles blocking the drain near the market.",
    "Medical waste and syringes are dumped behind the clinic, please come quickly.",
    "Food waste is attracting rats behind the stalls at the market.",
    "Chemical containers were dumped close to the water point.",
]


class SpeechToTextProvider(ABC):
    """Interface any speech-to-text provider must implement."""

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: Optional[str] = None,
    ) -> str:
        """Return the text transcript of an audio message."""
        raise NotImplementedError


class MockSpeechToTextProvider(SpeechToTextProvider):
    """
    Deterministic mock used until a production speech API is wired in.

    Same audio bytes produce the same transcript so the path is
    reproducible in test and in the simulator.
    """

    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: Optional[str] = None,
    ) -> str:
        digest = hashlib.sha256(audio_bytes[:8192]).digest()
        index = int.from_bytes(digest[:4], "big") % len(SAMPLE_TRANSCRIPTS)
        return SAMPLE_TRANSCRIPTS[index]


class GroqSpeechToTextProvider(SpeechToTextProvider):
    """Speech-to-text through Whisper served by Groq's API."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: Optional[str] = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        extension = "ogg"
        if mime_type:
            mapping = {
                "audio/mpeg": "mp3",
                "audio/mp3": "mp3",
                "audio/wav": "wav",
                "audio/x-wav": "wav",
                "audio/ogg": "ogg",
                "audio/mp4": "m4a",
            }
            extension = mapping.get(mime_type.lower(), "ogg")

        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": (f"voice.{extension}", audio_bytes, mime_type or "audio/ogg")},
            data={"model": self.model},
            timeout=90,
        )
        response.raise_for_status()
        text = (response.json().get("text") or "").strip()
        if not text:
            raise RuntimeError("Groq transcription returned empty text")
        return text


class ElevenLabsSpeechToTextProvider(SpeechToTextProvider):
    """Speech-to-text through ElevenLabs' Scribe API (uses the same key the
    project already has for TTS). No extra credentials needed."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: Optional[str] = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not configured")

        extension = "ogg"
        if mime_type:
            base_mime = mime_type.split(";", 1)[0].strip().lower()
            mapping = {
                "audio/mpeg": "mp3",
                "audio/mp3": "mp3",
                "audio/wav": "wav",
                "audio/x-wav": "wav",
                "audio/ogg": "ogg",
                "audio/opus": "ogg",
                "audio/webm": "webm",
                "audio/mp4": "m4a",
                "audio/aac": "aac",
            }
            extension = mapping.get(base_mime, "ogg")

        response = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": self.api_key},
            files={"file": (f"voice.{extension}", audio_bytes, mime_type or "audio/ogg")},
            data={"model_id": "scribe_v1"},
            timeout=90,
        )
        response.raise_for_status()
        text = (response.json().get("text") or "").strip()
        if not text:
            raise RuntimeError("ElevenLabs transcription returned empty text")
        text = re.sub(r"\s+", " ", _TAG_RE.sub(" ", text)).strip()
        if not text:
            raise RuntimeError("ElevenLabs transcription returned only audio events")
        return text


def get_speech_provider() -> SpeechToTextProvider:
    """Return the configured provider. Defaults to the mock."""
    provider_name = (settings.speech_provider or "mock").lower()
    if provider_name == "mock":
        return MockSpeechToTextProvider()
    if provider_name == "groq":
        return GroqSpeechToTextProvider(
            api_key=settings.groq_api_key,
            model=settings.speech_model,
        )
    if provider_name == "elevenlabs":
        return ElevenLabsSpeechToTextProvider(api_key=settings.elevenlabs_api_key)
    raise ValueError("Unknown SPEECH_PROVIDER '%s'. Use 'mock', 'groq' or 'elevenlabs'." % provider_name)