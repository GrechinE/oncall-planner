from pathlib import Path
from src.scheduler.loader import load_from_json, load_from_csv


SAMPLE_DIR = Path(__file__).parent.parent / "data" / "samples"


def test_load_from_json():
    team = load_from_json(SAMPLE_DIR / "team_config.json")
    assert len(team.people) >= 10
    assert team.schedule.start_date.year == 2026


def test_load_from_csv():
    team = load_from_csv(SAMPLE_DIR / "people.csv", SAMPLE_DIR / "schedule.json")
    assert len(team.people) >= 10
    ids = {p.id for p in team.people}
    assert "avi" in ids
    assert "priya" in ids


def test_loader_regions_parsed():
    team = load_from_json(SAMPLE_DIR / "team_config.json")
    avi = team.person_by_id("avi")
    assert "emea" in avi.regions


def test_loader_blackouts_parsed():
    team = load_from_json(SAMPLE_DIR / "team_config.json")
    from datetime import date
    avi = team.person_by_id("avi")
    assert date(2026, 9, 21) in avi.blackout_dates
