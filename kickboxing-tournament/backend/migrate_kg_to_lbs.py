"""One-time migration: convert legacy kg-based weight data to pounds.

Use this only if your database was populated when the system stored weights
in kilograms. The script:

  - Renames `tournaments.weighin_tolerance_kg` -> `weighin_tolerance_lbs`
    and multiplies stored values by 2.2046226218.
  - Multiplies `divisions.weight_class_min` and `weight_class_max` by 2.2046226218.
  - Multiplies `competitors.declared_weight` and `registrations.declared_weight`
    by 2.2046226218.
  - Rewrites `tournaments.weight_presets` JSON, renaming `min_kg`/`max_kg`
    to `min_lbs`/`max_lbs` and converting values.

Idempotent guard: if `weighin_tolerance_lbs` already exists, the script aborts.

Usage:
  python migrate_kg_to_lbs.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import inspect, text
from app.database import engine
from app.services.divisions import KG_TO_LBS


def _round1(v):
    return round(v * KG_TO_LBS, 1) if v is not None else None


def main():
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("tournaments")}
    if "weighin_tolerance_lbs" in cols and "weighin_tolerance_kg" not in cols:
        print("Already migrated; nothing to do.")
        return

    with engine.begin() as conn:
        if "weighin_tolerance_kg" in cols:
            # Rename + convert.
            conn.execute(text(
                "ALTER TABLE tournaments RENAME COLUMN weighin_tolerance_kg TO weighin_tolerance_lbs"
            ))
            conn.execute(text(
                "UPDATE tournaments SET weighin_tolerance_lbs = weighin_tolerance_lbs * :f"
            ), {"f": KG_TO_LBS})

        # Convert division thresholds.
        for sql in [
            "UPDATE divisions SET weight_class_min = weight_class_min * :f WHERE weight_class_min IS NOT NULL",
            "UPDATE divisions SET weight_class_max = weight_class_max * :f WHERE weight_class_max IS NOT NULL",
            "UPDATE competitors SET declared_weight = declared_weight * :f WHERE declared_weight IS NOT NULL",
            "UPDATE registrations SET declared_weight = declared_weight * :f WHERE declared_weight IS NOT NULL",
        ]:
            conn.execute(text(sql), {"f": KG_TO_LBS})

        # Rewrite weight_presets JSON, key-by-key.
        rows = conn.execute(text("SELECT id, weight_presets FROM tournaments")).fetchall()
        import json
        for row in rows:
            tid, presets = row[0], row[1]
            if not presets:
                continue
            data = presets if isinstance(presets, list) else json.loads(presets)
            new_presets = []
            for p in data:
                new_presets.append({
                    "name": p.get("name"),
                    "min_lbs": _round1(p.get("min_kg")) if "min_kg" in p else p.get("min_lbs"),
                    "max_lbs": _round1(p.get("max_kg")) if "max_kg" in p else p.get("max_lbs"),
                })
            conn.execute(
                text("UPDATE tournaments SET weight_presets = :v WHERE id = :id"),
                {"v": json.dumps(new_presets), "id": tid},
            )

    print("Migration complete: kg values converted to lbs.")


if __name__ == "__main__":
    main()
