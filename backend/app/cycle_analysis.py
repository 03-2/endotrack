"""
Cycle-day vs pain correlation analysis.

The core clinical question this answers: "is pain worse at a particular
point in the cycle (e.g. right before or during a period), or is it spread
out/constant?" That distinction matters for both patients (predicting
flare-ups) and clinicians (a pain pattern tightly clustered around
menstruation reads differently than pain that's constant all month).

Approach:
1. Sort the patient's logged cycles by start date.
2. For each cycle, define its date window: from that cycle's start date up
   to (but not including) the next cycle's start date. The last cycle's
   window is capped at 45 days out, since we have no "next start" to bound
   it and very long unbounded windows would pull in unrelated data.
3. For every symptom entry, find which cycle window it falls into and
   compute "cycle day" = how many days after that cycle's start date it was
   (day 1 = the day the period started).
4. Group all entries by cycle day (pooling across all of the patient's
   logged cycles) and average the pain level for each day.

This intentionally does NOT try to handle irregular cycle lengths with any
sophistication -- it's a straightforward pooled average, good enough to
reveal a pattern once a few cycles are logged, not a forecasting model.
"""
from datetime import timedelta
from typing import List

from .models import CycleEntry, SymptomEntry

MAX_CYCLE_WINDOW_DAYS = 45


def _cycle_windows(cycles: List[CycleEntry]):
    """
    Returns a list of (start_date, end_date_exclusive) tuples, one per cycle,
    sorted chronologically.
    """
    sorted_cycles = sorted(cycles, key=lambda c: c.start_date)
    windows = []
    for i, cycle in enumerate(sorted_cycles):
        if i + 1 < len(sorted_cycles):
            end_exclusive = sorted_cycles[i + 1].start_date
        else:
            end_exclusive = cycle.start_date + timedelta(days=MAX_CYCLE_WINDOW_DAYS)
        windows.append((cycle.start_date, end_exclusive))
    return windows


def compute_cycle_day_pain(cycles: List[CycleEntry], entries: List[SymptomEntry]) -> dict:
    """
    Returns a dict with:
      - "points": list of {cycle_day, avg_pain, entry_count}, sorted by day
      - "cycles_logged": how many cycles contributed
      - "entries_matched": how many symptom entries fell inside a cycle window
    """
    if not cycles:
        return {"points": [], "cycles_logged": 0, "entries_matched": 0}

    windows = _cycle_windows(cycles)

    # cycle_day -> list of pain levels logged on that day, pooled across cycles
    pain_by_day: dict[int, List[int]] = {}
    entries_matched = 0

    for entry in entries:
        for start, end_exclusive in windows:
            if start <= entry.entry_date < end_exclusive:
                cycle_day = (entry.entry_date - start).days + 1
                pain_by_day.setdefault(cycle_day, []).append(entry.pain_level)
                entries_matched += 1
                break  # an entry belongs to at most one cycle window

    points = [
        {
            "cycle_day": day,
            "avg_pain": round(sum(pains) / len(pains), 2),
            "entry_count": len(pains),
        }
        for day, pains in sorted(pain_by_day.items())
    ]

    return {
        "points": points,
        "cycles_logged": len(cycles),
        "entries_matched": entries_matched,
    }
