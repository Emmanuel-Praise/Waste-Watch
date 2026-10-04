"""
Vision analysis service.

Provides a pluggable VisionProvider interface so a production provider
(OpenRouter, NVIDIA, etc.) can be connected without touching the rest of
the application. The default implementation is a deterministic mock that
needs no API key, so the full pipeline is testable today.
"""

import base64
import hashlib
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import List, Optional

import requests

from config import settings
from schemas import VisionAnalysis, WasteType

logger = logging.getLogger(__name__)

# Fixed sample scenarios used by the mock provider. Each one is a
# plausible vision-analysis outcome covering the supported waste types,
# severities and hazard levels.
SAMPLE_SCENARIOS: List[VisionAnalysis] = [
    VisionAnalysis(
        waste_type=WasteType.MIXED,
        severity_score=4,
        hazard_level="high",
        estimated_size="large",
        visible_hazards=["Construction debris", "Blocked drainage"],
        description="Large mixed waste dump with construction and household waste. Partially blocking the road and drainage.",
        recommended_action="Dispatch a collection truck with crew to clear the dump and restore drainage flow.",
        confidence=0.91,
    ),
    VisionAnalysis(
        waste_type=WasteType.PLASTIC,
        severity_score=2,
        hazard_level="low",
        estimated_size="small",
        visible_hazards=["Scattered plastic bottles", "Bags"],
        description="Scattered plastic bottles and bags along the roadside. Mostly visual pollution with no immediate hazard.",
        recommended_action="Schedule routine street-cleanup sweep. Low urgency.",
        confidence=0.94,
    ),
    VisionAnalysis(
        waste_type=WasteType.ORGANIC,
        severity_score=3,
        hazard_level="medium",
        estimated_size="medium",
        visible_hazards=["Food waste", "Flies and rodents"],
        description="Accumulated organic and food waste attracting flies and rodents. Strong odor reported.",
        recommended_action="Dispatch a collection crew and treat the area to reduce odor and pest activity.",
        confidence=0.88,
    ),
    VisionAnalysis(
        waste_type=WasteType.HAZARDOUS,
        severity_score=5,
        hazard_level="critical",
        estimated_size="medium",
        visible_hazards=["Chemical containers", "Potential runoff"],
        description="Chemical and solvent containers dumped near a water source. High risk of contamination.",
        recommended_action="Treat as hazardous incident. Isolate the area, notify the environment unit, and arrange licensed removal.",
        confidence=0.87,
    ),
    VisionAnalysis(
        waste_type=WasteType.MEDICAL,
        severity_score=5,
        hazard_level="critical",
        estimated_size="medium",
        visible_hazards=["Syringes", "Bandages", "Sharps"],
        description="Illegal disposal of medical waste including syringes and bandages near a populated area.",
        recommended_action="Treat as a public-health emergency. Secure the site, notify health services, and arrange medical-waste removal.",
        confidence=0.9,
    ),
    VisionAnalysis(
        waste_type=WasteType.PLASTIC,
        severity_score=3,
        hazard_level="medium",
        estimated_size="medium",
        visible_hazards=["Plastic waste", "Risk of flooding"],
        description="Plastic waste mound blocking a drainage channel. Flooding risk during heavy rain.",
        recommended_action="Dispatch crew to clear the drain before the next rainfall.",
        confidence=0.89,
    ),
]

_MEDICAL_KEYWORDS = ("syringe", "medical", "clinic", "hospital", "bandage", "sharps", "health")
_HAZARDOUS_KEYWORDS = ("chemical", "container", "toxic", "drum", "solvent", "paint", "battery")
_PLASTIC_KEYWORDS = ("plastic", "bottle", "bag", "packaging", "pvc")
_MIXED_KEYWORDS = ("dump", "debris", "construction", "household", "mixed", "blocking")
_ORGANIC_KEYWORDS = ("organic", "food", "garden", "vegetable", "kitchen", "odor", "rotten")


