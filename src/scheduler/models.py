"""
Domain models for the OnCall Planner.
All business objects are Pydantic models for validation and serialisation.
"""

from __future__ import annotations

from datetime import date, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class ShiftStartDay(str, Enum):
    sunday = "sunday"
    monday = "monday"


class Person(BaseModel):
    id: str
    name: str
    country: str                        # ISO 3166-1 alpha-2, e.g. "US", "IL", "IN"
    timezone: str                       # IANA tz, e.g. "America/New_York"
    regions: list[str]                  # regions this person can cover, e.g. ["americas", "emea"]
    skills: list[str]                   # product/skill tags, e.g. ["product-a"]
    blackout_dates: list[date] = []     # dates person is unavailable
    max_shifts_per_year: Optional[int] = None  # cap on annual shifts; None = unlimited

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator("blackout_dates", mode="before")
    @classmethod
    def parse_blackout_dates(cls, v):
        if not v:
            return []
        result = []
        for d in v:
            if isinstance(d, date):
                result.append(d)
            elif isinstance(d, str):
                result.append(date.fromisoformat(d))
            else:
                raise ValueError(f"Cannot parse date: {d}")
        return result

    def is_available_on(self, d: date) -> bool:
        return d not in self.blackout_dates

    def can_cover_region(self, region: str) -> bool:
        return region in self.regions

    def has_skill(self, skill: str) -> bool:
        return skill in self.skills


class ScheduleConfig(BaseModel):
    start_date: date
    end_date: date
    shift_duration_days: int = 7
    shift_start_day: ShiftStartDay = ShiftStartDay.sunday
    min_gap_between_shifts_weeks: int = 4
    required_regions: list[str] = []    # regions that must have a primary each week
    required_skills: list[str] = []     # skills that primary must have (if non-empty)
    generate_backup: bool = True        # False = primary-only schedule; backup added on demand

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_dates(cls, v):
        if isinstance(v, date):
            return v
        return date.fromisoformat(v)

    @model_validator(mode="after")
    def end_after_start(self) -> ScheduleConfig:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

    def shift_start_dates(self) -> list[date]:
        """Return the Monday/Sunday that starts each shift window."""
        target_weekday = 6 if self.shift_start_day == ShiftStartDay.sunday else 0
        first = self.start_date
        # advance to first occurrence of the target weekday
        days_ahead = (target_weekday - first.weekday()) % 7
        first = first + timedelta(days=days_ahead)

        starts = []
        current = first
        while current + timedelta(days=self.shift_duration_days - 1) <= self.end_date:
            starts.append(current)
            current += timedelta(days=self.shift_duration_days)
        return starts


class ShiftAssignment(BaseModel):
    week_start: date
    week_end: date
    primary_id: Optional[str] = None
    backup_id: Optional[str] = None
    region: Optional[str] = None
    notes: str = ""

    @property
    def is_unassigned(self) -> bool:
        return self.primary_id is None

    def involves_person(self, person_id: str) -> bool:
        return self.primary_id == person_id or self.backup_id == person_id


class Schedule(BaseModel):
    config: ScheduleConfig
    assignments: list[ShiftAssignment] = []

    def shifts_for(self, person_id: str) -> list[ShiftAssignment]:
        return [a for a in self.assignments if a.involves_person(person_id)]

    def primary_shifts_for(self, person_id: str) -> list[ShiftAssignment]:
        return [a for a in self.assignments if a.primary_id == person_id]

    def backup_shifts_for(self, person_id: str) -> list[ShiftAssignment]:
        return [a for a in self.assignments if a.backup_id == person_id]


class TeamConfig(BaseModel):
    schedule: ScheduleConfig
    people: list[Person]

    @model_validator(mode="after")
    def unique_ids(self) -> TeamConfig:
        ids = [p.id for p in self.people]
        if len(ids) != len(set(ids)):
            raise ValueError("Person IDs must be unique")
        return self

    def person_by_id(self, person_id: str) -> Optional[Person]:
        for p in self.people:
            if p.id == person_id:
                return p
        return None


class Violation(BaseModel):
    week_start: date
    severity: str           # "error" | "warning"
    code: str               # machine-readable key
    message: str


class ScheduleResult(BaseModel):
    schedule: Schedule
    violations: list[Violation] = []
    fairness: dict[str, int] = {}   # person_id -> primary shift count

    @property
    def has_errors(self) -> bool:
        return any(v.severity == "error" for v in self.violations)
