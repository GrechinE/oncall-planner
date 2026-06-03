from datetime import date
import pytest
from src.scheduler.models import (
    Person, ScheduleConfig, ShiftStartDay, TeamConfig, ScheduleResult, Schedule
)


def test_person_country_uppercased():
    p = Person(id="x", name="X", country="us", timezone="UTC", regions=[], skills=[])
    assert p.country == "US"


def test_person_blackout_dates_parsed_from_strings():
    p = Person(
        id="x", name="X", country="US", timezone="UTC",
        regions=[], skills=[],
        blackout_dates=["2026-07-04", "2026-12-25"],
    )
    assert date(2026, 7, 4) in p.blackout_dates
    assert p.is_available_on(date(2026, 7, 3))
    assert not p.is_available_on(date(2026, 7, 4))


def test_person_region_and_skill_checks():
    p = Person(id="x", name="X", country="US", timezone="UTC",
               regions=["americas", "emea"], skills=["product-a"])
    assert p.can_cover_region("americas")
    assert not p.can_cover_region("apac")
    assert p.has_skill("product-a")
    assert not p.has_skill("product-z")


def test_schedule_config_shift_starts_sunday():
    config = ScheduleConfig(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 28),
        shift_start_day=ShiftStartDay.sunday,
    )
    starts = config.shift_start_dates()
    for s in starts:
        assert s.weekday() == 6, f"{s} is not a Sunday"


def test_schedule_config_shift_starts_monday():
    config = ScheduleConfig(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 28),
        shift_start_day=ShiftStartDay.monday,
    )
    starts = config.shift_start_dates()
    for s in starts:
        assert s.weekday() == 0, f"{s} is not a Monday"


def test_schedule_config_end_before_start_raises():
    with pytest.raises(Exception):
        ScheduleConfig(start_date=date(2026, 6, 1), end_date=date(2026, 1, 1))


def test_team_config_duplicate_ids_raises():
    config = ScheduleConfig(
        start_date=date(2026, 1, 1), end_date=date(2026, 3, 31)
    )
    p1 = Person(id="dup", name="A", country="US", timezone="UTC", regions=[], skills=[])
    p2 = Person(id="dup", name="B", country="GB", timezone="UTC", regions=[], skills=[])
    with pytest.raises(Exception):
        TeamConfig(schedule=config, people=[p1, p2])


def test_schedule_result_has_errors_flag():
    from src.scheduler.models import Violation
    from datetime import date
    v = Violation(week_start=date(2026,1,1), severity="error", code="TEST", message="test")
    # ScheduleResult needs a schedule — build minimal one
    config = ScheduleConfig(start_date=date(2026,1,1), end_date=date(2026,3,31))
    schedule = Schedule(config=config, assignments=[])
    result = ScheduleResult(schedule=schedule, violations=[v])
    assert result.has_errors
    result2 = ScheduleResult(schedule=schedule, violations=[])
    assert not result2.has_errors
