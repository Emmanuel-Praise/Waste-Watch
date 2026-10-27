"""Zetaris analytics gateway.

Treats Zetaris as a *read-only* analytics layer on top of the app's MySQL
database:

- login -> proxy -> run SQL -> surface results in the dashboard
- tokens are cached and refreshed; a 401 forces one re-login and retry
- every call is best-effort: if Zetaris is down nothing in the core product
  breaks, corroboration/insights just come back empty
- insight results are cached in memory for a short TTL (refresh=True bypasses)

SQL is written in Spark dialect (Zetaris parses it, MySQL executes it through
the registered JDBC datasource), so prefer date_sub(current_date(), n) over
MySQL-only functions, and always lowercase both sides of LIKE comparisons.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from config import settings

INSIGHTS_CACHE_SECONDS = 30


# ─── Data classes ────────────────────────────────────────────────────────


@dataclass
class QueryResult:
    """Result of one SQL statement run through Zetaris."""

    headers: List[str]
    rows: List[List[Any]]
    total: int
    time_used: float

    def as_dicts(self) -> List[Dict[str, Any]]:
        if not self.headers:
            return []
        return [dict(zip(self.headers, row)) for row in self.rows]

    def column(self, name: str) -> List[Any]:
        if name not in self.headers:
            return []
        idx = self.headers.index(name)
        return [row[idx] if idx < len(row) else None for row in self.rows]

    def first_number(self) -> Optional[float]:
        for row in self.rows:
            for cell in row:
                if isinstance(cell, bool):
                    continue
                if isinstance(cell, (int, float)):
                    return float(cell)
                if isinstance(cell, str):
                    try:
                        return float(cell)
                    except ValueError:
                        continue
        return None


class ZetarisError(Exception):
    """Any failure talking to Zetaris."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ZetarisNotConfiguredError(ZetarisError):
    """Required Zetaris settings are missing."""


class ZetarisAuthError(ZetarisError):
    """Login against Zetaris failed."""


# ─── Internal state ──────────────────────────────────────────────────────

_state: Dict[str, Any] = {
    "id_token": None,
    "refresh_token": None,
    "org_id": None,
    "expires_at": 0.0,
    "lock": asyncio.Lock(),
    "insights_cache": None,  # {"at": float, "data": dict}
}


def is_configured() -> bool:
    return bool(
        settings.zetaris_base_url
        and settings.zetaris_email
        and settings.zetaris_password
        and settings.zetaris_database
    )


def _token_expired() -> bool:
    # refresh a minute early so a slow request never uses a dying token
    return time.time() > _state["expires_at"] - 60


async def _login(force: bool = False) -> str:
    """Log in (or reuse the cached token) and return a valid id token."""
    if not is_configured():
        raise ZetarisNotConfiguredError(
            "Zetaris is not configured. Set ZETARIS_BASE_URL, ZETARIS_EMAIL, "
            "ZETARIS_PASSWORD and ZETARIS_DATABASE."
        )

    async with _state["lock"]:
        if not force and _state["id_token"] and not _token_expired():
            return _state["id_token"]

        base = settings.zetaris_base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=settings.zetaris_timeout_seconds) as client:
                resp = await client.post(
                    f"{base}/api/auth/login",
                    json={
                        "username": settings.zetaris_email,
                        "password": settings.zetaris_password,
                    },
                )
        except httpx.HTTPError as exc:
            raise ZetarisAuthError(f"Zetaris unreachable: {exc}") from exc

        if resp.status_code != 200:
            raise ZetarisAuthError(
                f"Zetaris login failed (HTTP {resp.status_code})", resp.status_code
            )

        data = resp.json()
        token = data.get("idToken")
        if not token:
            raise ZetarisAuthError("Zetaris login returned no idToken")

        _state["id_token"] = token
        _state["refresh_token"] = data.get("refreshToken")
        _state["org_id"] = data.get("orgId")
        # The API hands out ~15 minute tokens; refresh a little before that.
        _state["expires_at"] = time.time() + 600
        return token


