"""SQLAlchemy database models for the kickboxing tournament system."""

import datetime
import enum
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Enum, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    ON_DECK = "on_deck"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ResultMethod(str, enum.Enum):
    DECISION = "decision"
    KO = "ko"
    TKO = "tko"
    DQ = "dq"
    WITHDRAWAL = "withdrawal"
    WALKOVER = "walkover"
    NO_CONTEST = "no_contest"


class CompetitorStatus(str, enum.Enum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    DISQUALIFIED = "disqualified"
    NO_SHOW = "no_show"


class NoShowPolicy(str, enum.Enum):
    WALKOVER = "walkover"
    DQ = "dq"
    RESCHEDULE = "reschedule"


# --- Tournament ---

class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    date = Column(String(20), nullable=False)
    venue = Column(String(200), nullable=False)
    num_rings = Column(Integer, default=1)
    start_time = Column(String(10), nullable=False)  # HH:MM
    bout_duration_minutes = Column(Integer, default=3)
    break_duration_minutes = Column(Integer, default=2)
    buffer_minutes = Column(Integer, default=1)
    weighin_tolerance_kg = Column(Float, default=0.5)
    substitution_cutoff_round = Column(Integer, default=1)  # After this round, no subs
    no_show_policy = Column(Enum(NoShowPolicy), default=NoShowPolicy.WALKOVER)
    weight_presets = Column(JSON, nullable=True)  # Custom weight class presets
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    divisions = relationship("Division", back_populates="tournament", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tournament", cascade="all, delete-orphan")


# --- Division ---

class Division(Base):
    __tablename__ = "divisions"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    weight_class_min = Column(Float, nullable=True)
    weight_class_max = Column(Float, nullable=True)
    gender = Column(String(20), nullable=True)
    age_group = Column(String(50), nullable=True)
    experience_level = Column(String(50), nullable=True)
    bracket_generated = Column(Boolean, default=False)
    bracket_started = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    tournament = relationship("Tournament", back_populates="divisions")
    competitors = relationship("Competitor", back_populates="division", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="division", cascade="all, delete-orphan")


# --- Competitor ---

class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(Integer, primary_key=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(200), nullable=False)
    declared_weight = Column(Float, nullable=True)
    gym_team = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    age = Column(Integer, nullable=True)
    waiver_signed = Column(Boolean, default=False)
    seed = Column(Integer, nullable=True)
    status = Column(Enum(CompetitorStatus), default=CompetitorStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    division = relationship("Division", back_populates="competitors")


# --- Match (bracket node) ---

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    division_id = Column(Integer, ForeignKey("divisions.id", ondelete="CASCADE"), nullable=False)
    round_number = Column(Integer, nullable=False)  # 1 = first round, increasing
    position = Column(Integer, nullable=False)  # Position within the round (0-indexed)
    competitor1_id = Column(Integer, ForeignKey("competitors.id", ondelete="SET NULL"), nullable=True)
    competitor2_id = Column(Integer, ForeignKey("competitors.id", ondelete="SET NULL"), nullable=True)
    winner_id = Column(Integer, ForeignKey("competitors.id", ondelete="SET NULL"), nullable=True)
    next_match_id = Column(Integer, ForeignKey("matches.id", ondelete="SET NULL"), nullable=True)
    is_bye = Column(Boolean, default=False)
    status = Column(Enum(MatchStatus), default=MatchStatus.PENDING)
    result_method = Column(Enum(ResultMethod), nullable=True)
    ring_number = Column(Integer, nullable=True)
    scheduled_time = Column(String(10), nullable=True)  # HH:MM
    queue_position = Column(Integer, nullable=True)  # Order in ring queue
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    division = relationship("Division", back_populates="matches")
    competitor1 = relationship("Competitor", foreign_keys=[competitor1_id])
    competitor2 = relationship("Competitor", foreign_keys=[competitor2_id])
    winner = relationship("Competitor", foreign_keys=[winner_id])
    next_match = relationship("Match", remote_side=[id], foreign_keys=[next_match_id])


# --- Audit Log ---

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)  # competitor, match, division, bracket
    entity_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    performed_by = Column(String(50), nullable=False)  # admin, staff, system
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    tournament = relationship("Tournament", back_populates="audit_logs")


# --- Sync Tracking ---

class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, nullable=False)
    sync_type = Column(String(50), nullable=False)  # full, incremental
    status = Column(String(20), nullable=False)  # success, failed, in_progress
    records_synced = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
