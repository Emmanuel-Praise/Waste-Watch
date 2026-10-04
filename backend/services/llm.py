"""
Free-form LLM text generation for composing natural citizen replies.

Uses the same free-tier providers as vision analysis but WITHOUT the strict
JSON vision contract, so the model can write a real, contextual reply that
reads the citizen's words. Falls back through OpenRouter -> NVIDIA and returns
an empty string on total failure (callers keep a template as last resort).
"""

import logging
import time

import requests

from config import settings

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM = (
    "You are Waste Watch, the citizen messaging assistant for the Bamenda "
    "Municipality waste management office. You write short, warm, clear WhatsApp "
    "replies in simple English. Use a little Markdown: put emphasis in "
    "*asterisks*. Never invent tickets, IDs or statuses. Keep it under 200 words. "
    "Reply directly with the message text only - never describe your reasoning "
    "or planning.\n\n"
    "Services you can offer citizens:\n"
    "1. Report waste - photo/voice + location; AI verifies it, opens a ticket, "
    "and the citizen earns a 10% commission when a vendor buys the waste.\n"
    "2. EcoCollector - citizens register to collect, sort and deliver waste; "
    "they earn 55% of every completed delivery.\n"
    "3. Waste Vendor - businesses buy sorted plastic, organic and mixed "
    "materials and get WhatsApp alerts when new stock is reported.\n"
    "4. Marketplace - live listings of sellable waste with per-kg prices "
    "(plastic 150, organic 60, mixed 100 FCFA); vendors reserve the quantity "
    "they want.\n"
    "When greeting a new citizen, briefly introduce these services and ask what "
    "they would like. When a citizen declines to report waste, gently mention "
    "they can still earn as an EcoCollector or sell as a Vendor."
)


def _text_chain():
    """Yield (api_key, base_url, model) for each configured text provider."""
    if settings.openrouter_api_key:
        yield settings.openrouter_api_key, "https://openrouter.ai/api/v1", settings.text_model
    if settings.nvidia_api_key:
        yield settings.nvidia_api_key, "https://integrate.api.nvidia.com/v1", settings.nvidia_text_model


_REASONING_STARTS = (
    "we need", "we should", "we must", "i need", "i should", "let's",
    "lets ", "the user", "a citizen", "according to", "as waste watch",
    "as an assistant", "ok", "okay,", "here is a", "here is the",
    "here's a", "first,", "firstly", "surely", "as a",
)


def _looks_like_reasoning(text: str) -> bool:
    """True when the model wrote its thought-process instead of the reply."""
    low = text.lower().lstrip("*+- #").lstrip()
    return low.startswith(_REASONING_STARTS) or "reasoning" in low[:60]


def generate_text(
    context: str,
    *,
    instructions: str = "",
    system: str = _DEFAULT_SYSTEM,
    max_tokens: int = 200,
) -> str:
    """Ask the text model to write a reply. Returns '' if no provider works.

    Keeps a strict wall-clock budget: at most 3 model calls across the whole
    provider chain (first provider, its 429 retry, then the fallback) so a
    busy free tier can never stall a reply for minutes.
    """
    prompt = f"{context}\n\n{instructions}".strip()
    chain = list(_text_chain())
    calls_left = 3
    for api_key, base_url, model in chain:
        for attempt in range(2):
            if calls_left <= 0:
                return ""
            calls_left -= 1
            message = prompt
            if attempt:
                message += (
                    "\n\nOutput only the final chat message to the citizen "
                    "right now, with no explanations, no reasoning and no preamble."
                )
            t0 = time.time()
            try:
                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": message},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.7,
                    },
                    timeout=30,
                )
                if response.status_code == 429 and attempt == 0:
                    time.sleep(1)
                    continue
                response.raise_for_status()
                content = (
                    response.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )
                if content and content.strip():
                    content = content.strip()
                    if _looks_like_reasoning(content):
                        continue
                    logger.info("LLM reply done in %.1fs via %s", time.time() - t0, model)
                    return content
            except Exception as exc:  # noqa: BLE001 - try next provider
                logger.warning("LLM reply failed via %s in %.1fs: %s", model, time.time() - t0, exc)
                break
    return ""