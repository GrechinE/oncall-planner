"""
Export a ScheduleResult to Excel (.xlsx), CSV, or iCalendar (.ics).
"""

from __future__ import annotations

import io
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Union

import pandas as pd

from .fairness import PersonFairnessRow, compute_fairness, fairness_summary_text
from .holidays import get_public_holidays_with_names
from .validator import violations_summary_text

if TYPE_CHECKING:
    from .models import ScheduleResult, TeamConfig


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe(value: str) -> str:
    """Strip leading characters that Excel treats as formula starters."""
    if value and value[0] in _FORMULA_PREFIXES:
        return "'" + value
    return value


def _holidays_in_week(countries: list[str], week_start: date, week_end: date) -> str:
    """Return a comma-separated string of 'Name (CC)' for all holidays in the week."""
    from datetime import timedelta
    seen: list[str] = []
    for country in countries:
        years = {week_start.year, week_end.year}
        for year in years:
            named = get_public_holidays_with_names(country, year)
            if not named:
                continue
            current = week_start
            while current <= week_end:
                if current in named:
                    entry = f"{named[current]} ({country})"
                    if entry not in seen:
                        seen.append(entry)
                current += timedelta(days=1)
    return "; ".join(seen)


def build_schedule_dataframe(result: "ScheduleResult", team: "TeamConfig") -> pd.DataFrame:
    """Return a DataFrame with one row per week (per region)."""
    person_map = {p.id: p for p in team.people}
    all_countries = list({p.country for p in team.people})
    has_backup = any(a.backup_id for a in result.schedule.assignments)
    has_regions = bool(result.schedule.config.required_regions)

    rows = []
    for a in result.schedule.assignments:
        primary = person_map.get(a.primary_id) if a.primary_id else None
        backup = person_map.get(a.backup_id) if a.backup_id else None
        holidays = _holidays_in_week(all_countries, a.week_start, a.week_end)

        row: dict = {
            "Week Start": a.week_start.isoformat(),
            "Week End": a.week_end.isoformat(),
        }
        if has_regions:
            row["Region"] = _safe(a.region or "all")
        row["Primary"] = _safe(primary.name if primary else "UNASSIGNED")
        row["Primary Country"] = _safe(primary.country if primary else "")
        if has_backup:
            row["Backup"] = _safe(backup.name if backup else "")
            row["Backup Country"] = _safe(backup.country if backup else "")
        row["Team Holidays"] = holidays
        row["Notes"] = _safe(a.notes)

        rows.append(row)

    return pd.DataFrame(rows)


def build_fairness_dataframe(rows: list[PersonFairnessRow]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Person ID": _safe(r.person_id),
            "Name": _safe(r.name),
            "Country": _safe(r.country),
            "Primary Shifts": r.primary_shifts,
            "Backup Shifts": r.backup_shifts,
            "Total Shifts": r.total_shifts,
            "Expected Primary": r.expected_primary,
            "Deviation": r.deviation,
            "Holiday Weeks": r.holiday_weeks,
        }
        for r in rows
    ])


def export_to_excel(
    result: "ScheduleResult",
    team: "TeamConfig",
    output_path: Union[str, Path, None] = None,
) -> bytes:
    """
    Write schedule + fairness + violations to an .xlsx workbook.
    Returns the raw bytes. If output_path is provided, also writes to disk.
    """
    schedule_df = build_schedule_dataframe(result, team)
    fairness_rows = compute_fairness(result, team)
    fairness_df = build_fairness_dataframe(fairness_rows)

    violations_text = violations_summary_text(result.violations)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        schedule_df.to_excel(writer, sheet_name="Schedule", index=False)
        fairness_df.to_excel(writer, sheet_name="Fairness", index=False)

        # Violations as a plain-text sheet
        violations_df = pd.DataFrame(
            [{"Violations": violations_text}]
        )
        violations_df.to_excel(writer, sheet_name="Violations", index=False)

        _autofit_columns(writer)

    raw = buf.getvalue()
    if output_path:
        Path(output_path).write_bytes(raw)
    return raw


def export_to_csv(
    result: "ScheduleResult",
    team: "TeamConfig",
    output_path: Union[str, Path, None] = None,
) -> str:
    """Return schedule as CSV string and optionally write to disk."""
    df = build_schedule_dataframe(result, team)
    csv = df.to_csv(index=False)
    if output_path:
        Path(output_path).write_text(csv, encoding="utf-8")
    return csv


def export_to_ical(
    result: "ScheduleResult",
    team: "TeamConfig",
    output_path: Union[str, Path, None] = None,
) -> str:
    """
    Return an iCalendar (.ics) string with one VEVENT per week.

    Each event spans the full week (all-day, DATE-based).
    Summary: "On-Call: <Primary> (+ Backup: <Backup>)"
    Description includes country and any team holidays that week.
    """
    person_map = {p.id: p for p in team.people}
    all_countries = list({p.country for p in team.people})
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OnCall Planner//oncall-planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:On-Call Schedule",
        "X-WR-CALDESC:Generated by OnCall Planner",
    ]

    for a in result.schedule.assignments:
        primary = person_map.get(a.primary_id) if a.primary_id else None
        backup = person_map.get(a.backup_id) if a.backup_id else None

        primary_label = primary.name if primary else "UNASSIGNED"
        summary = f"On-Call: {primary_label}"
        if backup:
            summary += f" (+ Backup: {backup.name})"
        if a.region:
            summary += f" [{a.region}]"

        desc_parts = []
        if primary:
            desc_parts.append(f"Primary: {primary.name} ({primary.country})")
        if backup:
            desc_parts.append(f"Backup: {backup.name} ({backup.country})")
        holidays = _holidays_in_week(all_countries, a.week_start, a.week_end)
        if holidays:
            desc_parts.append(f"Holidays: {holidays}")
        if a.notes:
            desc_parts.append(f"Notes: {a.notes}")
        description = "\\n".join(desc_parts)

        # iCal all-day events: DTSTART is week_start, DTEND is week_end + 1 day (exclusive)
        from datetime import timedelta
        dtstart = a.week_start.strftime("%Y%m%d")
        dtend = (a.week_end + timedelta(days=1)).strftime("%Y%m%d")
        uid = str(uuid.uuid4())

        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now}",
            f"DTSTART;VALUE=DATE:{dtstart}",
            f"DTEND;VALUE=DATE:{dtend}",
            f"SUMMARY:{_ical_escape(summary)}",
            f"DESCRIPTION:{_ical_escape(description)}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    ical = "\r\n".join(lines) + "\r\n"

    if output_path:
        Path(output_path).write_text(ical, encoding="utf-8")
    return ical


def _ical_escape(value: str) -> str:
    """Escape special characters for iCalendar text values."""
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


_WIDE_COLUMNS = {"team holidays", "notes"}


def _autofit_columns(writer: pd.ExcelWriter) -> None:
    for sheet_name, worksheet in writer.sheets.items():
        for col in worksheet.columns:
            header = str(col[0].value or "").lower()
            max_len = max(
                (len(str(cell.value)) for cell in col if cell.value is not None),
                default=8,
            )
            cap = 80 if header in _WIDE_COLUMNS else 30
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, cap)