async def _proxy(
    method: str,
    path: str,
    *,
    json_body: Optional[dict] = None,
) -> tuple:
    """Call a proxied Zetaris endpoint with auth headers.

    Returns (status_code, parsed_body_or_text). Retries once after a forced
    re-login when the gateway answers 401.
    """
    base = settings.zetaris_base_url.rstrip("/")
    token = await _login()
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-ID": str(_state["org_id"] or ""),
        "Content-Type": "application/json",
    }

    async def send() -> httpx.Response:
        async with httpx.AsyncClient(timeout=settings.zetaris_timeout_seconds) as client:
            return await client.request(
                method, f"{base}{path}", json=json_body, headers=headers
            )

    resp = await send()

    if resp.status_code == 401:
        token = await _login(force=True)
        headers["Authorization"] = f"Bearer {token}"
        resp = await send()

    try:
        body: Any = resp.json()
    except ValueError:
        body = resp.text

    return resp.status_code, body


# ─── Core query ──────────────────────────────────────────────────────────


async def run_query(sql: str) -> QueryResult:
    """Run one read-only SQL statement through Zetaris."""
    if not sql or not sql.strip():
        raise ZetarisError("SQL query cannot be empty", 400)
    if not is_configured():
        raise ZetarisNotConfiguredError("Zetaris is not configured")

    status, body = await _proxy(
        "POST",
        "/api/proxy/sql-editor/sqls/run-query",
        json_body={"sql": sql},
    )

    if status != 200:
        detail = body.get("msg") if isinstance(body, dict) else str(body)
        raise ZetarisError(f"Zetaris query failed: {detail}", status)

    if not isinstance(body, dict):
        raise ZetarisError("Zetaris query returned an unexpected payload", status)

    rows = body.get("data") or []
    return QueryResult(
        headers=body.get("headers") or [],
        rows=rows,
        total=int(body.get("total", len(rows)) or 0),
        time_used=float(body.get("timeUsed", 0) or 0) / 1000.0,
    )


# ─── Insights ────────────────────────────────────────────────────────────


def _insights_queries() -> Dict[str, str]:
    """Read-only statements behind the insights view (Spark dialect).

    Deliberately merged: the gateway costs ~1s per round trip, so three
    statements beat seven even though they are launched concurrently.
    """
    db = settings.zetaris_database
    reports = f"{db}.waste_reports"
    locations = f"{db}.locations"
    return {
        "summary": (
            f"SELECT COUNT(*) AS total, "
            f"SUM(CASE WHEN created_at >= date_sub(current_date(), 1) THEN 1 ELSE 0 END) AS recent_24h, "
            f"SUM(CASE WHEN priority IN ('high', 'critical') THEN 1 ELSE 0 END) AS critical_high "
            f"FROM {reports}"
        ),
        "breakdowns": (
            f"SELECT 'status' AS dim, status AS k, COUNT(*) AS cnt FROM {reports} GROUP BY status "
            f"UNION ALL SELECT 'priority', priority, COUNT(*) AS cnt FROM {reports} GROUP BY priority "
            f"UNION ALL SELECT 'waste_type', waste_type, COUNT(*) AS cnt FROM {reports} GROUP BY waste_type"
        ),
        "top_areas": (
            f"SELECT l.address AS area, COUNT(*) AS cnt FROM {reports} r "
            f"JOIN {locations} l ON r.location_id = l.id "
            f"GROUP BY l.address ORDER BY cnt DESC LIMIT 10"
        ),
    }


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _sql_str(value: str) -> str:
    """Escape a value for a single-quoted SQL literal (apostrophes etc.)."""
    return str(value).replace("'", "''")


def _rows_for_log(name: str, sql: str, result: QueryResult) -> Dict[str, Any]:
    return {
        "name": name,
        "sql": sql,
        "rows": result.total,
        "time_used": round(result.time_used, 3),
        "ok": True,
    }


