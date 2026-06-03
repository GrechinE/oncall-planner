"""
Fairness analysis for a generated schedule.
Computes per-person shift counts, expected distribution, and deviation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ScheduleResult, TeamConfig


@dataclass
class PersonFairnessRow:
    person_id: str
    name: str
    country: str
    primary_shifts: int
    backup_shifts: int
    total_shifts: int
    expected_primary: float     # ideal equal share
    deviation: float            # actual - expected (positive = over-scheduled)
    holiday_weeks: int          # weeks where person had a holiday


def compute_fairness(result: "ScheduleResult", team: "TeamConfig") -> list[PersonFairnessRow]:
    """Build a fairness report for every person in the team."""
    assignments = result.schedule.assignments
    n_people = len(team.people)
    # For multi-region schedules each calendar week produces N assignment rows (one per
    # region). Use unique calendar weeks so that expected = calendar_weeks / people.
    unique_weeks = len({a.week_start for a in assignments})
    expected = unique_weeks / n_people if n_people else 0

    rows = []
    for person in team.people:
        primary = sum(1 for a in assignments if a.primary_id == person.id)
        backup = sum(1 for a in assignments if a.backup_id == person.id)
        total = primary + backup

        # Count weeks the person had a national holiday
        from .holidays import person_has_holiday_in_week
        holiday_weeks = sum(
            1 for a in assignments
            if person_has_holiday_in_week(person.country, a.week_start, a.week_end)
        )

        rows.append(PersonFairnessRow(
            person_id=person.id,
            name=person.name,
            country=person.country,
            primary_shifts=primary,
            backup_shifts=backup,
            total_shifts=total,
            expected_primary=round(expected, 2),
            deviation=round(primary - expected, 2),
            holiday_weeks=holiday_weeks,
        ))

    rows.sort(key=lambda r: r.primary_shifts, reverse=True)
    return rows


def fairness_summary_text(rows: list[PersonFairnessRow]) -> str:
    lines = [
        f"{'Name':<22} {'Country':<8} {'Primary':>8} {'Backup':>7} "
        f"{'Expected':>9} {'Deviation':>10} {'HolWks':>7}",
        "-" * 75,
    ]
    for r in rows:
        marker = " *" if abs(r.deviation) > 2 else "  "
        lines.append(
            f"{r.name:<22} {r.country:<8} {r.primary_shifts:>8} {r.backup_shifts:>7} "
            f"{r.expected_primary:>9.1f} {r.deviation:>+10.1f} {r.holiday_weeks:>7}{marker}"
        )
    lines.append("")
    lines.append("* = deviation > 2 shifts from expected")
    return "\n".join(lines)
