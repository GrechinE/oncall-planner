"""
Core schedule generation engine.

Algorithm: greedy weighted selection with fairness balancing.
- Iterates week by week through the planning period.
- For each week, scores every eligible person using a cost function that penalises:
    * already having too many shifts (fairness)
    * having a holiday during the week
    * being within the minimum gap since their last PRIMARY shift
    * being on blackout dates
    * not covering the required region
    * exceeding max_shifts_per_year
- Selects primary (lowest cost), then backup (second-lowest, must differ from primary).
- Records violations when no valid candidate is found.

Min-gap enforcement applies only to primary shifts. Backup eligibility uses a
shorter gap (half of min gap) so small regional pools don't run out of candidates.

The engine is intentionally simple so it can later be replaced with OR-Tools
or another solver without changing the surrounding infrastructure.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from .holidays import person_has_holiday_in_week
from .models import (
    Person,
    Schedule,
    ScheduleResult,
    ShiftAssignment,
    TeamConfig,
    Violation,
)

logger = logging.getLogger(__name__)

_BIG = 10_000  # cost sentinel that makes a candidate effectively ineligible


class ScheduleGenerator:
    def __init__(self, team: TeamConfig) -> None:
        self.team = team
        self.config = team.schedule

    def generate(self) -> ScheduleResult:
        shift_starts = self.config.shift_start_dates()
        assignments: list[ShiftAssignment] = []
        violations: list[Violation] = []

        primary_count: dict[str, int] = {p.id: 0 for p in self.team.people}
        # Separate tracking: last primary end vs last any-role end
        last_primary_end: dict[str, Optional[date]] = {p.id: None for p in self.team.people}
        last_any_end: dict[str, Optional[date]] = {p.id: None for p in self.team.people}

        regions = self.config.required_regions or [None]  # type: ignore[list-item]

        for week_start in shift_starts:
            week_end = week_start + timedelta(days=self.config.shift_duration_days - 1)

            # ── Pass 1: assign primaries for all regions ──────────────────────
            # We must know every primary before selecting any backup, so that
            # no person ends up as primary in one region and backup in another.
            assigned_primary_this_week: set[str] = set()
            week_primaries: dict[str, Optional[Person]] = {}   # region -> primary
            week_primary_violations: dict[str, list[Violation]] = {}

            for region in regions:
                primary, viol = self._assign_primary(
                    week_start, week_end, region, primary_count,
                    last_primary_end, assigned_primary_this_week,
                )
                week_primaries[region] = primary
                week_primary_violations[region] = viol
                if primary:
                    primary_count[primary.id] += 1
                    last_primary_end[primary.id] = week_end
                    last_any_end[primary.id] = week_end
                    assigned_primary_this_week.add(primary.id)

            # ── Pass 2: assign backups (skipped when generate_backup=False) ──
            assigned_backup_this_week: set[str] = set()

            for region in regions:
                primary = week_primaries[region]
                violations.extend(week_primary_violations[region])

                if primary is None:
                    assignments.append(ShiftAssignment(
                        week_start=week_start,
                        week_end=week_end,
                        primary_id=None,
                        backup_id=None,
                        region=region,
                    ))
                    continue

                backup: Optional[Person] = None
                if self.config.generate_backup:
                    backup, backup_viol = self._assign_backup(
                        week_start, week_end, region, primary_count, last_any_end,
                        exclude_id=primary.id,
                        assigned_primary_this_week=assigned_primary_this_week,
                        assigned_backup_this_week=assigned_backup_this_week,
                    )
                    violations.extend(backup_viol)
                    if backup:
                        last_any_end[backup.id] = week_end
                        assigned_backup_this_week.add(backup.id)

                assignments.append(ShiftAssignment(
                    week_start=week_start,
                    week_end=week_end,
                    primary_id=primary.id,
                    backup_id=backup.id if backup else None,
                    region=region,
                ))

        schedule = Schedule(config=self.config, assignments=assignments)
        return ScheduleResult(
            schedule=schedule,
            violations=violations,
            fairness=primary_count,
        )

    def _assign_primary(
        self,
        week_start: date,
        week_end: date,
        region: Optional[str],
        primary_count: dict[str, int],
        last_primary_end: dict[str, Optional[date]],
        assigned_primary_this_week: set[str],
    ) -> tuple[Optional[Person], list[Violation]]:
        violations: list[Violation] = []

        primary_eligible = self._eligible_for_primary(
            week_start, week_end, region, last_primary_end, assigned_primary_this_week
        )
        if not primary_eligible:
            violations.append(Violation(
                week_start=week_start,
                severity="error",
                code="NO_PRIMARY_CANDIDATE",
                message=(
                    f"No eligible primary for week {week_start} "
                    f"(region={region}). Check gap constraints and blackouts."
                ),
            ))
            return None, violations

        scored = sorted(primary_eligible, key=lambda p: self._score(
            p, week_start, week_end, primary_count, last_primary_end
        ))
        return scored[0], violations

    def _assign_backup(
        self,
        week_start: date,
        week_end: date,
        region: Optional[str],
        primary_count: dict[str, int],
        last_any_end: dict[str, Optional[date]],
        exclude_id: str,
        assigned_primary_this_week: set[str],
        assigned_backup_this_week: set[str],
    ) -> tuple[Optional[Person], list[Violation]]:
        violations: list[Violation] = []

        backup_eligible = self._eligible_for_backup(
            week_start, week_end, region, last_any_end,
            exclude_id=exclude_id,
            assigned_primary_this_week=assigned_primary_this_week,
            assigned_backup_this_week=assigned_backup_this_week,
        )
        if not backup_eligible:
            violations.append(Violation(
                week_start=week_start,
                severity="warning",
                code="NO_BACKUP_CANDIDATE",
                message=(
                    f"No eligible backup for week {week_start} "
                    f"(region={region}). Only one person available."
                ),
            ))
            return None, violations

        backup_scored = sorted(backup_eligible, key=lambda p: self._score(
            p, week_start, week_end, primary_count, {}
        ))
        return backup_scored[0], violations

    def _eligible_for_primary(
        self,
        week_start: date,
        week_end: date,
        region: Optional[str],
        last_primary_end: dict[str, Optional[date]],
        already_primary: set[str],
    ) -> list[Person]:
        candidates = []
        min_gap = timedelta(weeks=self.config.min_gap_between_shifts_weeks)
        for person in self.team.people:
            if person.id in already_primary:
                continue
            if region and not person.can_cover_region(region):
                continue
            if self._has_blackout(person, week_start):
                continue
            last = last_primary_end.get(person.id)
            if last is not None and (week_start - last) < min_gap:
                continue
            candidates.append(person)
        # Prefer people with no national holiday this week.
        # Fall back to the full candidate list only if everyone has a holiday
        # (avoids NO_PRIMARY_CANDIDATE on heavily-observed holiday weeks).
        without_holiday = [
            p for p in candidates
            if not person_has_holiday_in_week(p.country, week_start, week_end)
        ]
        return without_holiday if without_holiday else candidates

    def _eligible_for_backup(
        self,
        week_start: date,
        week_end: date,
        region: Optional[str],
        last_any_end: dict[str, Optional[date]],
        exclude_id: str,
        assigned_primary_this_week: set[str],
        assigned_backup_this_week: set[str],
    ) -> list[Person]:
        candidates = []
        # Backup gap = half of primary gap (minimum 1 week)
        backup_gap_weeks = max(1, self.config.min_gap_between_shifts_weeks // 2)
        backup_gap = timedelta(weeks=backup_gap_weeks)
        for person in self.team.people:
            if person.id == exclude_id:
                continue
            if person.id in assigned_primary_this_week:
                continue
            if person.id in assigned_backup_this_week:
                continue
            if region and not person.can_cover_region(region):
                continue
            if self._has_blackout(person, week_start):
                continue
            last = last_any_end.get(person.id)
            if last is not None and (week_start - last) < backup_gap:
                continue
            candidates.append(person)
        without_holiday = [
            p for p in candidates
            if not person_has_holiday_in_week(p.country, week_start, week_end)
        ]
        return without_holiday if without_holiday else candidates

    def _has_blackout(self, person: Person, week_start: date) -> bool:
        return any(
            not person.is_available_on(week_start + timedelta(days=i))
            for i in range(self.config.shift_duration_days)
        )

    def _score(
        self,
        person: Person,
        week_start: date,
        week_end: date,
        primary_count: dict[str, int],
        last_primary_end: dict[str, Optional[date]],
    ) -> float:
        score = 0.0

        # Fairness: prefer people with fewer primary shifts
        score += primary_count[person.id] * 10


        # Max shifts cap — soft block
        if person.max_shifts_per_year is not None:
            if primary_count[person.id] >= person.max_shifts_per_year:
                score += _BIG

        # Recency: slightly prefer people whose last primary shift was longer ago
        last = last_primary_end.get(person.id)
        if last is not None:
            weeks_since = (week_start - last).days / 7
            score += max(0, 10 - weeks_since)

        return score