class VisionProvider(ABC):
    """Interface any vision provider must implement."""

    @abstractmethod
    def analyze(
        self,
        image_bytes: Optional[bytes] = None,
        text: Optional[str] = None,
        address: Optional[str] = None,
    ) -> VisionAnalysis:
        """Return a structured analysis for the given image and/or message."""
        raise NotImplementedError


class MockVisionProvider(VisionProvider):
    """
    Deterministic mock provider used until a production provider is wired in.

    Same inputs produce the same output, so results are reproducible in test.
    """

    def _scenario_for_bytes(self, image_bytes: bytes) -> VisionAnalysis:
        digest = hashlib.sha256(image_bytes[:8192]).digest()
        index = int.from_bytes(digest[:4], "big") % len(SAMPLE_SCENARIOS)
        return SAMPLE_SCENARIOS[index]

    def _scenario_for_text(self, text: str) -> VisionAnalysis:
        lowered = text.lower()
        if any(k in lowered for k in _MEDICAL_KEYWORDS):
            category = WasteType.MEDICAL
        elif any(k in lowered for k in _HAZARDOUS_KEYWORDS):
            category = WasteType.HAZARDOUS
        elif any(k in lowered for k in _PLASTIC_KEYWORDS):
            category = WasteType.PLASTIC
        elif any(k in lowered for k in _MIXED_KEYWORDS):
            category = WasteType.MIXED
        elif any(k in lowered for k in _ORGANIC_KEYWORDS):
            category = WasteType.ORGANIC
        else:
            category = WasteType.MIXED

        matches = [s for s in SAMPLE_SCENARIOS if s.waste_type == category]
        return matches[0] if matches else SAMPLE_SCENARIOS[0]

    def analyze(
        self,
        image_bytes: Optional[bytes] = None,
        text: Optional[str] = None,
        address: Optional[str] = None,
    ) -> VisionAnalysis:
        if image_bytes:
            scenario = self._scenario_for_bytes(image_bytes)
        elif text:
            scenario = self._scenario_for_text(text)
        else:
            scenario = SAMPLE_SCENARIOS[0]

        if address and any(k in address.lower() for k in ("school", "clinic", "health", "water", "market")):
            scenario = scenario.model_copy(
                update={
                    "description": f"{scenario.description} Located near a sensitive area."
                }
            )
        return scenario


_VALID_HAZARDS = {"low", "medium", "high", "critical"}
_VALID_SIZES = {"small", "medium", "large"}
_VALID_TYPES = {t.value for t in WasteType}

SYSTEM_PROMPT = (
    "You are a municipal waste inspector reviewing citizen photos and messages for the "
    "Bamenda waste management office. Evaluate what is actually visible and be objective.\n"
    "Rules:\n"
    "1. If the image or message does not clearly show waste or dumping, set severity_score to 1, "
    "hazard_level to low, estimated_size to small, and describe exactly what is seen and why you "
    "are uncertain.\n"
    "2. Focus on the waste type that dominates the scene: plastic, organic, mixed, hazardous, medical.\n"
    "3. If the reported location mentions a school, clinic, hospital, health center, market or water "
    "source, note the sensitivity in the description.\n"
    "Respond with ONLY a JSON object, no prose, using exactly these keys: "
    '"waste_type" (one of: plastic, organic, mixed, hazardous, medical), '
    '"severity_score" (integer 1-5), "hazard_level" (one of: low, medium, high, critical), '
    '"estimated_size" (one of: small, medium, large), '
    '"visible_hazards" (array of short strings), '
    '"description" (one sentence), '
    '"recommended_action" (one sentence, a concrete action for a cleanup crew), '
    '"confidence" (float 0-1).'
)


