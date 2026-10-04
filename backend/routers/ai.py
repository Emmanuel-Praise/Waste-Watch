"""
AI vision-analysis endpoints.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from schemas import VisionAnalysis
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