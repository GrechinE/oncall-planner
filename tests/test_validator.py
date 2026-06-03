from datetime import date, timedelta
from src.scheduler.generator import ScheduleGenerator
from src.scheduler.validator import validate


def test_validate_clean_schedule(simple_team):
    generator = ScheduleGenerator(simple_team)
    result = generator.generate()
    violations = validate(result, simple_team)
    errors = [v for v in violations if v.severity == "error"]
    assert len(errors) == 0, f"Unexpected errors: {errors}"


def test_validate_detects_blackout_violation(simple_team):
    """Manually inject an assignment that violates a blackout."""
    from src.scheduler.models import ShiftAssignment, Violation

    first_week = simple_team.schedule.shift_start_dates()[0]
    alice = next(p for p in simple_team.people if p.id == "alice")
    alice_with_blackout = alice.model_copy(update={"blackout_dates": [first_week]})
    new_people = [alice_with_blackout if p.id == "alice" else p for p in simple_team.people]
    team = simple_team.model_copy(update={"people": new_people})

    # Generate normally — alice won't be assigned first week
    generator = ScheduleGenerator(team)
    result = generator.generate()

    # Force alice into primary of week 1
    result.schedule.assignments[0] = ShiftAssignment(
        week_start=first_week,
        week_end=first_week + timedelta(days=6),
        primary_id="alice",
        backup_id="bob",
    )
    # reset violations from generator
    result.violations = []

    violations = validate(result, team)
    blackout_violations = [v for v in violations if v.code == "BLACKOUT_VIOLATION"]
    assert len(blackout_violations) >= 1


def test_validate_detects_primary_equals_backup(simple_team):
    from src.scheduler.models import ShiftAssignment
    first_week = simple_team.schedule.shift_start_dates()[0]
    result_copy = ScheduleGenerator(simple_team).generate()
    result_copy.schedule.assignments[0] = ShiftAssignment(
        week_start=first_week,
        week_end=first_week + timedelta(days=6),
        primary_id="alice",
        backup_id="alice",  # same!
    )
    result_copy.violations = []
    violations = validate(result_copy, simple_team)
    assert any(v.code == "PRIMARY_EQUALS_BACKUP" for v in violations)


def test_validate_full_year_has_no_critical_errors():
    """Regression: full-year sample should produce 0 NO_PRIMARY_CANDIDATE errors."""
    from pathlib import Path
    from src.scheduler.loader import load_from_json
    sample = Path(__file__).parent.parent / "data" / "samples" / "team_config.json"
    team = load_from_json(sample)
    result = ScheduleGenerator(team).generate()
    result.violations = validate(result, team)
    critical = [v for v in result.violations if v.code == "NO_PRIMARY_CANDIDATE"]
    assert len(critical) == 0