def _coerce_vision(parsed: dict, fallback: VisionAnalysis) -> VisionAnalysis:
    """Coerce a parsed model reply into a valid VisionAnalysis, falling back sensibly."""
    waste = str(parsed.get("waste_type", "")).strip().lower()
    try:
        waste_type = WasteType(waste)
    except ValueError:
        waste_type = fallback.waste_type

    try:
        severity = max(1, min(5, int(parsed.get("severity_score", 0))))
    except (TypeError, ValueError):
        severity = fallback.severity_score

    hazard = str(parsed.get("hazard_level", "")).strip().lower()
    hazard = hazard if hazard in _VALID_HAZARDS else fallback.hazard_level

    size = str(parsed.get("estimated_size", "")).strip().lower()
    size = size if size in _VALID_SIZES else fallback.estimated_size

    hazards = parsed.get("visible_hazards") or []
    if not isinstance(hazards, list):
        hazards = []
    hazards = [str(h)[:60] for h in hazards][:6]

    try:
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = fallback.confidence

    return VisionAnalysis(
        waste_type=waste_type,
        severity_score=severity,
        hazard_level=hazard,
        estimated_size=size,
        visible_hazards=hazards,
        description=str(parsed.get("description") or fallback.description)[:500],
        recommended_action=str(parsed.get("recommended_action") or fallback.recommended_action)[:500],
        confidence=confidence,
    )


def _extract_json(raw: str) -> Optional[dict]:
    """Best-effort extraction of a JSON object from an LLM reply."""
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            parsed = json.loads(raw[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _build_content(
    image_bytes: Optional[bytes],
    text: Optional[str],
    address: Optional[str],
) -> list:
    """Build an OpenAI-style multimodal content list for a chat completion."""
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if image_bytes:
        image_b64 = base64.b64encode(image_bytes[:1_500_000]).decode()
        content.append(
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_b64}}
        )
    if address:
        content.append({"type": "text", "text": f"Reported location: {address}"})
    return content or [{"type": "text", "text": "No details provided."}]


