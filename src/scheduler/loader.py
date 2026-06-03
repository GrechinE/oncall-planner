"""
Load TeamConfig from JSON or CSV input files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import Person, ScheduleConfig, TeamConfig


def load_from_json(path: str | Path) -> TeamConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return TeamConfig.model_validate(data)


def load_from_csv(
    people_csv: str | Path,
    schedule_json: str | Path,
) -> TeamConfig:
    """Load people from CSV and schedule config from a separate JSON file."""
    df = pd.read_csv(people_csv, dtype=str).fillna("")

    people = []
    for _, row in df.iterrows():
        regions = [r.strip() for r in row.get("regions", "").split(",") if r.strip()]
        skills = [s.strip() for s in row.get("skills", "").split(",") if s.strip()]
        blackouts = [
            b.strip()
            for b in row.get("blackout_dates", "").split(",")
            if b.strip()
        ]
        max_shifts_raw = row.get("max_shifts_per_year", "")
        max_shifts = int(max_shifts_raw) if max_shifts_raw.isdigit() else None

        people.append(Person(
            id=row["id"],
            name=row["name"],
            country=row["country"],
            timezone=row["timezone"],
            regions=regions,
            skills=skills,
            blackout_dates=blackouts,
            max_shifts_per_year=max_shifts,
        ))

    schedule_data = json.loads(Path(schedule_json).read_text(encoding="utf-8"))
    schedule_config = ScheduleConfig.model_validate(schedule_data)

    return TeamConfig(schedule=schedule_config, people=people)
