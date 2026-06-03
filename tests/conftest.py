"""Shared fixtures for all tests."""
import sys
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import date

from src.scheduler.models import Person, ScheduleConfig, ShiftStartDay, TeamConfig


@pytest.fixture
def simple_team():
    """A minimal 4-person global team covering a single region."""
    config = ScheduleConfig(
        start_date=date(2026, 1, 4),   # first Sunday of 2026
        end_date=date(2026, 3, 29),
        shift_duration_days=7,
        shift_start_day=ShiftStartDay.sunday,
        min_gap_between_shifts_weeks=2,
        required_regions=[],
    )
    people = [
        Person(id="alice", name="Alice Smith", country="US", timezone="America/New_York",
               regions=["americas"], skills=["product-a"]),
        Person(id="bob", name="Bob Jones", country="GB", timezone="Europe/London",
               regions=["emea"], skills=["product-a"]),
        Person(id="carol", name="Carol Levi", country="IL", timezone="Asia/Jerusalem",
               regions=["emea"], skills=["product-b"]),
        Person(id="dave", name="Dave Kumar", country="IN", timezone="Asia/Kolkata",
               regions=["apac"], skills=["product-a"]),
    ]
    return TeamConfig(schedule=config, people=people)


@pytest.fixture
def multi_region_team():
    """A team with 3 explicit regions — americas, emea, apac."""
    config = ScheduleConfig(
        start_date=date(2026, 1, 4),
        end_date=date(2026, 3, 29),
        shift_duration_days=7,
        shift_start_day=ShiftStartDay.sunday,
        min_gap_between_shifts_weeks=2,
        required_regions=["americas", "emea", "apac"],
    )
    people = [
        Person(id="alice", name="Alice Smith", country="US", timezone="America/New_York",
               regions=["americas"], skills=["product-a"]),
        Person(id="bob", name="Bob Jones", country="US", timezone="America/Chicago",
               regions=["americas"], skills=["product-a"]),
        Person(id="carol", name="Carol Levi", country="IL", timezone="Asia/Jerusalem",
               regions=["emea"], skills=["product-b"]),
        Person(id="james", name="James Okafor", country="GB", timezone="Europe/London",
               regions=["emea"], skills=["product-a"]),
        Person(id="priya", name="Priya Sharma", country="IN", timezone="Asia/Kolkata",
               regions=["apac"], skills=["product-a"]),
        Person(id="akira", name="Akira Tanaka", country="JP", timezone="Asia/Tokyo",
               regions=["apac"], skills=["product-a"]),
    ]
    return TeamConfig(schedule=config, people=people)
