# OnCall Planner — CLAUDE.md

## What this project is
A global on-call scheduling tool being built as a Streamlit MVP + Python engine.
Target users: engineering teams across multiple countries/regions.
Deployed on Streamlit Cloud (branch: `main`).
GitHub: https://github.com/GrechinE/oncall-planner

## Tech stack
- Python 3.14 (Streamlit Cloud runtime)
- Streamlit ≥ 1.35 — UI, all tabs in `src/ui/app.py`
- Pydantic v2 — all domain models
- `holidays==0.98` — offline public holiday data (60+ countries)
- Nager.Date API — fallback for countries not in `holidays` lib
- pytest + pytest-cov — 53 tests under `tests/`
- Themes: `src/ui/themes.py` — `default` (Streamlit dark) or `philips` (blue corporate); select via `?theme=philips` URL param or `ONCALL_THEME` env var

## Project layout
```
src/
  scheduler/
    models.py       # Pydantic domain models (Person, ScheduleConfig, Schedule, etc.)
    generator.py    # ScheduleGenerator class — core scheduling logic
    holidays.py     # Holiday fetching (lib + Nager fallback, eve logic for IL etc.)
    fairness.py     # Fairness scoring
    validator.py    # Schedule validation, Violation objects
    exporter.py     # Excel/CSV export
    loader.py       # CSV/JSON team config loader
    main.py         # CLI entry point
  ui/
    app.py          # Single-file Streamlit app — all tabs
    themes.py       # CSS injection for Philips theme
tests/
  test_models.py
  test_holidays.py
  conftest.py
```

## Core domain models (models.py)
- `Person` — id, name, country (ISO 3166-1 α2), timezone (IANA), regions[], skills[], blackout_dates[], max_shifts_per_year
- `ScheduleConfig` — start_date, end_date, shift_duration_days (default 7), shift_start_day (sunday|monday), min_gap_between_shifts_weeks (default 4), required_regions[], required_skills[], generate_backup
- `ShiftAssignment` — week_start, week_end, primary_id, backup_id, region, notes
- `Schedule` — config + assignments[]
- `TeamConfig` — schedule config + people[]
- `ScheduleResult` — schedule + violations[] + fairness dict

## Holiday logic (holidays.py)
- `get_public_holidays_with_names(country, year)` — canonical function; uses module-level `_holiday_cache` keyed `(country, year, _CACHE_VERSION)`
- `get_public_holidays(country, year)` — returns frozenset of dates
- `_COUNTRIES_WITH_HOLIDAY_EVES = {"IL"}` — countries where day-before holiday is also non-working; eve logic auto-applied inside `get_public_holidays_with_names`
- `_CACHE_VERSION = 2` — bump when holiday logic changes to bust in-process cache
- **Streamlit Cloud gotcha**: `@st.cache_data` persists to disk across deploys. Bust it by changing the `_v` salt param on `_cached_holidays` in app.py. Current value: `_v=3`
- **Streamlit Cloud gotcha**: Module bytecode may be cached — critical logic that must survive a deploy should live inline in app.py, not only in holidays.py. Holiday eve logic is currently duplicated inline in app.py (Fetch Holidays button ~line 691, Team Summary ~line 722) for this reason.

## Known Streamlit Cloud pitfalls
- Never import private names (`_symbol`) from library modules inside a button handler — runs at page-load time, crashes if Cloud has old bytecode
- Only use top-level imports already at the top of app.py inside handlers

## Running tests
```bash
cd C:\DEV\oncall-planner
python -m pytest tests/ -v
```
All 53 tests must pass before committing.

## Regional on-call patterns documented so far

### France (FR) — `Astreinte FR 24x7`
- **Granularity**: daily (one person per day)
- **Slots**: 1 per day, no morning/afternoon split
- **Pool size**: ~17 engineers
- **Coverage**: true 24x7 including weekends and public holidays
- **Holiday handling**: on-call persists; rest of team marked off (Fête travail, 08-Mai-45, Ascension, RTT Imposé)
- **Language constraint**: none visible
- **Role tags in phone directory**: SUPPORT, TC, SD (escalation tiers, not rotation pools)

### EMEA L1/L2
- **Granularity**: daily
- **Slots**: multiple per day — morning/afternoon splits, language-restricted sub-pools
- **Language constraints**: IIG Italian-only, Iberia Spanish-only, FR Telemedicine French-only
- **Pool size**: 15+ distinct pools
- **Coverage**: 24x7

### Nordic Technical Team
- **Granularity**: weekly TRIAGE rotation embedded in a team availability calendar
- **Tracked states**: SICK / TRAINING / NOT AVAILABLE / On site / Holiday
- **Pool size**: ~8–10 engineers
- **Coverage**: weekday-focused

### UK Duty Manager
- **Granularity**: weekly rotation
- **Slots**: 1 duty manager per week
- **Pool size**: 10 managers
- **Coverage**: includes key contacts / escalation directory

## Product direction (confirmed)
Focus on on-call **generation** with constraints — planner that accommodates different countries/regions' ways of working (daily vs weekly granularity, single vs multi-pool, language/skill constraints, holiday-aware fairness). Not a generic calendar tool.

## Cost-effective working conventions
- Reference files as `path:line` (e.g. `holidays.py:61`) — skip exploration
- Batch related changes into one request
- Say "just do it" for low-risk changes to skip confirmation round-trips
- Paste only relevant CSV rows, not full files with static phone directories
