"""
Central configuration loaded from the environment.

Values come from a `.env` file in the backend directory (see .env.example)
or from the process environment. No secrets are stored in code.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MEDIA_DIR = Path(os.getenv("MEDIA_DIR", str(BASE_DIR / "media")))


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


class Settings:
    # WhatsApp / Meta Cloud API
    whatsapp_access_token: str = _env("WHATSAPP_ACCESS_TOKEN")
    whatsapp_phone_id: str = _env("WHATSAPP_PHONE_ID")
    whatsapp_verify_token: str = _env("WHATSAPP_VERIFY_TOKEN", "bamendaWebhookV1")
    whatsapp_app_secret: str = _env("WHATSAPP_APP_SECRET")
    whatsapp_api_version: str = _env("WHATSAPP_API_VERSION", "v25.0")

    # Message delivery: "log" (simulator only) or "whatsapp" (real delivery)
    message_channel: str = _env("MESSAGE_CHANNEL", "log")

    # Vision provider: "mock" or "openrouter". Falls back to NVIDIA then mock.
    vision_provider: str = _env("VISION_PROVIDER", "mock")
    openrouter_api_key: str = _env("OPENROUTER_API_KEY")
    vision_model: str = _env("VISION_MODEL", "nex-agi/nex-n2.5-pro:free")
    text_model: str = _env("TEXT_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

    # NVIDIA NIM fallback (free credits, OpenAI-compatible endpoint)
    nvidia_api_key: str = _env("NVIDIA_API_KEY")
    nvidia_vision_model: str = _env("NVIDIA_VISION_MODEL", "meta/llama-3.2-11b-vision-instruct")
    nvidia_text_model: str = _env("NVIDIA_TEXT_MODEL", "meta/llama-3.2-11b-vision-instruct")

    # Speech provider: "mock" or "groq"
    speech_provider: str = _env("SPEECH_PROVIDER", "mock")
    groq_api_key: str = _env("GROQ_API_KEY")
    speech_model: str = _env("SPEECH_MODEL", "whisper-large-v3")

    # ElevenLabs text-to-speech (voice notes)
    elevenlabs_api_key: str = _env("ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = _env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

    # Proof-of-waste verification: when a model is too unsure (low confidence
    # or "no waste clearly visible"), we ask the citizen for another photo
    # instead of creating a report. Number of extra attempts before accepting.
    verification_threshold: float = float(_env("VERIFICATION_THRESHOLD", "0.45"))
    verification_max_attempts: int = int(_env("VERIFICATION_MAX_ATTEMPTS", "1"))

    # Branded image sent to citizens (logo / info card). Path relative to
    # the backend directory, or absolute.
    brand_image_path: str = _env("BRAND_IMAGE_PATH", "../wastewatch.png")

    # How long a partially-filled submission stays alive. After this, stored
    # evidence (photo/description/location) is dropped, so a fresh conversation
    # never merges with an old one (e.g. after the citizen clears their chat).
    pending_expiry_minutes: int = int(_env("PENDING_EXPIRY_MINUTES", "60"))

    # ---- Waste marketplace (business layer) ----
    # When a sellable waste report arrives, matching vendors are alerted and a
    # listing is opened. Hazardous / medical / high-priority incidents are
    # routed to the community head via WhatsApp (when configured).
    community_head_phone: str = _env("COMMUNITY_HEAD_PHONE")

    # Money split of a vendor deal (must roughly total 100).
    reporter_commission_pct: float = float(_env("REPORTER_COMMISSION_PCT", "10"))
    collector_payout_pct: float = float(_env("COLLECTOR_PAYOUT_PCT", "55"))

    # Voice reports on the web app: prefer ElevenLabs Scribe (same key as TTS)
    # even when SPEECH_PROVIDER points elsewhere.
    voice_prefer_elevenlabs: bool = _env("VOICE_PREFER_ELEVENLABS", "true").lower() in ("1", "true", "yes")


settings = Settings()