# OnCall Planner

Fair, holiday-aware on-call scheduling for any global team — engineering, ops, support, and more.

The missing planning layer before PagerDuty/Opsgenie: generate a constraint-valid, balanced schedule, export to Excel or CSV, then paste into your alerting tool.

---

## Quick Start

### 1. Install dependencies

```bash
cd oncall-planner
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Run the Streamlit UI

```bash
streamlit run src/ui/app.py
```

Opens at http://localhost:8501

### 3. Run the scheduler from CLI

```bash
python -m src.scheduler.main --config data/samples/team_config.json
```

### 4. Run tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
oncall-planner/
├── src/
│   ├── scheduler/
│   │   ├── models.py          # Domain models (Person, Shift, Schedule)
│   │   ├── holidays.py        # Holiday fetching (holidays lib + Nager.Date fallback)
│   │   ├── generator.py       # Core schedule generation engine
│   │   ├── fairness.py        # Fairness scoring and balancing
│   │   ├── validator.py       # Constraint validation and violation reporting
│   │   ├── exporter.py        # Excel/CSV export
│   │   └── main.py            # CLI entry point
│   ├── ui/
│   │   └── app.py             # Streamlit UI
│   └── api/                   # FastAPI backend (future)
├── tests/
│   ├── test_models.py
│   ├── test_holidays.py
│   ├── test_generator.py
│   ├── test_fairness.py
│   └── test_validator.py
├── data/
│   └── samples/
│       ├── team_config.json   # Sample team configuration
│       └── team_config.csv    # Same data in CSV format
├── requirements.txt
└── README.md
```

---

## Input Format

### JSON (team_config.json)

```json
{
  "schedule": {
    "start_date": "2026-01-01",
    "end_date": "2026-12-31",
    "shift_duration_days": 7,
    "shift_start_day": "sunday",
    "min_gap_between_shifts_weeks": 4
  },
  "people": [
    {
      "id": "alice",
      "name": "Alice Smith",
      "country": "US",
      "timezone": "America/New_York",
      "regions": ["americas", "emea"],
      "skills": ["product-a", "product-b"],
      "blackout_dates": ["2026-07-04", "2026-07-05"],
      "max_shifts_per_year": 10
    }
  ]
}
```

### CSV (team_config.csv)

```csv
id,name,country,timezone,regions,skills,blackout_dates,max_shifts_per_year
alice,Alice Smith,US,America/New_York,"americas,emea","product-a,product-b","2026-07-04,2026-07-05",10
```

---

## Output

- **schedule.xlsx** — one row per week, primary + backup columns, holiday indicators
- **schedule.csv** — same in CSV
- **fairness_report.txt** — shift count per person, deviation from average
- **violations.txt** — any constraints that could not be satisfied

---

## Roadmap

- [x] MVP scheduler engine
- [x] Streamlit UI
- [x] Excel/CSV export (Schedule + Fairness + Violations sheets)
- [x] Holiday-aware scheduling (60+ countries, offline)
- [x] Backup on-call generation (on demand)
- [x] CSV team import
- [ ] iCal / .ics export
- [ ] Shift swap requests
- [ ] FastAPI backend
- [ ] React frontend (SaaS)
- [ ] PagerDuty/Opsgenie write-back
- [ ] Multi-tenant accounts
