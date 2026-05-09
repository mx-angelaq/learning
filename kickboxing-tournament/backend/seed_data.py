"""Seed script: creates a demo tournament with divisions, competitors, and a generated bracket."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, init_db
from app.models.db_models import (
    Tournament, Division, Competitor, NoShowPolicy, CompetitorStatus
)
from app.services.bracket_engine import generate_bracket

def seed():
    init_db()
    db = SessionLocal()

    # Check if already seeded
    if db.query(Tournament).first():
        print("Database already has data. Skipping seed.")
        db.close()
        return

    # Create tournament
    t = Tournament(
        name="Spring Kickboxing Championship 2026",
        date="2026-04-15",
        venue="Metro Sports Arena",
        num_rings=2,
        start_time="09:00",
        bout_duration_minutes=3,
        break_duration_minutes=2,
        buffer_minutes=1,
        weighin_tolerance_lbs=1.1,
        substitution_cutoff_round=1,
        no_show_policy=NoShowPolicy.WALKOVER,
        weight_presets=[
            {"name": "Flyweight", "min_lbs": None, "max_lbs": 125},
            {"name": "Lightweight", "min_lbs": 125, "max_lbs": 155},
            {"name": "Middleweight", "min_lbs": 155, "max_lbs": 185},
            {"name": "Heavyweight", "min_lbs": 185, "max_lbs": None},
        ],
    )
    db.add(t)
    db.flush()

    # Create divisions (weight_class_* are pounds).
    divisions_data = [
        {"name": "Men's Lightweight", "weight_class_min": 125, "weight_class_max": 155,
         "gender": "male", "experience_level": "open"},
        {"name": "Men's Middleweight", "weight_class_min": 155, "weight_class_max": 185,
         "gender": "male", "experience_level": "open"},
        {"name": "Women's Lightweight", "weight_class_min": 115, "weight_class_max": 145,
         "gender": "female", "experience_level": "open"},
    ]

    competitors_data = {
        "Men's Lightweight": [
            {"full_name": "Alex Rivera", "declared_weight": 151.0, "gym_team": "Iron Fist MMA"},
            {"full_name": "Jordan Chen", "declared_weight": 152.0, "gym_team": "Tiger Muay Thai"},
            {"full_name": "Marcus Williams", "declared_weight": 149.5, "gym_team": "Hammer House"},
            {"full_name": "Dmitri Volkov", "declared_weight": 153.0, "gym_team": "Red Corner"},
            {"full_name": "Kai Tanaka", "declared_weight": 150.0, "gym_team": "Rising Sun Dojo"},
            {"full_name": "Luis Gutierrez", "declared_weight": 152.5, "gym_team": "Iron Fist MMA"},
            {"full_name": "Tyler Morrison", "declared_weight": 148.5, "gym_team": "Knockout Kings"},
        ],
        "Men's Middleweight": [
            {"full_name": "James Okafor", "declared_weight": 181.0, "gym_team": "Power Strike"},
            {"full_name": "Ryan Thompson", "declared_weight": 179.5, "gym_team": "Hammer House"},
            {"full_name": "Ahmed Hassan", "declared_weight": 183.0, "gym_team": "Red Corner"},
            {"full_name": "Viktor Petrov", "declared_weight": 182.0, "gym_team": "Eastern Block"},
            {"full_name": "Daniel Park", "declared_weight": 176.5, "gym_team": "Tiger Muay Thai"},
        ],
        "Women's Lightweight": [
            {"full_name": "Sarah Mitchell", "declared_weight": 139.0, "gym_team": "Iron Fist MMA"},
            {"full_name": "Yuki Nakamura", "declared_weight": 137.5, "gym_team": "Rising Sun Dojo"},
            {"full_name": "Elena Kowalski", "declared_weight": 141.0, "gym_team": "Knockout Kings"},
            {"full_name": "Priya Sharma", "declared_weight": 135.5, "gym_team": "Tiger Muay Thai"},
        ],
    }

    for div_data in divisions_data:
        div = Division(tournament_id=t.id, **div_data)
        db.add(div)
        db.flush()

        for comp_data in competitors_data.get(div_data["name"], []):
            comp = Competitor(
                division_id=div.id,
                status=CompetitorStatus.ACTIVE,
                waiver_signed=True,
                **comp_data,
            )
            db.add(comp)

    db.flush()

    # Generate brackets for all divisions
    for div in db.query(Division).filter(Division.tournament_id == t.id).all():
        matches, warning = generate_bracket(db, div, seeding="separate_gyms", performed_by="seed_script")
        if warning:
            print(f"  Warning for {div.name}: {warning}")
        print(f"  Generated bracket for {div.name}: {len(matches)} matches")

    db.commit()
    print(f"Seeded tournament: {t.name} (ID: {t.id})")
    print(f"  Divisions: {len(divisions_data)}")
    print(f"  Total competitors: {sum(len(v) for v in competitors_data.values())}")
    db.close()


if __name__ == "__main__":
    seed()
