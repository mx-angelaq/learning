"""Weight class division definitions and auto-assignment.

Single source of truth for default division thresholds. All weights stored
and compared in pounds (lbs). Division boundaries are open-low / closed-high:
a competitor is in division D when (D.min_lbs, D.max_lbs] contains their weight,
where None min/max means open-ended.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.db_models import Division


# Conversion factor used by the one-time kg -> lbs migration helper.
KG_TO_LBS = 2.2046226218


# Default tournament weight class presets, in pounds.
# Mirrors the previous kg-based MMA-style preset but expressed in lbs.
DEFAULT_WEIGHT_PRESETS_LBS = [
    {"name": "Strawweight", "min_lbs": None, "max_lbs": 115.0},
    {"name": "Flyweight", "min_lbs": 115.0, "max_lbs": 125.0},
    {"name": "Bantamweight", "min_lbs": 125.0, "max_lbs": 135.0},
    {"name": "Featherweight", "min_lbs": 135.0, "max_lbs": 145.0},
    {"name": "Lightweight", "min_lbs": 145.0, "max_lbs": 155.0},
    {"name": "Welterweight", "min_lbs": 155.0, "max_lbs": 170.0},
    {"name": "Middleweight", "min_lbs": 170.0, "max_lbs": 185.0},
    {"name": "Light Heavyweight", "min_lbs": 185.0, "max_lbs": 205.0},
    {"name": "Heavyweight", "min_lbs": 205.0, "max_lbs": None},
]


def assign_division(db: Session, tournament_id: int,
                    weight_lbs: Optional[float],
                    gender: Optional[str] = None) -> Optional[Division]:
    """Find the Division (in `tournament_id`) whose lbs range contains weight_lbs.

    Boundary convention: lower exclusive, upper inclusive.
    A division with min=None matches everyone up to its max; max=None matches
    everyone above its min. If `gender` is provided, only divisions with a
    matching gender (or no gender restriction) are considered.
    Returns None if no division matches.
    """
    if weight_lbs is None:
        return None

    divisions: List[Division] = (
        db.query(Division)
        .filter(Division.tournament_id == tournament_id)
        .all()
    )

    candidates = []
    for d in divisions:
        if gender and d.gender and d.gender != gender:
            continue
        lo = d.weight_class_min if d.weight_class_min is not None else float("-inf")
        hi = d.weight_class_max if d.weight_class_max is not None else float("inf")
        if lo < weight_lbs <= hi:
            candidates.append(d)

    if not candidates:
        return None
    # Prefer gender-specific match over a generic (no gender) division.
    if gender:
        gendered = [c for c in candidates if c.gender == gender]
        if gendered:
            return gendered[0]
    return candidates[0]
