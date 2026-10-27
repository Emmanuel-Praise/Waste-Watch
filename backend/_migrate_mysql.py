"""One-off migration: SQLite (bamenda.db) -> MySQL (wastewatch).

Usage:  python _migrate_mysql.py   (run from backend/)
Creates the schema in MySQL from the SQLAlchemy models, then copies every
row of every model table across. Safe to re-run: rows are only inserted
when the MySQL table is empty.
"""

import os
import sys

sys.path.insert(0, os.getcwd())

from sqlalchemy import create_engine, inspect, text

from database import Base
import models  # noqa: F401  (registers every table on Base.metadata)

MYSQL_URL = os.environ["MYSQL_URL"]
SQLITE_URL = "sqlite:///./bamenda.db"

src = create_engine(SQLITE_URL)
dst = create_engine(MYSQL_URL)

Base.metadata.create_all(bind=dst)

src_tables = set(inspect(src).get_table_names())
dst_conn = inspect(dst)

# Parents before children so MySQL foreign keys can be satisfied.
ORDER = [
    "users",
    "auth_tokens",
    "teams",
    "locations",
    "hotspots",
    "waste_reports",
    "status_history",
    "citizen_messages",
    "pending_intakes",
    "brand_notified",
    "vendors",
    "collectors",
    "listings",
    "claims",
    "payouts",
    "processed_messages",
]

tables = list(Base.metadata.tables.items())
tables.sort(key=lambda kv: ORDER.index(kv[0]) if kv[0] in ORDER else len(ORDER))

total = 0
for name, table in tables:
    if name not in src_tables:
        print(f"skip {name} (not in sqlite)")
        continue
    with src.connect() as sc:
        rows = [dict(r) for r in sc.execute(table.select()).mappings().all()]
    if not rows:
        print(f"{name}: 0 rows (nothing to copy)")
        continue
    if name == "waste_reports":
        # SQLite does not enforce foreign keys, so a report can point at a
        # hotspot row that no longer exists. MySQL does enforce them, so drop
        # the dangling link rather than lose the report.
        with src.connect() as sc:
            valid = {r[0] for r in sc.execute(text("SELECT id FROM hotspots"))}
        orphans = [r["hotspot_id"] for r in rows if r.get("hotspot_id") not in valid]
        if orphans:
            print(f"{name}: nulling {len(orphans)} dangling hotspot_id link(s)")
            for r in rows:
                if r.get("hotspot_id") not in valid:
                    r["hotspot_id"] = None
    with dst.begin() as dc:
        existing = dc.execute(text(f"SELECT COUNT(*) FROM `{name}`")).scalar() or 0
        if existing:
            print(f"{name}: mysql already has {existing} rows - skipped")
            continue
        dc.execute(table.insert(), rows)
    total += len(rows)
    print(f"{name}: {len(rows)} rows copied")

print(f"TOTAL rows copied: {total}")
