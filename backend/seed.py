"""
Seed the local database from the sample data on first start.

Demo seeding is intentionally disabled: the app starts empty and only
real WhatsApp reports build the dashboard.
"""

import logging

logger = logging.getLogger(__name__)


def seed_if_empty() -> None:
    logger.info("Demo seeding disabled - dashboard starts empty.")
    return