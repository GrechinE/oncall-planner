from src.scheduler.generator import ScheduleGenerator
from src.scheduler.fairness import compute_fairness


def test_fairness_expected_uses_calendar_weeks_not_assignment_rows(multi_region_team):
    """For a 3-region team, expected_primary must equal calendar_weeks/n_people,
    NOT assignment_rows/n_people (which would be 3x too high)."""
    result = ScheduleGenerator(multi_region_team).generate()
    rows = compute_fairness(result, multi_region_team)

    assignments = result.schedule.assignments
    unique_weeks = len({a.week_start for a in assignments})
    n_people = len(multi_region_team.people)
    expected_correct = round(unique_weeks / n_people, 2)

    for r in rows:
        assert r.expected_primary == expected_correct, (
            f"{r.name}: expected_primary={r.expected_primary}, should be {expected_correct}"
        )


def test_fairness_no_person_starved(simple_team):
    generator = ScheduleGenerator(simple_team)
    result = generator.generate()
    rows = compute_fairness(result, simple_team)

    # Everyone should have at least 1 primary shift in a 13-week period with 4 people
    for r in rows:
        assert r.primary_shifts > 0, f"{r.name} has 0 primary shifts"


def test_fairness_max_deviation_reasonable(simple_team):
    generator = ScheduleGenerator(simple_team)
    result = generator.generate()
    rows = compute_fairness(result, simple_team)

    max_dev = max(abs(r.deviation) for r in rows)
    # With 4 people and 13 weeks, max deviation should be well under 4
    assert max_dev <= 4, f"Max deviation {max_dev} too high"


def test_fairness_total_sums_to_assignments(simple_team):
    generator = ScheduleGenerator(simple_team)
    result = generator.generate()
    rows = compute_fairness(result, simple_team)

    total_primary = sum(r.primary_shifts for r in rows)
    expected = len(result.schedule.assignments)
    # Every assignment has exactly 1 primary (or 0 if unassigned)
    assigned = sum(1 for a in result.schedule.assignments if a.primary_id)
    assert total_primary == assigned