async def fetch_insights(force: bool = False) -> Dict[str, Any]:
    """Run the insight queries concurrently and merge them into one payload.

    Raises ZetarisNotConfiguredError when settings are missing and
    ZetarisError when every query fails (the router maps them to 503/502).
    """
    if not is_configured():
        raise ZetarisNotConfiguredError("Zetaris is not configured")

    cached = _state["insights_cache"]
    if (
        not force
        and cached
        and time.time() - cached["at"] < INSIGHTS_CACHE_SECONDS
    ):
        return {**cached["data"], "cached": True}

    queries = _insights_queries()
    names = list(queries)
    results = await asyncio.gather(
        *[run_query(queries[name]) for name in names], return_exceptions=True
    )

    log: List[Dict[str, Any]] = []
    payload: Dict[str, QueryResult] = {}
    for name, result in zip(names, results):
        if isinstance(result, BaseException):
            log.append(
                {
                    "name": name,
                    "sql": queries[name],
                    "rows": 0,
                    "time_used": 0.0,
                    "ok": False,
                    "error": str(result),
                }
            )
            continue
        payload[name] = result
        log.append(_rows_for_log(name, queries[name], result))

    if not payload:
        # nothing worked at all -> surface it instead of an empty dashboard
        first_error = next(
            (e for e in results if isinstance(e, ZetarisError)), None
        )
        raise first_error or ZetarisError("Zetaris queries failed")

    summary: Dict[str, Any] = {}
    if "summary" in payload and payload["summary"].rows:
        summary = payload["summary"].as_dicts()[0]

    breakdowns: Dict[str, Dict[str, int]] = {
        "status": {},
        "priority": {},
        "waste_type": {},
    }
    if "breakdowns" in payload:
        for row in payload["breakdowns"].as_dicts():
            dim = str(row.get("dim") or "")
            if dim in breakdowns:
                breakdowns[dim][str(row.get("k"))] = _to_int(row.get("cnt"))

    top_areas = [
        {"area": str(row.get("area") or ""), "count": _to_int(row.get("cnt"))}
        for row in (payload["top_areas"].as_dicts() if "top_areas" in payload else [])
        if row.get("area") is not None
    ]

    generated_at = datetime.utcnow().isoformat(timespec="seconds")
    data: Dict[str, Any] = {
        "total": _to_int(summary.get("total")),
        "by_status": breakdowns["status"],
        "by_priority": breakdowns["priority"],
        "by_waste_type": breakdowns["waste_type"],
        "top_areas": top_areas,
        "recent_24h": _to_int(summary.get("recent_24h")),
        "critical_high": _to_int(summary.get("critical_high")),
        "source": {
            "engine": "Spark SQL (Zetaris)",
            "database": settings.zetaris_database,
        },
        "queries": log,
        "generated_at": generated_at,
        "cached": False,
    }

    _state["insights_cache"] = {"at": time.time(), "data": data}
    return data


# ─── Corroboration ───────────────────────────────────────────────────────


async def corroborate(
    report_id: Optional[str],
    report_type: str = "",
    location: str = "",
) -> Optional[Dict[str, Any]]:
    """Count similar recent reports for a report (used as extra context).

    Best-effort by design: returns None whenever anything goes wrong so the
    caller can carry on. The location is never used as a WHERE filter - the
    same-area figure comes from a CASE inside SUM, which keeps the "other
    reports" count neutral.
    """
    if not is_configured():
        return None

    db = settings.zetaris_database
    days = max(1, settings.zetaris_corroboration_days)
    exclude = f"AND r.id <> '{_sql_str(report_id)}'" if report_id else ""
    kind = (
        f"AND LOWER(waste_type) = LOWER('{_sql_str(report_type)}')"
        if report_type
        else ""
    )
    same_area = (
        f"SUM(CASE WHEN LOWER(address) = LOWER('{_sql_str(location)}') THEN 1 ELSE 0 END)"
        if location
        else "0"
    )

    sql = (
        f"SELECT COUNT(*) AS cnt, {same_area} AS same_area "
        f"FROM {db}.waste_reports r "
        f"LEFT JOIN {db}.locations l ON r.location_id = l.id "
        f"WHERE r.created_at >= date_sub(current_date(), {days}) "
        f"{exclude} {kind}"
    )

    try:
        result = await run_query(sql)
        row = result.as_dicts()[0] if result.rows else {}
        return {
            "total": _to_int(row.get("cnt")),
            "same_area": _to_int(row.get("same_area")),
            "window_days": days,
            "checked_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
    except Exception:  # noqa: BLE001 - corroboration must never break a flow
        return None


# ─── Lifecycle ───────────────────────────────────────────────────────────


async def initialize() -> None:
    """Warm the token on startup. Failure is fine - it retries on first use."""
    if not is_configured():
        return
    try:
        await asyncio.wait_for(_login(), timeout=settings.zetaris_timeout_seconds)
    except (ZetarisError, asyncio.TimeoutError):
        pass
