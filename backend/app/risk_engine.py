"""
Rules-based endometriosis screening risk engine.

Deliberately NOT a black-box ML model for the MVP:
- Every point awarded has a human-readable reason (see RiskFactor.detail).
- Clinicians and users can see exactly why a score is what it is.
- It's based on commonly cited endometriosis red flags (severe dysmenorrhea,
  dyspareunia, chronic pelvic pain distinct from menstrual pain, cyclical bowel/
  bladder symptoms, infertility, family history) -- the same signals mentioned
  in the project brief.

This is a screening heuristic, not a validated clinical instrument. It has not
been peer reviewed or clinically validated. Treat point values and thresholds
as a starting point to refine with an actual clinician/gynecologist before any
real-world use, and present it to users as a triage nudge only, never as a
diagnosis substitute.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean
from typing import List, Optional

from .models import SymptomEntry, Patient


@dataclass
class Factor:
    label: str
    points: int
    detail: str


def _severe_menstrual_pain(entries: List[SymptomEntry]) -> Optional[Factor]:
    period_entries = [e for e in entries if e.on_period]
    if len(period_entries) < 3:
        return None
    avg_pain = mean(e.pain_level for e in period_entries)
    if avg_pain >= 7:
        return Factor(
            "Severe menstrual pain",
            3,
            f"Average logged pain during periods is {avg_pain:.1f}/10 across "
            f"{len(period_entries)} entries (threshold: 7/10).",
        )
    return None


def _pain_during_intercourse(entries: List[SymptomEntry]) -> Optional[Factor]:
    count = sum(1 for e in entries if e.pain_during_intercourse)
    if count >= 2:
        return Factor(
            "Pain during intercourse (dyspareunia)",
            2,
            f"Reported on {count} separate log entries.",
        )
    return None


def _chronic_pelvic_pain(entries: List[SymptomEntry]) -> Optional[Factor]:
    off_period_pain = [e for e in entries if not e.on_period and e.pain_level >= 5]
    if len(off_period_pain) >= 3:
        return Factor(
            "Chronic pelvic pain outside menstruation",
            2,
            f"{len(off_period_pain)} entries show pain >=5/10 on days not "
            "marked as 'on period' -- suggests pain isn't purely menstrual.",
        )
    return None


def _cyclical_bowel_bladder(entries: List[SymptomEntry]) -> Optional[Factor]:
    period_entries = [e for e in entries if e.on_period]
    flagged = sum(1 for e in period_entries if e.bowel_symptoms or e.bladder_symptoms)
    if period_entries and flagged / len(period_entries) >= 0.5 and flagged >= 2:
        return Factor(
            "Cyclical bowel/bladder symptoms",
            1,
            f"Bowel or bladder symptoms co-occur with {flagged}/{len(period_entries)} "
            "logged periods.",
        )
    return None


def _functional_impact(entries: List[SymptomEntry]) -> Optional[Factor]:
    missed = sum(1 for e in entries if e.missed_work_or_school)
    if missed >= 2:
        return Factor(
            "Missed work/school due to symptoms",
            1,
            f"Work or school was missed on {missed} logged occasions.",
        )
    return None


def _fertility_difficulty(patient: Patient) -> Optional[Factor]:
    if patient.trying_to_conceive and (patient.months_trying_to_conceive or 0) >= 12:
        return Factor(
            "Difficulty conceiving",
            2,
            f"Trying to conceive for {patient.months_trying_to_conceive} months "
            "without success (>=12 month threshold).",
        )
    return None


def _family_history(patient: Patient) -> Optional[Factor]:
    if patient.family_history_endometriosis:
        return Factor(
            "Family history of endometriosis",
            1,
            "A first-degree relative has a diagnosis of endometriosis.",
        )
    return None


MAX_SCORE = 3 + 2 + 2 + 1 + 1 + 2 + 1  # sum of all possible points = 12


def assess_risk(patient: Patient, entries: List[SymptomEntry]) -> dict:
    factors: List[Factor] = []

    for fn in (
        _severe_menstrual_pain,
        _pain_during_intercourse,
        _chronic_pelvic_pain,
        _cyclical_bowel_bladder,
        _functional_impact,
    ):
        result = fn(entries)
        if result:
            factors.append(result)

    for fn in (_fertility_difficulty, _family_history):
        result = fn(patient)
        if result:
            factors.append(result)

    score = sum(f.points for f in factors)

    if score >= 7:
        tier = "high"
        recommendation = (
            "Multiple strong indicators are present. Consider booking an "
            "appointment with a gynecologist or endometriosis specialist soon, "
            "and bring your symptom timeline to the visit."
        )
    elif score >= 3:
        tier = "moderate"
        recommendation = (
            "Some indicators are present. Keep logging symptoms for a few more "
            "cycles, and consider discussing your pattern with a doctor, "
            "especially if pain is worsening."
        )
    else:
        tier = "low"
        recommendation = (
            "Few or no strong indicators yet based on current logs. Keep "
            "tracking, since patterns often become clearer after 2-3 cycles "
            "of data."
        )

    return {
        "score": score,
        "max_score": MAX_SCORE,
        "tier": tier,
        "recommendation": recommendation,
        "factors": [f.__dict__ for f in factors],
        "entries_considered": len(entries),
    }