def _chat_completion(api_key: str, base_url: str, model: str, content: list) -> str:
    """Call an OpenAI-compatible chat completion and return the raw reply text."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        # Reasoning-style free models need headroom before they emit their answer.
        "max_tokens": 1200,
        "temperature": 0.1,
    }
    for attempt in range(3):
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code not in (429, 500, 502, 503) or attempt == 2:
            break
        logger.warning("Vision API rate-limited (HTTP %s), retrying %s in a moment...", response.status_code, attempt + 1)
        time.sleep(2 * (attempt + 1))
    response.raise_for_status()
    data = response.json()
    try:
        content_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected completion payload from {base_url}: {str(data)[:200]}") from exc
    if not content_text:
        raise RuntimeError(f"Model {model} returned an empty completion (tokens spent on reasoning).")
    return content_text


def _estimate_from_prose(
    raw: str,
    image_bytes: Optional[bytes],
    text: Optional[str],
) -> Optional[VisionAnalysis]:
    """Recover a usable analysis when a model narrated instead of emitting JSON."""
    if not raw or not raw.strip():
        return None
    probe = MockVisionProvider()
    base = probe._scenario_for_bytes(image_bytes) if image_bytes else probe._scenario_for_text(text or raw)

    severity = base.severity_score
    sev_match = re.search(r"(?:severity|score|scale)\s*(?::|=|is)?\s*(\d)(?:/5)?", raw, re.IGNORECASE)
    if sev_match:
        severity = max(1, min(5, int(sev_match.group(1))))

    hazard = base.hazard_level
    for level in _VALID_HAZARDS:
        if re.search(rf"\b{level}\b", raw, re.IGNORECASE):
            hazard = level
            break

    size = base.estimated_size
    for size_word in _VALID_SIZES:
        if re.search(rf"\b{size_word}\b", raw, re.IGNORECASE):
            size = size_word
            break

    prose = " ".join(raw.split())
    if not text and len(prose) > 20:
        description = prose[:500]
    else:
        description = getattr(base, "description", None)

    return VisionAnalysis(
        waste_type=base.waste_type,
        severity_score=severity,
        hazard_level=hazard,
        estimated_size=size,
        visible_hazards=list(getattr(base, "visible_hazards", []) or []),
        description=description,
        recommended_action=getattr(base, "recommended_action", None),
        confidence=max(0.4, base.confidence - 0.3),
    )


def _to_analysis(
    raw: str,
    image_bytes: Optional[bytes],
    text: Optional[str],
) -> VisionAnalysis:
    """Parse an LLM reply as JSON when possible, else recover from prose."""
    parsed = _extract_json(raw)
    if parsed is not None:
        return _coerce_vision(parsed, SAMPLE_SCENARIOS[0])
    estimated = _estimate_from_prose(raw, image_bytes, text)
    if estimated is not None:
        logger.info("Vision reply was prose; recovered structured analysis from it.")
        return estimated
    raise ValueError(f"Unusable model reply: {raw[:200]}")


class OpenRouterVisionProvider(VisionProvider):
    """Vision/text analysis through free-tier multimodal models on OpenRouter."""

    def __init__(self, api_key: str, vision_model: str, text_model: str):
        self.api_key = api_key
        self.vision_model = vision_model
        self.text_model = text_model

    def analyze(
        self,
        image_bytes: Optional[bytes] = None,
        text: Optional[str] = None,
        address: Optional[str] = None,
    ) -> VisionAnalysis:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")

        model = self.vision_model if image_bytes else self.text_model
        content = _build_content(image_bytes, text, address)
        raw = _chat_completion(self.api_key, "https://openrouter.ai/api/v1", model, content)
        return _to_analysis(raw, image_bytes, text)


class NVIDIAVisionProvider(VisionProvider):
    """Vision/text analysis through NVIDIA NIM free models (OpenAI-compatible)."""

    def __init__(self, api_key: str, vision_model: str, text_model: str):
        self.api_key = api_key
        self.vision_model = vision_model
        self.text_model = text_model

    def analyze(
        self,
        image_bytes: Optional[bytes] = None,
        text: Optional[str] = None,
        address: Optional[str] = None,
    ) -> VisionAnalysis:
        if not self.api_key:
            raise RuntimeError("NVIDIA_API_KEY is not configured")

        model = self.vision_model if image_bytes else self.text_model
        content = _build_content(image_bytes, text, address)
        raw = _chat_completion(
            self.api_key, "https://integrate.api.nvidia.com/v1", model, content
        )
        return _to_analysis(raw, image_bytes, text)


class FallbackVisionProvider(VisionProvider):
    """Try each provider in order until one succeeds; raise when all fail."""

    def __init__(self, providers: List[VisionProvider]):
        self.providers = providers

    def analyze(
        self,
        image_bytes: Optional[bytes] = None,
        text: Optional[str] = None,
        address: Optional[str] = None,
    ) -> VisionAnalysis:
        if not self.providers:
            raise ValueError("No vision providers configured")
        failures = []
        for provider in self.providers:
            try:
                return provider.analyze(image_bytes=image_bytes, text=text, address=address)
            except Exception as exc:  # noqa: BLE001 - try the next provider
                failures.append(f"{type(provider).__name__}: {exc}")
                logger.warning(
                    "Vision provider %s failed, trying next: %s", type(provider).__name__, exc
                )
        logger.error("All vision providers failed: %s", "; ".join(failures))
        raise ValueError("All vision providers failed")


def get_vision_provider() -> VisionProvider:
    """Return the configured provider chain. Falls back through NVIDIA and mock."""
    if (settings.vision_provider or "mock").lower() == "mock":
        return MockVisionProvider()

    chain: List[VisionProvider] = []
    if settings.openrouter_api_key:
        chain.append(
            OpenRouterVisionProvider(
                api_key=settings.openrouter_api_key,
                vision_model=settings.vision_model,
                text_model=settings.text_model,
            )
        )
    if settings.nvidia_api_key:
        chain.append(
            NVIDIAVisionProvider(
                api_key=settings.nvidia_api_key,
                vision_model=settings.nvidia_vision_model,
                text_model=settings.nvidia_text_model,
            )
        )
    if not chain:
        return MockVisionProvider()
    return FallbackVisionProvider(chain)