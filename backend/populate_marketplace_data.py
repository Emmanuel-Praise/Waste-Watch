"""Populate the local marketplace with additional WST report/listing records."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import requests

from config import MEDIA_DIR
from database import SessionLocal
from models import Location, Listing, StatusHistory, WasteReport
from services.market import estimate_quantity_kg, price_for_type


NAMESPACE = uuid.UUID("b169b720-e77f-413b-9a06-e06211df8c48")

IMAGES = {
    "plastic": {
        "filename": "plastic-bottles.jpg",
        "commons_file": "Déchets des bouteilles plastiques.jpg",
    },
    "pile": {
        "filename": "waste-pile.jpg",
        "commons_file": "Pile of garbage.jpg",
    },
    "dump": {
        "filename": "garbage-dump.jpg",
        "commons_file": "Quibdo Garbage dump.jpg",
    },
    "bins": {
        "filename": "recycling-bins.jpg",
        "commons_file": "Regular rubbish bin and recycle bin.jpg",
    },
}

REPORTS = [
    {
        "ticket": "WST-019", "area": "Nkwen Market Gate", "lat": 5.9850, "lng": 10.1740,
        "type": "plastic", "severity": "medium", "priority": "medium", "size": "medium",
        "status": "pending", "age_days": 1, "image": "plastic",
        "description": "Plastic bottles and food containers have collected around the market entrance. Collection is requested before evening foot traffic.",
        "action": "Collect the plastic containers and separate recyclable material.",
        "hazards": ["busy pedestrian area"],
    },
    {
        "ticket": "WST-020", "area": "Mile 90, Nsongwa", "lat": 5.9780, "lng": 10.1880,
        "type": "organic", "severity": "medium", "priority": "medium", "size": "small",
        "status": "pending", "age_days": 1, "image": "pile",
        "description": "Vegetable trimmings and food scraps have been left beside the neighbourhood collection point. The uncovered waste is producing an odour.",
        "action": "Collect the organic waste and move it to a covered composting area.",
        "hazards": ["uncovered organic waste"],
    },
    {
        "ticket": "WST-021", "area": "Commercial Avenue, near the market", "lat": 5.9602, "lng": 10.1544,
        "type": "mixed", "severity": "high", "priority": "high", "size": "large",
        "status": "verified", "age_days": 2, "image": "dump",
        "description": "Household packaging and mixed refuse have accumulated beside a storm drain, narrowing the pedestrian path.",
        "action": "Clear the drain edge and separate recyclable materials during collection.",
        "hazards": ["near drainage", "pedestrian obstruction"],
    },
    {
        "ticket": "WST-022", "area": "Up Station Junction", "lat": 5.9673, "lng": 10.1618,
        "type": "plastic", "severity": "low", "priority": "low", "size": "small",
        "status": "verified", "age_days": 3, "image": "plastic",
        "description": "Empty water bottles and sachet wrappers are scattered around the public transport stop.",
        "action": "Collect the bottles and wrappers; keep the stop clear for passengers.",
        "hazards": [],
    },
    {
        "ticket": "WST-023", "area": "Ntarinkon Community Collection Point", "lat": 5.9730, "lng": 10.1767,
        "type": "organic", "severity": "medium", "priority": "medium", "size": "medium",
        "status": "pending", "age_days": 2, "image": "bins",
        "description": "Fruit and vegetable scraps are filling the organic collection bin and need a scheduled pickup.",
        "action": "Empty the organic bin and take suitable material for composting.",
        "hazards": [],
    },
    {
        "ticket": "WST-024", "area": "Mulang Roadside Collection Point", "lat": 5.9471, "lng": 10.1442,
        "type": "mixed", "severity": "medium", "priority": "medium", "size": "medium",
        "status": "pending", "age_days": 4, "image": "pile",
        "description": "Household packaging, cardboard and food waste are mixed at the roadside collection point.",
        "action": "Collect the pile and sort reusable packaging from organic waste.",
        "hazards": ["roadside collection point"],
    },
    {
        "ticket": "WST-025", "area": "Nkwen Roadside Market", "lat": 5.9891, "lng": 10.1697,
        "type": "plastic", "severity": "medium", "priority": "medium", "size": "medium",
        "status": "verified", "age_days": 5, "image": "plastic",
        "description": "Plastic drink bottles and packaging have gathered around the roadside stalls after market hours.",
        "action": "Arrange a market-side pickup and send bottles for recycling.",
        "hazards": [],
    },
    {
        "ticket": "WST-026", "area": "Old Town Neighbourhood Bin", "lat": 5.9538, "lng": 10.1655,
        "type": "organic", "severity": "low", "priority": "low", "size": "small",
        "status": "pending", "age_days": 6, "image": "bins",
        "description": "Compostable yard trimmings and food scraps are ready for collection from the neighbourhood bin.",
        "action": "Collect suitable organic material for composting.",
        "hazards": [],
    },
    {
        "ticket": "WST-027", "area": "Commercial Avenue Drain Walkway", "lat": 5.9588, "lng": 10.1553,
        "type": "plastic", "severity": "medium", "priority": "medium", "size": "medium",
        "status": "pending", "age_days": 2, "image": "plastic",
        "description": "PET bottles and clear plastic containers have collected along the market-side drain after afternoon trading.",
        "action": "Collect and separate recyclable plastic before the next rainfall.",
        "hazards": ["near drainage"],
    },
]


def stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{key}"))


def cache_images() -> dict[str, str]:
    folder = MEDIA_DIR / "marketplace"
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "WasteWatchMarketplace/1.0 (local media cache)"
    paths: dict[str, str] = {}
    for key, spec in IMAGES.items():
        target = folder / spec["filename"]
        if not target.is_file() or target.stat().st_size == 0:
            source = "https://commons.wikimedia.org/wiki/Special:FilePath/"
            url = source + requests.utils.quote(spec["commons_file"]) + "?width=960"
            response = session.get(url, timeout=30)
            response.raise_for_status()
            if not response.headers.get("Content-Type", "").startswith("image/"):
                raise RuntimeError(f"Expected an image for {spec['commons_file']}")
            target.write_bytes(response.content)
        paths[key] = f"/media/marketplace/{spec['filename']}"
    return paths


def populate() -> int:
    image_paths = cache_images()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    added = 0
    try:
        for item in REPORTS:
            if db.query(WasteReport).filter_by(ticket_id=item["ticket"]).first():
                continue

            report_id = stable_id("report", item["ticket"])
            location_id = stable_id("location", item["ticket"])
            created_at = now - timedelta(days=item["age_days"])
            location = Location(
                id=location_id,
                lat=item["lat"],
                lng=item["lng"],
                address=item["area"],
                created_at=created_at,
            )
            report = WasteReport(
                id=report_id,
                ticket_id=item["ticket"],
                location_id=location_id,
                waste_type=item["type"],
                severity=item["severity"],
                priority=item["priority"],
                description=item["description"],
                image_url=image_paths[item["image"]],
                status=item["status"],
                created_at=created_at,
                updated_at=created_at,
                severity_score={"low": 25, "medium": 50, "high": 78}[item["severity"]],
                hazard_level=item["severity"],
                estimated_size=item["size"],
                visible_hazards=item["hazards"],
                recommended_action=item["action"],
                confidence=0.92,
            )
            db.add_all([location, report])
            db.flush()

            history = ["pending"]
            if item["status"] == "verified":
                history.append("verified")
            previous = None
            for index, status in enumerate(history):
                db.add(StatusHistory(
                    id=stable_id("history", f"{item['ticket']}:{index}"),
                    report_id=report_id,
                    from_status=previous,
                    to_status=status,
                    notes="Report received" if index == 0 else "Report verified for collection.",
                    created_at=created_at + timedelta(hours=index),
                ))
                previous = status

            quantity = estimate_quantity_kg(item["size"])
            db.add(Listing(
                id=stable_id("listing", item["ticket"]),
                report_id=report_id,
                waste_type=item["type"],
                quantity_kg=quantity,
                available_kg=quantity,
                price_per_kg=price_for_type(item["type"]),
                status="available",
                created_at=created_at,
                updated_at=created_at,
            ))
            added += 1

        db.commit()
        return added
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    count = populate()
    print(f"Added {count} marketplace entries with linked reports and photos.")
    print(f"Images are cached under {MEDIA_DIR / 'marketplace'}.")
