"""CLI entry point for the kg -> lbs data migration.

The same logic also runs automatically on application startup; this script
exists so the migration can be triggered (or re-checked) manually:

    python migrate_kg_to_lbs.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine
from app.migrations.kg_to_lbs import migrate


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ran = migrate(engine)
    print("Migration complete." if ran else "Already migrated; nothing to do.")
