"""Zetaris insights router.

GET /api/insights returns read-only analytics from the Zetaris gateway.

- 503 when Zetaris is not configured (missing env vars)
- 502 when the queries fail
- 200 with the payload otherwise
- ?refresh=true bypasses the in-memory cache
"""

from fastapi import APIRouter, HTTPException

from services.zetaris import (
    ZetarisError,
    ZetarisNotConfiguredError,
    fetch_insights,
)

# Prefix is owned by main.py's include (prefix="/api/insights"),
# matching the bare-router convention of reports/market/partners.
router = APIRouter()


@router.get("")
async def get_insights(refresh: bool = False):
    """Read-only analytics: totals, breakdowns, top areas and a SQL log.

    Zetaris is treated as optional - if it is not configured the endpoint
    answers 503 so the dashboard can show a "not connected" state instead
    of breaking.
    """
    try:
        return await fetch_insights(force=refresh)
    except ZetarisNotConfiguredError:
        raise HTTPException(
            status_code=503,
            detail="Zetaris analytics is not configured on this server.",
        )
    except ZetarisError as exc:
        raise HTTPException(status_code=502, detail=exc.message)
