# EndoTrack MVP

A minimal, runnable slice of the EndoTrack Africa concept: **symptom logging →
pain timeline → rules-based, non-diagnostic risk score**. This is the
"Fastest MVP" core from the plan, built so you can run it today on Linux Mint
with VS Code, with no cloud accounts, API keys, or mobile toolchain required.

Everything else in the original brief (Flutter app, telemedicine, wearables,
ML on imaging, SMS reminders, research dashboard) is a natural *next step*
from this base, not a rewrite of it — see "Where to go next" below.

## What's here

```
endotrack-mvp/
  backend/           FastAPI + SQLite API
    app/
      main.py         routes
      models.py       DB tables (Patient, SymptomEntry, CycleEntry)
      schemas.py       request/response validation
      risk_engine.py   explainable, rules-based screening score
      database.py      DB connection (SQLite now, Postgres later = 1 line change)
    requirements.txt
  frontend/          Plain HTML/JS/CSS single page (no build step)
    index.html
    app.js
    style.css
```

## Authentication (added in v0.2)

Every account now needs to register with an email + password, then log in to
get a token before doing anything else. Passwords are hashed with bcrypt
before being stored -- the plaintext password is never saved. Each account
has exactly one patient profile, and every `/patients/me/...` route only
ever touches the logged-in user's own data.

Before running this anywhere beyond your own machine, set a real secret key
(used to sign login tokens) instead of the built-in development default:

```bash
export ENDOTRACK_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Run this in the same terminal before `uvicorn`, or add it to your shell
profile. Anyone with this key could forge valid login tokens, so never
commit a real one to git (it isn't hardcoded anywhere in this repo -- the
fallback value is clearly labeled as dev-only in `backend/app/auth.py`).

## 1. Run the backend

Open a terminal in VS Code (`` Ctrl+` ``), then:

```bash
cd endotrack-mvp/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

You should see it running at `http://127.0.0.1:8000`. Visit
`http://127.0.0.1:8000/docs` in a browser — FastAPI auto-generates an
interactive API explorer there, useful for testing endpoints without the
frontend.

A file `endotrack.db` (SQLite) will be created automatically in `backend/` on
first run. Delete it any time to reset all data.

## 2. Run the frontend

No build step needed — it's plain HTML/JS. Easiest option in VS Code:

- Install the **Live Server** extension (Extensions panel → search "Live
  Server" by Ritwick Dey → Install).
- Right-click `frontend/index.html` → "Open with Live Server".

Or, without any extension:

```bash
cd endotrack-mvp/frontend
python3 -m http.server 5500
```

then open `http://127.0.0.1:5500` in your browser.

Keep the backend terminal running in parallel — the frontend calls it at
`http://127.0.0.1:8000` (see the `API_BASE` constant at the top of `app.js`
if you ever need to change this).

## 3. Try it

1. Enter an email and password (8+ characters), then click "Create account".
   You'll be logged in automatically.
2. Fill in the patient profile form and click "Create profile" (shown once,
   the first time you log in).
3. Log a few days of symptoms (vary the pain level, mark some as "on
   period", check some flags like bowel symptoms or pain during
   intercourse).
4. Watch the pain timeline chart and risk score update. Click "Refresh
   timeline & risk score" any time.
5. Click "Log out" to test the login flow again with the same account --
   your data and profile will still be there.

Your login session is remembered in the browser (via a token in
localStorage), so refreshing the page keeps you logged in.

The risk score is deliberately **explainable**: every point comes from a
named factor with plain-language reasoning (see `risk_engine.py`). This
matters both for user trust and because a black-box score on a health app is
a much bigger liability than a transparent one.

## Important: this is a screening aid, not a diagnostic tool

The risk engine encodes commonly cited red flags (severe dysmenorrhea, pain
during intercourse, chronic non-menstrual pelvic pain, cyclical bowel/bladder
symptoms, difficulty conceiving, family history) but:

- it has **not** been clinically validated,
- point values and thresholds are a starting draft, not a medical
  instrument, and
- it should be reviewed and adjusted with an actual gynecologist before any
  real users rely on it.

The disclaimer field returned by `/patients/{id}/risk-score` should always be
shown alongside the score in any UI you build on top of this.

## Where to go next (in rough order of effort)

1. **Postgres** — swap `DATABASE_URL` in `backend/app/database.py` from
   SQLite to a Postgres URL (e.g. from Railway or Render) once you need
   multi-user, concurrent access. No other code changes needed.
3. **Cycle-aware analytics** — you already have `CycleEntry`; add an endpoint
   that correlates cycle day with pain to show *where in the cycle* pain
   peaks, which is clinically more useful than a raw timeline.
4. **Mobile app** — wrap this same backend with a Flutter or React Native
   frontend once you want offline logging and push notifications for
   reminders. The API doesn't need to change for this.
5. **SMS reminders (Africa's Talking)** — add a scheduled job that texts
   patients to log symptoms or reminds them of a specialist referral.
6. **Telemedicine referral** — add a `Referral` model + a simple directory of
   gynecologists, and surface a "Book a consultation" action when the risk
   tier is "high".
7. **Anonymized research export** — add an endpoint that strips
   `display_name` and exports aggregated, de-identified symptom data for the
   research-database idea in the original brief. Get an ethics/IRB review
   before doing this with real patient data.
8. **LLM-assisted intake** — once the rules engine is validated, you can let
   users describe symptoms in natural language (including Swahili/Luo/
   Luhya/Kikuyu) and have an LLM map that text onto the same structured
   fields the rules engine already consumes, rather than replacing the
   engine itself.

Each of these is additive — you don't have to rebuild anything above to add
them.
