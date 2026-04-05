"""Pydantic schemas for request/response validation."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# --- Auth ---

class LoginRequest(BaseModel):
    password: str
    role: str = Field(pattern="^(admin|staff)$")


class TokenResponse(BaseModel):
    access_token: str
    role: str


# --- Tournament ---

class WeightPreset(BaseModel):
    name: str
    min_kg: Optional[float] = None
    max_kg: Optional[float] = None


class TournamentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    date: str = Field(min_length=1)
    venue: str = Field(min_length=1, max_length=200)
    num_rings: int = Field(ge=1, le=20, default=1)
    start_time: str = Field(default="09:00")
    bout_duration_minutes: int = Field(ge=1, le=30, default=3)
    break_duration_minutes: int = Field(ge=0, le=30, default=2)
    buffer_minutes: int = Field(ge=0, le=15, default=1)
    weighin_tolerance_kg: float = Field(ge=0, le=5, default=0.5)
    substitution_cutoff_round: int = Field(ge=1, default=1)
    no_show_policy: str = Field(default="walkover")
    weight_presets: Optional[List[WeightPreset]] = None


class TournamentUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    venue: Optional[str] = None
    num_rings: Optional[int] = None
    start_time: Optional[str] = None
    bout_duration_minutes: Optional[int] = None
    break_duration_minutes: Optional[int] = None
    buffer_minutes: Optional[int] = None
    weighin_tolerance_kg: Optional[float] = None
    substitution_cutoff_round: Optional[int] = None
    no_show_policy: Optional[str] = None
    weight_presets: Optional[List[WeightPreset]] = None


class TournamentResponse(BaseModel):
    id: int
    name: str
    date: str
    venue: str
    num_rings: int
    start_time: str
    bout_duration_minutes: int
    break_duration_minutes: int
    buffer_minutes: int
    weighin_tolerance_kg: float
    substitution_cutoff_round: int
    no_show_policy: str
    weight_presets: Optional[list] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Division ---

class DivisionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    weight_class_min: Optional[float] = None
    weight_class_max: Optional[float] = None
    gender: Optional[str] = None
    age_group: Optional[str] = None
    experience_level: Optional[str] = None


class DivisionResponse(BaseModel):
    id: int
    tournament_id: int
    name: str
    weight_class_min: Optional[float] = None
    weight_class_max: Optional[float] = None
    gender: Optional[str] = None
    age_group: Optional[str] = None
    experience_level: Optional[str] = None
    bracket_generated: bool
    bracket_started: bool
    competitor_count: Optional[int] = 0

    class Config:
        from_attributes = True


# --- Competitor ---

class CompetitorCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    declared_weight: Optional[float] = None
    gym_team: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=5, le=99)
    waiver_signed: bool = False
    seed: Optional[int] = None

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, v):
        if not v.strip():
            raise ValueError("Full name cannot be blank")
        return v.strip()


class CompetitorUpdate(BaseModel):
    full_name: Optional[str] = None
    declared_weight: Optional[float] = None
    gym_team: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    waiver_signed: Optional[bool] = None
    seed: Optional[int] = None
    status: Optional[str] = None


class CompetitorBulkCreate(BaseModel):
    competitors: List[CompetitorCreate]


class CompetitorResponse(BaseModel):
    id: int
    division_id: int
    full_name: str
    declared_weight: Optional[float] = None
    gym_team: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    waiver_signed: bool
    seed: Optional[int] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Match ---

class MatchResponse(BaseModel):
    id: int
    division_id: int
    round_number: int
    position: int
    competitor1_id: Optional[int] = None
    competitor2_id: Optional[int] = None
    competitor1_name: Optional[str] = None
    competitor2_name: Optional[str] = None
    winner_id: Optional[int] = None
    winner_name: Optional[str] = None
    next_match_id: Optional[int] = None
    is_bye: bool
    status: str
    result_method: Optional[str] = None
    ring_number: Optional[int] = None
    scheduled_time: Optional[str] = None
    queue_position: Optional[int] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class RecordResultRequest(BaseModel):
    winner_id: int
    result_method: str = Field(pattern="^(decision|ko|tko|dq|withdrawal|walkover|no_contest)$")
    notes: Optional[str] = None


class MatchStatusUpdate(BaseModel):
    status: str = Field(pattern="^(pending|queued|on_deck|in_progress|completed|cancelled)$")
    ring_number: Optional[int] = None
    queue_position: Optional[int] = None


# --- Bracket ---

class BracketGenerateRequest(BaseModel):
    seeding: str = Field(default="random", pattern="^(random|manual|separate_gyms)$")
    confirm_regenerate: bool = False


# --- Chaos Scenarios ---

class WithdrawalRequest(BaseModel):
    reason: str = Field(min_length=1)


class SubstitutionRequest(BaseModel):
    new_competitor: CompetitorCreate
    reason: str = Field(min_length=1)


class DivisionChangeRequest(BaseModel):
    new_division_id: int
    reason: str = Field(min_length=1)


class ResultCorrectionRequest(BaseModel):
    correct_winner_id: int
    result_method: str
    reason: str = Field(min_length=1)


class NoShowRequest(BaseModel):
    reason: Optional[str] = "No show"


# --- Scheduling ---

class ReorderRequest(BaseModel):
    match_ids: List[int]  # Ordered list of match IDs


# --- Audit Log ---

class AuditLogResponse(BaseModel):
    id: int
    tournament_id: int
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[dict] = None
    performed_by: str
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Sync ---

class SyncRequest(BaseModel):
    target_url: Optional[str] = None
    api_key: Optional[str] = None


class SyncStatusResponse(BaseModel):
    last_sync: Optional[datetime] = None
    status: str
    records_synced: int = 0
