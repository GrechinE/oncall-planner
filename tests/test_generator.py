from datetime import date, timedelta
import pytest
from src.scheduler.generator import ScheduleGenerator
from src.scheduler.models import Person, ScheduleConfig, ShiftStartDay, TeamConfig


def _make_multi_region_team_small():
    """3 regions, 2 people per region — enough to hit the backup-dedup path."""
    config = ScheduleConfig(
        start_date=date(2026, 1, 4),
        end_date=date(2026, 3, 1),
        shift_duration_days=7,
        shift_start_day=ShiftStartDay.sunday,
        min_gap_between_shifts_weeks=2,
        required_regions=["americas", "emea", "apac"],
    )
    people = [
        Person(id="a1", name="Alice", country="US", timezone="America/New_York", regions=["americas"], skills=[]),
        Person(id="a2", name="Bob",   country="US", timezone="America/Chicago",  regions=["americas"], skills=[]),
        Person(id="e1", name="Carol", country="GB", timezone="Europe/London",    regions=["emea"],     skills=[]),
        Person(id="e2", name="Dave",  country="IL", timezone="Asia/Jerusalem",   regions=["emea"],     skills=[]),
        Person(id="p1", name="Priya", country="IN", timezone="Asia/Kolkata",     regions=["apac"],     skills=[]),
        Person(id="p2", name="Akira", country="JP", timezone="Asia/Tokyo",       regions=["apac"],     skills=[]),
    ]
    return TeamConfig(schedule=config, people=people)


def test_generate_covers_all_weeks(simple_team):
    generator = ScheduleGenerator(simple_team)
    result = generator.generate()
    expected_weeks = len(simple_team.schedule.shift_start_dates())
    assert len(result.schedule.assignments) == expected_weeks


def test_generate_multi_region_coverage(multi_region_team):
    generator = ScheduleGenerator(multi_region_team)
    result = generator.generate()
    # Each week should have 3 assignments (one per region)
    weeks = {a.week_start for a in result.schedule.assignments}
    for week in weeks:
        week_assignments = [a for a in result.schedule.assignments if a.week_start == week]
        regions_covered = {a.region for a in week_assignments}
        assert "americas" in regions_covered
        assert "emea" in regions_covered
        assert "apac" in regions_covered


def test_generate_primary_and_backup_differ(simple_team):
    generator = ScheduleGenerator(simple_team)
    result = generator.generate()
    for a in result.schedule.assignments:
        if a.primary_id and a.backup_id:
            assert a.primary_id != a.backup_id


def test_generate_respects_blackout(simple_team):
    # Add a blackout for the first week to alice
    first_week = simple_team.schedule.shift_start_dates()[0]
    blackout_day = first_week + timedelta(days=0)
    # rebuild alice with the blackout
    alice = next(p for p in simple_team.people if p.id == "alice")
    alice_with_blackout = alice.model_copy(update={"blackout_dates": [blackout_day]})
    new_people = [alice_with_blackout if p.id == "alice" else p for p in simple_team.people]
    team = simple_team.model_copy(update={"people": new_people})

    generator = ScheduleGenerator(team)
    result = generator.generate()

    # alice should not be primary in the first week
    first_assignment = result.schedule.assignments[0]
    assert first_assignment.primary_id != "alice"
    assert first_assignment.backup_id != "alice"


def test_generate_min_gap_respected(simple_team):
    """Min gap only applies to consecutive PRIMARY shifts for the same person."""
    generator = ScheduleGenerator(simple_team)
    result = generator.generate()
    min_gap = timedelta(weeks=simple_team.schedule.min_gap_between_shifts_weeks)

    last_primary_end: dict = {}
    for a in result.schedule.assignments:
        pid = a.primary_id
        if pid is None:
            continue
        last = last_primary_end.get(pid)
        if last is not None:
            gap = a.week_start - last
            assert gap >= min_gap, (
                f"{pid}: primary gap of {gap.days}d is less than min {min_gap.days}d "
                f"(shift starting {a.week_start}, previous ended {last})"
            )
        last_primary_end[pid] = a.week_end


def test_generate_full_year_sample():
    """Integration: generate the full 2026 schedule from the sample dataset."""
    import json
    from pathlib import Path
    from src.scheduler.loader import load_from_json
    from src.scheduler.validator import validate

    sample = Path(__file__).parent.parent / "data" / "samples" / "team_config.json"
    team = load_from_json(sample)
    generator = ScheduleGenerator(team)
    result = generator.generate()
    result.violations = validate(result, team)

    # Should have generated assignments
    assert len(result.schedule.assignments) > 0
    # No NO_PRIMARY_CANDIDATE errors expected with 8-person team
    errors = [v for v in result.violations if v.code == "NO_PRIMARY_CANDIDATE"]
    assert len(errors) == 0, f"Unexpected unassigned weeks: {errors}"


def test_no_person_backup_in_two_regions_same_week():
    """SE-001: a person must not be backup in more than one region per week."""
    team = _make_multi_region_team_small()
    result = ScheduleGenerator(team).generate()

    for week_start in {a.week_start for a in result.schedule.assignments}:
        week_assignments = [a for a in result.schedule.assignments if a.week_start == week_start]
        backup_ids = [a.backup_id for a in week_assignments if a.backup_id]
        assert len(backup_ids) == len(set(backup_ids)), (
            f"Week {week_start}: same person assigned backup in multiple regions: {backup_ids}"
        )


def test_no_person_primary_and_backup_same_week():
    """A person must not be primary in one region and backup in another same week."""
    team = _make_multi_region_team_small()
    result = ScheduleGenerator(team).generate()

    for week_start in {a.week_start for a in result.schedule.assignments}:
        week_assignments = [a for a in result.schedule.assignments if a.week_start == week_start]
        primaries = {a.primary_id for a in week_assignments if a.primary_id}
        backups = {a.backup_id for a in week_assignments if a.backup_id}
        overlap = primaries & backups
        assert not overlap, (
            f"Week {week_start}: {overlap} assigned as both primary and backup"
        )
