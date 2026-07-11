"""
EndoTrack MVP backend.

Run with (from the backend/ folder, inside your virtualenv):
    uvicorn app.main:app --reload

Then visit http://127.0.0.1:8000/docs for interactive API docs (Swagger UI) --
FastAPI generates this for free from the schemas below.
"""
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, risk_engine
from .database import engine, get_db, Base

# Create tables on startup if they don't exist yet (fine for MVP; use Alembic
# migrations once the schema stabilizes and you have real user data).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EndoTrack MVP API",
    description=(
        "Symptom tracking, cycle history, and a rules-based, non-diagnostic "
        "endometriosis screening risk score."
    ),
    version="0.1.0",
)

# Allow the local frontend (opened as a static HTML file or via a dev server)
# to call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---------- Patients ----------

@app.post("/patients", response_model=schemas.PatientOut)
def create_patient(patient: schemas.PatientCreate, db: Session = Depends(get_db)):
    db_patient = models.Patient(**patient.dict())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


@app.get("/patients/{patient_id}", response_model=schemas.PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _get_patient_or_404(patient_id: int, db: Session) -> models.Patient:
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


# ---------- Symptom entries ----------

@app.post("/patients/{patient_id}/symptoms", response_model=schemas.SymptomEntryOut)
def add_symptom_entry(
    patient_id: int, entry: schemas.SymptomEntryCreate, db: Session = Depends(get_db)
):
    _get_patient_or_404(patient_id, db)
    db_entry = models.SymptomEntry(patient_id=patient_id, **entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.get("/patients/{patient_id}/symptoms", response_model=List[schemas.SymptomEntryOut])
def list_symptom_entries(
    patient_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
):
    _get_patient_or_404(patient_id, db)
    query = db.query(models.SymptomEntry).filter(models.SymptomEntry.patient_id == patient_id)
    if start:
        query = query.filter(models.SymptomEntry.entry_date >= start)
    if end:
        query = query.filter(models.SymptomEntry.entry_date <= end)
    return query.order_by(models.SymptomEntry.entry_date).all()


# ---------- Cycle entries ----------

@app.post("/patients/{patient_id}/cycles", response_model=schemas.CycleEntryOut)
def add_cycle_entry(
    patient_id: int, entry: schemas.CycleEntryCreate, db: Session = Depends(get_db)
):
    _get_patient_or_404(patient_id, db)
    db_entry = models.CycleEntry(patient_id=patient_id, **entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.get("/patients/{patient_id}/cycles", response_model=List[schemas.CycleEntryOut])
def list_cycle_entries(patient_id: int, db: Session = Depends(get_db)):
    _get_patient_or_404(patient_id, db)
    return (
        db.query(models.CycleEntry)
        .filter(models.CycleEntry.patient_id == patient_id)
        .order_by(models.CycleEntry.start_date)
        .all()
    )


# ---------- Risk assessment ----------

@app.get("/patients/{patient_id}/risk-score", response_model=schemas.RiskAssessmentOut)
def get_risk_score(patient_id: int, db: Session = Depends(get_db)):
    patient = _get_patient_or_404(patient_id, db)
    entries = (
        db.query(models.SymptomEntry)
        .filter(models.SymptomEntry.patient_id == patient_id)
        .all()
    )
    result = risk_engine.assess_risk(patient, entries)
    return result


# ---------- Timeline / heat map data ----------

@app.get("/patients/{patient_id}/timeline")
def get_timeline(patient_id: int, db: Session = Depends(get_db)):
    """
    Returns a simple date -> pain_level series, convenient for charting
    a pain timeline or a calendar heat map on the frontend.
    """
    _get_patient_or_404(patient_id, db)
    entries = (
        db.query(models.SymptomEntry)
        .filter(models.SymptomEntry.patient_id == patient_id)
        .order_by(models.SymptomEntry.entry_date)
        .all()
    )
    return [
        {
            "date": e.entry_date.isoformat(),
            "pain_level": e.pain_level,
            "on_period": e.on_period,
            "fatigue_level": e.fatigue_level,
            "bowel_symptoms": e.bowel_symptoms,
            "bladder_symptoms": e.bladder_symptoms,
        }
        for e in entries
    ]
