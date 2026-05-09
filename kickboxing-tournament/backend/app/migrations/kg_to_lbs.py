"""One-time, idempotent migration: convert legacy kg-based weight data to pounds.

Runs automatically from `init_db()` on app startup so a deploy that ships the
lbs-based code self-heals an existing kg-based database (otherwise queries
against `tournaments.weighin_tolerance_lbs` blow up because the column is
still named `weighin_tolerance_kg`, which manifests as 503s on every API call).

Idempotent: if the rename has already happened (no `weighin_tolerance_kg`
column on `tournaments`), the function exits without touching any rows.
"""

import json
import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.services.divisions import KG_TO_LBS

log = logging.getLogger(__name__)


def _round1(v):
    return round(v * KG_TO_LBS, 1) if v is not None else None


def migrate(engine: Engine) -> bool:
    """Convert any kg-era data to lbs. Returns True if a migration ran."""
    insp = inspect(engine)
    if "tournaments" not in insp.get_table_names():
        return False

    cols = {c["name"] for c in insp.get_columns("tournaments")}
    if "weighin_tolerance_kg" not in cols:
        # Already migrated (or DB was created fresh in lbs).
        return False

    log.warning("kg->lbs migration: detected legacy column, converting weights now.")

    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE tournaments RENAME COLUMN weighin_tolerance_kg TO weighin_tolerance_lbs"
        ))
        conn.execute(
            text("UPDATE tournaments SET weighin_tolerance_lbs = weighin_tolerance_lbs * :f"),
            {"f": KG_TO_LBS},
        )

        for sql in [
            "UPDATE divisions SET weight_class_min = weight_class_min * :f WHERE weight_class_min IS NOT NULL",
            "UPDATE divisions SET weight_class_max = weight_class_max * :f WHERE weight_class_max IS NOT NULL",
            "UPDATE competitors SET declared_weight = declared_weight * :f WHERE declared_weight IS NOT NULL",
            "UPDATE registrations SET declared_weight = declared_weight * :f WHERE declared_weight IS NOT NULL",
        ]:
            conn.execute(text(sql), {"f": KG_TO_LBS})

        rows = conn.execute(text("SELECT id, weight_presets FROM tournaments")).fetchall()
        for row in rows:
            tid, presets = row[0], row[1]
            if not presets:
                continue
            data = presets if isinstance(presets, list) else json.loads(presets)
            new_presets = [
                {
                    "name": p.get("name"),
                    "min_lbs": _round1(p.get("min_kg")) if "min_kg" in p else p.get("min_lbs"),
                    "max_lbs": _round1(p.get("max_kg")) if "max_kg" in p else p.get("max_lbs"),
                }
                for p in data
            ]
            conn.execute(
                text("UPDATE tournaments SET weight_presets = :v WHERE id = :id"),
                {"v": json.dumps(new_presets), "id": tid},
            )

    log.warning("kg->lbs migration complete.")
    return True
