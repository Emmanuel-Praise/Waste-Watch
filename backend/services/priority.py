"""
Priority engine.

Deterministic, transparent rules that turn analysis signals into a
priority level: low, medium, high or critical. The same inputs always
produce the same output so the logic is easy to audit and adjust.
"""

from typing import List, Optional

SEVERITY_TO_LABEL = {1: "low", 2: "medium", 3: "high", 4: "high", 5: "critical"}
PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
RANK_PRIORITY = ["low", "medium", "high", "critical"]

SENSITIVE_KEYWORDS = (
    "school", "clinic", "health", "hospital", "market", "water",
    "river", "residential", "children", "church",
)


def severity_label(severity_score: Optional[int]) -> str:
    """Map a 1-5 severity score to a low/medium/high/critical label."""
    if not severity_score:
        return "low"
    return SEVERITY_TO_LABEL.get(severity_score, "low")


def compute_priority(
    severity_score: Optional[int] = None,
    hazard_level: Optional[str] = None,
    waste_type: Optional[str] = None,
    address: Optional[str] = None,
    report_count: int = 1,
) -> str:
    """
    Compute a priority from multiple factors.

    Base comes from severity (1-5). Then rank is incremented for:
      - a critical hazard level (or high hazard with high severity),
      - hazardous or medical waste types,
      - a sensitive location context (school, clinic, market, water...),
      - multiple citizen reports at the same hotspot.

    The result is clamped between low and critical.
    """
    rank = PRIORITY_RANK.get(severity_label(severity_score), 0)

    hazard = (hazard_level or "").lower()
    if hazard == "critical":
        rank += 1
    elif hazard == "high" and (severity_score or 0) >= 3:
        rank += 1

    waste = (waste_type or "").lower()
    if waste in ("hazardous", "medical"):
        rank += 1

    if address and any(k in address.lower() for k in SENSITIVE_KEYWORDS):
        rank += 1

    if report_count and report_count > 1:
        rank += min(report_count - 1, 2)

    clamped = max(0, min(rank, 3))
    return RANK_PRIORITY[clamped]