import io
import pandas as pd
from src.scheduler.generator import ScheduleGenerator
from src.scheduler.exporter import export_to_excel, export_to_csv, build_schedule_dataframe
from src.scheduler.validator import validate


def test_export_to_csv_returns_string(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    csv = export_to_csv(result, simple_team)
    assert isinstance(csv, str)
    assert "Week Start" in csv
    assert "Primary" in csv
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
    assert "Fairness" in xl.sheet_names
    assert "Violations" in xl.sheet_names


def test_schedule_dataframe_no_nulls_in_key_columns(simple_team):
    result = ScheduleGenerator(simple_team).generate()
    df = build_schedule_dataframe(result, simple_team)
    assert df["Week Start"].notna().all()
    assert df["Week End"].notna().all()
    assert df["Primary"].notna().all()
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
