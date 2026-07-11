"""
Pydantic schemas: define what the API accepts and returns.
Keeping these separate from the SQLAlchemy models (models.py) is standard
FastAPI practice -- it lets the API shape evolve independently of the DB schema.
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ---------- Patient ----------

class PatientCreate(BaseModel):
    display_name: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=120)
    trying_to_conceive: bool = False
    months_trying_to_conceive: Optional[int] = Field(None, ge=0)
    family_history_endometriosis: bool = False


class PatientOut(PatientCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Symptom Entry ----------

class SymptomEntryCreate(BaseModel):
    entry_date: date
    pain_level: int = Field(..., ge=0, le=10)
    on_period: bool = False
    pain_during_intercourse: bool = False
    bleeding_level: Optional[int] = Field(None, ge=0, le=10)
    fatigue_level: Optional[int] = Field(None, ge=0, le=10)
    bowel_symptoms: bool = False
    bladder_symptoms: bool = False
    took_pain_medication: bool = False
    missed_work_or_school: bool = False
    notes: Optional[str] = None


class SymptomEntryOut(SymptomEntryCreate):
    id: int
    patient_id: int

    class Config:
        from_attributes = True


# ---------- Cycle Entry ----------

class CycleEntryCreate(BaseModel):
    start_date: date
    end_date: Optional[date] = None
    flow_level: Optional[int] = Field(None, ge=0, le=10)


class CycleEntryOut(CycleEntryCreate):
    id: int
    patient_id: int

    class Config:
        from_attributes = True


# ---------- Risk Assessment ----------

class RiskFactor(BaseModel):
    label: str
    points: int
    detail: str


class RiskAssessmentOut(BaseModel):
    score: int
    max_score: int
    tier: str  # "low" | "moderate" | "high"
    recommendation: str
    factors: List[RiskFactor]
    entries_considered: int
    disclaimer: str = (
        "This is a screening tool, not a diagnosis. Only a qualified clinician "
        "can diagnose endometriosis, typically via pelvic exam, imaging, and/or "
        "laparoscopy. Use this score to decide whether to seek specialist care sooner."
    )
