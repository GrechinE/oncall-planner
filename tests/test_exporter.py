import io
import pandas as pd
from src.scheduler.generator import ScheduleGenerator
from src.scheduler.exporter import export_to_excel, export_to_csv, export_to_ical, build_schedule_dataframe
from src.scheduler.validator import validate


def test_export_to_csv_returns_string(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    csv = export_to_csv(result, simple_team)
    assert isinstance(csv, str)
    assert "Week Start" in csv
    assert "Primary Engineer" in csv
    assert "Team Holidays" in csv


def test_export_to_csv_row_count(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    csv = export_to_csv(result, simple_team)
    df = pd.read_csv(io.StringIO(csv))
    assert len(df) == len(result.schedule.assignments)


def test_export_to_excel_returns_bytes(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    raw = export_to_excel(result, simple_team)
    assert isinstance(raw, bytes)
    # Excel files start with PK (zip header)
    assert raw[:2] == b"PK"


def test_export_excel_has_all_sheets(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    raw = export_to_excel(result, simple_team)
    xl = pd.ExcelFile(io.BytesIO(raw))
    assert "Schedule" in xl.sheet_names
    assert "Engineer Fairness" in xl.sheet_names
    assert "Violations" in xl.sheet_names


def test_schedule_dataframe_no_nulls_in_key_columns(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    df = build_schedule_dataframe(result, simple_team)
    assert df["Week Start"].notna().all()
    assert df["Week End"].notna().all()
    assert df["Primary Engineer"].notna().all()
    assert "Team Holidays" in df.columns


def test_export_sanitises_formula_injection(simple_team):
    """SEC-001: person names starting with formula chars must be prefixed with '."""
    from src.scheduler.models import Person
    from src.scheduler.exporter import _safe

    for dangerous in ["=SUM(A1)", "+cmd|calc", "-2+2", "@SUM", "\t=evil"]:
        result = _safe(dangerous)
        assert result.startswith("'"), f"_safe() did not sanitise: {dangerous!r}"
        assert result[1:] == dangerous

    # Safe values must pass through unchanged
    for safe_val in ["Alice Smith", "US", "americas", ""]:
        assert _safe(safe_val) == safe_val


def test_export_to_ical_returns_string(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    ical = export_to_ical(result, simple_team)
    assert isinstance(ical, str)
    assert "BEGIN:VCALENDAR" in ical
    assert "END:VCALENDAR" in ical


def test_export_to_ical_event_count(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    ical = export_to_ical(result, simple_team)
    event_count = ical.count("BEGIN:VEVENT")
    assert event_count == len(result.schedule.assignments)


def test_export_to_ical_event_structure(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    ical = export_to_ical(result, simple_team)
    assert "DTSTART;VALUE=DATE:" in ical
    assert "DTEND;VALUE=DATE:" in ical
    assert "SUMMARY:On-Call:" in ical
    assert "UID:" in ical


def test_schedule_dataframe_with_manager_column(simple_team):
    """Duty Manager column appears when manager_result is provided."""
    from src.scheduler.models import Person, ScheduleConfig, ShiftStartDay, TeamConfig
    from datetime import date
    mgr_config = ScheduleConfig(
        start_date=date(2026, 1, 4),
        end_date=date(2026, 3, 29),
        shift_duration_days=7,
        shift_start_day=ShiftStartDay.sunday,
        min_gap_between_shifts_weeks=2,
    )
    managers = [
        Person(id="mgr1", name="Manager One", country="US", timezone="America/New_York", regions=[], skills=[]),
        Person(id="mgr2", name="Manager Two", country="GB", timezone="Europe/London", regions=[], skills=[]),
    ]
    mgr_team = TeamConfig(schedule=mgr_config, people=managers)
    mgr_result = ScheduleGenerator(mgr_team).generate()

    eng_result = ScheduleGenerator(simple_team).generate()
    df = build_schedule_dataframe(eng_result, simple_team, mgr_result, mgr_team)
    assert "Duty Manager" in df.columns
    assert df["Duty Manager"].notna().all()


def test_export_excel_with_manager_has_two_fairness_sheets(simple_team):
    """Excel export includes both Engineer Fairness and Manager Fairness sheets."""
    from src.scheduler.models import Person, ScheduleConfig, ShiftStartDay, TeamConfig
    from datetime import date
    mgr_config = ScheduleConfig(
        start_date=date(2026, 1, 4),
        end_date=date(2026, 3, 29),
        shift_duration_days=7,
        shift_start_day=ShiftStartDay.sunday,
        min_gap_between_shifts_weeks=2,
    )
    managers = [
        Person(id="mgr1", name="Manager One", country="US", timezone="America/New_York", regions=[], skills=[]),
        Person(id="mgr2", name="Manager Two", country="GB", timezone="Europe/London", regions=[], skills=[]),
    ]
    mgr_team = TeamConfig(schedule=mgr_config, people=managers)
    mgr_result = ScheduleGenerator(mgr_team).generate()

    eng_result = ScheduleGenerator(simple_team).generate()
    raw = export_to_excel(eng_result, simple_team, manager_result=mgr_result, manager_team=mgr_team)
    xl = pd.ExcelFile(io.BytesIO(raw))
    assert "Engineer Fairness" in xl.sheet_names
    assert "Manager Fairness" in xl.sheet_names


def test_export_csv_formula_injection_in_name(simple_team):
    """Formula-named person must not produce a raw formula cell in CSV output."""
    from src.scheduler.models import Person
    evil_person = Person(
        id="evil", name="=HYPERLINK(\"http://evil.com\")",
        country="US", timezone="America/New_York",
        regions=["americas"], skills=[],
    )
    team = simple_team.model_copy(update={"people": list(simple_team.people) + [evil_person]})
    result = ScheduleGenerator(team).generate()
    csv = export_to_csv(result, team)
    # The sanitised form prefixes with ' so Excel treats it as text, not a formula.
    # Raw =HYPERLINK(...) must not appear — only the prefixed form is acceptable.
    assert "'=HYPERLINK" in csv, "Sanitised formula prefix not found in CSV"
    # Verify no cell starts a raw formula (every =HYPERLINK must be preceded by ')
    import re
    raw_formulas = re.findall(r'(?<!\')=HYPERLINK', csv)
    assert not raw_formulas, f"Raw formula found in CSV export: {raw_formulas}"
