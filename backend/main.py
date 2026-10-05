"""
Bamenda Waste Management System - FastAPI Backend
Main application entry point
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import MEDIA_DIR
from database import init_db
from routers import ai, dashboard, market, partners, reports, voice, whatsapp
from seed import seed_if_empty

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_if_empty()
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Bamenda Waste Management API",
    description="API for municipal waste reporting and management",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration: local dev plus the hosted frontend (set FRONTEND_URL
# on Render, e.g. https://wastewatch-frontend.onrender.com).
import os as _os

_frontend_url = _os.getenv("FRONTEND_URL", "").strip().rstrip("/")
_allowed = ["http://localhost:5173", "http://localhost:3000"]
if _frontend_url and _frontend_url not in _allowed:
    _allowed.append(_frontend_url)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["whatsapp"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(market.router, prefix="/api/market", tags=["market"])
app.include_router(partners.router, prefix="/api/partners", tags=["partners"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])

# Serve incoming WhatsApp images so the dashboard can display them
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


@app.get("/")
def root():
    return {
        "message": "Bamenda Waste Management API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)