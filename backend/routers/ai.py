"""
AI endpoints: vision analysis and the Meterless model proxy status.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from schemas import VisionAnalysis
from services.meterless import check as meterless_check
from services.vision import get_vision_provider

router = APIRouter()


@router.post("/analyze", response_model=VisionAnalysis)
async def analyze_image(file: UploadFile = File(...)):
    """Run vision analysis on an uploaded waste image and return a structured result."""
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image provided")

    provider = get_vision_provider()
    return provider.analyze(image_bytes=image_bytes)


@router.get("/meterless/status")
def meterless_status(ping: bool = True):
    """Status of the local Meterless model proxy. Always answers 200.

    Fields: status (ok | configured | disabled | not_configured | error),
    enabled, base_url, model, token_path, token_found, connected,
    routed_model, latency_ms, reply, detail.

    With ?ping=false only configuration is reported (no network call), so the
    dashboard can poll cheaply; by default a tiny completion is sent to prove
    the round-trip.
    """
    # sync def: the probe uses `requests`, FastAPI runs this in a threadpool.
    return meterless_check(ping=ping)