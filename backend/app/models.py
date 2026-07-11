"""
Core data models.

Kept deliberately simple for the MVP:
- Patient: minimal identity, no PII required beyond an optional display name.
- SymptomEntry: one row per day/log a user makes. This is what powers the
  pain timeline, symptom heat map, and the risk engine.
- CycleEntry: menstrual cycle start/end dates, used both for cycle history
  and to help the risk engine distinguish "pain only during periods" from
  "chronic pelvic pain" (a key diagnostic distinction for endometriosis).

Nothing here is a diagnosis. All of it is inputs to a *screening* risk score,
which is explicitly labelled as non-diagnostic everywhere it's surfaced.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    """
    An account that can log in. Kept separate from Patient so that, later,
    a clinician/admin account type could exist without a symptom-tracking
    profile of their own.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship(
        "Patient", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    display_name = Column(String, nullable=True)  # optional, can be pseudonymous
    age = Column(Integer, nullable=True)
    trying_to_conceive = Column(Boolean, default=False)
    months_trying_to_conceive = Column(Integer, nullable=True)
    family_history_endometriosis = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="patient")
    symptom_entries = relationship("SymptomEntry", back_populates="patient", cascade="all, delete-orphan")
    cycle_entries = relationship("CycleEntry", back_populates="patient", cascade="all, delete-orphan")


class SymptomEntry(Base):
    __tablename__ = "symptom_entries"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    entry_date = Column(Date, nullable=False)

    # Core symptom fields, each 0-10 unless noted otherwise
    pain_level = Column(Integer, nullable=False, default=0)
    on_period = Column(Boolean, default=False)  # was this pain during menstruation?
    pain_during_intercourse = Column(Boolean, default=False)
    bleeding_level = Column(Integer, nullable=True)  # 0-10 subjective heaviness
    fatigue_level = Column(Integer, nullable=True)   # 0-10
    bowel_symptoms = Column(Boolean, default=False)  # pain/diarrhea/constipation flare tied to cycle
    bladder_symptoms = Column(Boolean, default=False)
    took_pain_medication = Column(Boolean, default=False)
    missed_work_or_school = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="symptom_entries")


class CycleEntry(Base):
    __tablename__ = "cycle_entries"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    flow_level = Column(Integer, nullable=True)  # 0-10 subjective

    patient = relationship("Patient", back_populates="cycle_entries")
