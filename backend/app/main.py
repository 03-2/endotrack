"""
EndoTrack MVP backend, now with authentication.

Run with (from the backend/ folder, inside your virtualenv):
    uvicorn app.main:app --reload

Then visit http://127.0.0.1:8000/docs for interactive API docs.

Auth model: each User has exactly one Patient profile. All patient/symptom/
cycle/risk routes now require a valid Bearer token and only ever operate on
the calling user's own patient record -- there is no "give me patient id 5"
by number anymore from the frontend's perspective; it's always "my" data.
"""
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import models, schemas, risk_engine, auth
from .database import engine, get_db, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="EndoTrack MVP API",
    description=(
        "Symptom tracking, cycle history, and a rules-based, non-diagnostic "
        "endometriosis screening risk score. Requires authentication."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# ---------- Auth ----------

@app.post("/auth/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    user = models.User(email=user_in.email, hashed_password=auth.hash_password(user_in.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm uses a field called "username" -- we treat
    # that as the email address here, since that's what the frontend sends.
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@app.get("/auth/me", response_model=schemas.UserOut)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ---------- Helper: get the calling user's own patient record ----------

def _get_own_patient(db: Session, current_user: models.User) -> models.Patient:
    patient = db.query(models.Patient).filter(models.Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="No patient profile yet for this account")
    return patient


# ---------- Patient profile (one per user) ----------

@app.post("/patients", response_model=schemas.PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    patient_in: schemas.PatientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    existing = db.query(models.Patient).filter(models.Patient.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="This account already has a patient profile")

    db_patient = models.Patient(user_id=current_user.id, **patient_in.dict())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return db_patient


@app.get("/patients/me", response_model=schemas.PatientOut)
def get_my_patient(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return _get_own_patient(db, current_user)


# ---------- Symptom entries ----------

@app.post("/patients/me/symptoms", response_model=schemas.SymptomEntryOut, status_code=status.HTTP_201_CREATED)
def add_symptom_entry(
    entry: schemas.SymptomEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    patient = _get_own_patient(db, current_user)
    db_entry = models.SymptomEntry(patient_id=patient.id, **entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.get("/patients/me/symptoms", response_model=List[schemas.SymptomEntryOut])
def list_symptom_entries(
    start: Optional[date] = None,
    end: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    patient = _get_own_patient(db, current_user)
    query = db.query(models.SymptomEntry).filter(models.SymptomEntry.patient_id == patient.id)
    if start:
        query = query.filter(models.SymptomEntry.entry_date >= start)
    if end:
        query = query.filter(models.SymptomEntry.entry_date <= end)
    return query.order_by(models.SymptomEntry.entry_date).all()


# ---------- Cycle entries ----------

@app.post("/patients/me/cycles", response_model=schemas.CycleEntryOut, status_code=status.HTTP_201_CREATED)
def add_cycle_entry(
    entry: schemas.CycleEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    patient = _get_own_patient(db, current_user)
    db_entry = models.CycleEntry(patient_id=patient.id, **entry.dict())
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.get("/patients/me/cycles", response_model=List[schemas.CycleEntryOut])
def list_cycle_entries(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    patient = _get_own_patient(db, current_user)
    return (
        db.query(models.CycleEntry)
        .filter(models.CycleEntry.patient_id == patient.id)
        .order_by(models.CycleEntry.start_date)
        .all()
    )


# ---------- Risk assessment ----------

@app.get("/patients/me/risk-score", response_model=schemas.RiskAssessmentOut)
def get_risk_score(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    patient = _get_own_patient(db, current_user)
    entries = (
        db.query(models.SymptomEntry)
        .filter(models.SymptomEntry.patient_id == patient.id)
        .all()
    )
    return risk_engine.assess_risk(patient, entries)


# ---------- Timeline / heat map data ----------

@app.get("/patients/me/timeline")
def get_timeline(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    patient = _get_own_patient(db, current_user)
    entries = (
        db.query(models.SymptomEntry)
        .filter(models.SymptomEntry.patient_id == patient.id)
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
