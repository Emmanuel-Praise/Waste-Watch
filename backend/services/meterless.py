"""Meterless local model proxy.

Talks to the Meterless runtime proxy (default http://127.0.0.1:8088), an
OpenAI-compatible `/v1/chat/completions` endpoint that routes the `worker`
model to whatever backend the runtime picks. Auth is a bearer token the
runtime writes to `%LOCALAPPDATA%\\ai.meterless.runtime\\proxy-token`; the
file is re-read on every call, so a rotated token is picked up without a
restart.

Meterless is optional and best-effort (same contract as the Zetaris
gateway): when it is disabled, the token is missing or the proxy is not
running, callers raise `MeterlessNotConfiguredError` / `MeterlessError` and
fall back to their other providers.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

from config import settings

logger = logging.getLogger(__name__)

# Probe used by check() to prove a round-trip through the proxy.
_PROBE_PROMPT = "Reply with exactly: OK"

# The routed models think aloud inside `content`, which the reply composer
# rejects as reasoning and burns its call budget. Asking for no reasoning
# makes them answer directly (verified: clean reply, ~3s instead of ~8s).
# Merge into the request body by every caller of this proxy.
EXTRA_BODY = {"reasoning_effort": "none"}


class MeterlessError(Exception):
    """Any failure talking to the Meterless proxy."""


class MeterlessNotConfiguredError(MeterlessError):
    """Meterless is switched off or the proxy token is missing."""


def token_path() -> Path:
    """Where the runtime writes the bearer token."""
    if settings.meterless_token_path:
        return Path(settings.meterless_token_path).expanduser()
    local = os.getenv("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "ai.meterless.runtime" / "proxy-token"


def read_token() -> str:
    """Read the proxy token fresh from disk; '' when unavailable."""
    try:
        return token_path().read_text(encoding="utf-8-sig").strip()
    except OSError:
        return ""


def api_base() -> str:
    """Root URL for chat calls, e.g. http://127.0.0.1:8088/v1."""
    base = settings.meterless_base_url.rstrip("/")
    return base if base.endswith("/v1") else f"{base}/v1"


def is_configured() -> bool:
    """True when Meterless is switched on and a proxy token is present."""
    return bool(settings.meterless_enabled and read_token())


def chat(
    messages: List[Dict[str, str]],
    *,
    max_tokens: int = 200,
    temperature: float = 0.7,
    timeout: Optional[float] = None,
) -> Dict:
    """One chat completion against the proxy. Returns the parsed payload.

    Raises MeterlessNotConfiguredError when there is nothing to call and
    MeterlessError for transport / HTTP failures.
    """
    if not settings.meterless_enabled:
        raise MeterlessNotConfiguredError("METERLESS_ENABLED is false.")
    token = read_token()
    if not token:
        raise MeterlessNotConfiguredError(f"Proxy token not found at {token_path()}.")

    url = f"{api_base()}/chat/completions"
    payload = {
        "model": settings.meterless_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        **EXTRA_BODY,
    }
    t0 = time.time()
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout or settings.meterless_timeout_seconds,
        )
    except requests.RequestException as exc:
        raise MeterlessError(f"Meterless proxy unreachable at {url}: {exc}") from exc

    if not response.ok:
        raise MeterlessError(
            f"Meterless proxy answered HTTP {response.status_code}: {response.text[:200]}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise MeterlessError("Meterless proxy returned a non-JSON body.") from exc

    logger.info(
        "Meterless completion in %.1fs (model=%s routed=%s)",
        time.time() - t0,
        settings.meterless_model,
        routed_model(data) or "?",
    )
    return data


def routed_model(payload: Dict) -> str:
    """Model the runtime actually answered with (proxy receipt, else echo)."""
    receipt = payload.get("meterless") or {}
    return str(receipt.get("routed_model") or payload.get("model") or "")


def first_content(payload: Dict) -> str:
    """Text of the first choice, '' when the proxy sent none."""
    try:
        return str(payload["choices"][0]["message"]["content"] or "")
    except (KeyError, IndexError, TypeError):
        return ""


def check(ping: bool = True) -> Dict:
    """Integration status for GET /api/ai/meterless/status.

    Never raises: disabled / unconfigured / unreachable all come back as a
    payload with a `status` field so the dashboard can render the state.
    """
    info: Dict = {
        "status": "ok",
        "enabled": bool(settings.meterless_enabled),
        "base_url": settings.meterless_base_url,
        "model": settings.meterless_model,
        "token_path": str(token_path()),
        "token_found": False,
        "connected": False,
        "routed_model": None,
        "latency_ms": None,
        "reply": None,
        "detail": "",
    }

    if not settings.meterless_enabled:
        info["status"] = "disabled"
        info["detail"] = "METERLESS_ENABLED is false on this server."
        return info

    info["token_found"] = bool(read_token())
    if not info["token_found"]:
        info["status"] = "not_configured"
        info["detail"] = f"Proxy token not found at {token_path()}."
        return info

    if not ping:
        info["status"] = "configured"
        info["detail"] = "Token present; proxy probe skipped (?ping=false)."
        return info

    t0 = time.time()
    try:
        payload = chat(
            [{"role": "user", "content": _PROBE_PROMPT}],
            max_tokens=64,
            temperature=0.0,
            timeout=min(20.0, float(settings.meterless_timeout_seconds)),
        )
    except MeterlessError as exc:
        info["status"] = "error"
        info["detail"] = str(exc)
        return info

    info["connected"] = True
    info["routed_model"] = routed_model(payload) or None
    info["latency_ms"] = int((time.time() - t0) * 1000)
    info["reply"] = first_content(payload).strip()[:200] or None
    info["detail"] = "Proxy answered a chat completion."
    return info
