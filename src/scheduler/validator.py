"""
Post-generation constraint validation.
Runs over a completed ScheduleResult and appends any violations not already caught
by the generator (which only catches eligibility failures during generation).
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from .holidays import person_has_holiday_in_week
from .models import Violation

if TYPE_CHECKING:
    from .models import ScheduleResult, TeamConfig


def validate(result: "ScheduleResult", team: "TeamConfig") -> list[Violation]:
    """Return a (possibly empty) list of post-hoc violations."""
    violations: list[Violation] = list(result.violations)  # start from generator violations
    config = team.schedule

    person_map = {p.id: p for p in team.people}
    assignments = result.schedule.assignments

    # Build last-seen dict for gap checks
    last_end: dict[str, object] = {}

    for i, assignment in enumerate(assignments):
        week_start = assignment.week_start
        week_end = assignment.week_end

        # --- Primary must be set ---
        if assignment.primary_id is None:
            # Already recorded by generator; skip duplicate
            pass

        # --- Primary == Backup ---
        if (
            assignment.primary_id
            and assignment.backup_id
            and assignment.primary_id == assignment.backup_id
        ):
            violations.append(Violation(
                week_start=week_start,
                severity="error",
                code="PRIMARY_EQUALS_BACKUP",
                message=(
                    f"Week {week_start}: primary and backup are the same person "
                    f"({assignment.primary_id})"
                ),
            ))

        for role, pid in [("primary", assignment.primary_id), ("backup", assignment.backup_id)]:
            if pid is None:
                continue
            person = person_map.get(pid)
            if person is None:
                violations.append(Violation(
                    week_start=week_start,
                    severity="error",
                    code="UNKNOWN_PERSON",
                    message=f"Week {week_start}: {role} person '{pid}' not in team",
                ))
                continue

            # --- Blackout dates ---
            for d_offset in range(config.shift_duration_days):
                d = week_start + timedelta(days=d_offset)
                if not person.is_available_on(d):
                    violations.append(Violation(
                        week_start=week_start,
                        severity="error",
                        code="BLACKOUT_VIOLATION",
                        message=(
                            f"Week {week_start}: {role} {person.name} has blackout on {d}"
                        ),
                    ))

            # --- National holiday on duty (warning only) ---
            if person_has_holiday_in_week(person.country, week_start, week_end):
                violations.append(Violation(
                    week_start=week_start,
                    severity="warning",
                    code="HOLIDAY_ON_DUTY",
                    message=(
                        f"Week {week_start}: {role} {person.name} ({person.country}) "
                        f"has a national holiday during this week"
                    ),
                ))

            # --- Region coverage ---
            if assignment.region and not person.can_cover_region(assignment.region):
                violations.append(Violation(
                    week_start=week_start,
                    severity="error",
                    code="REGION_MISMATCH",
                    message=(
                        f"Week {week_start}: {role} {person.name} cannot cover "
                        f"region '{assignment.region}'"
                    ),
                ))

            # --- Max shifts per year ---
            if role == "primary" and person.max_shifts_per_year is not None:
                count = result.fairness.get(pid, 0)
                if count > person.max_shifts_per_year:
                    violations.append(Violation(
                        week_start=week_start,
                        severity="warning",
                        code="MAX_SHIFTS_EXCEEDED",
                        message=(
                            f"{person.name} has {count} primary shifts, "
                            f"exceeds max {person.max_shifts_per_year}"
                        ),
                    ))

        # --- Minimum gap between primary shifts only ---
        min_gap = timedelta(weeks=config.min_gap_between_shifts_weeks)
        pid = assignment.primary_id
        if pid is not None:
            last = last_end.get(pid)
            if last is not None and (week_start - last) < min_gap:  # type: ignore[operator]
                violations.append(Violation(
                    week_start=week_start,
                    severity="warning",
                    code="GAP_TOO_SHORT",
                    message=(
                        f"Week {week_start}: {pid} last primary shift ended {last}, "
                        f"gap is less than {config.min_gap_between_shifts_weeks} weeks"
                    ),
                ))

        # track primary shifts only for gap validation
        if assignment.primary_id:
            last_end[assignment.primary_id] = week_end

    return violations


def violations_summary_text(violations: list[Violation]) -> str:
    if not violations:
        return "No violations found. Schedule looks clean!"
    errors = [v for v in violations if v.severity == "error"]
    warnings = [v for v in violations if v.severity == "warning"]
    lines = [f"Total violations: {len(violations)}  ({len(errors)} errors, {len(warnings)} warnings)", ""]
    if errors:
        lines.append("ERRORS:")
        for v in errors:
            lines.append(f"  [{v.code}] {v.message}")
        lines.append("")
    if warnings:
        lines.append("WARNINGS:")
        for v in warnings:
            lines.append(f"  [{v.code}] {v.message}")
    return "\n".join(lines)
