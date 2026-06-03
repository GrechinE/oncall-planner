from pathlib import Path
from src.scheduler.loader import load_from_json, load_from_csv


SAMPLE_DIR = Path(__file__).parent.parent / "data" / "samples"


def test_load_from_json():
    team = load_from_json(SAMPLE_DIR / "team_config.json")
    assert len(team.people) >= 4
    assert team.schedule.start_date.year == 2026


def test_load_from_csv():
    team = load_from_csv(SAMPLE_DIR / "people.csv", SAMPLE_DIR / "schedule.json")
    assert len(team.people) >= 10
    ids = {p.id for p in team.people}
    assert "avi" in ids
    assert "priya" in ids


def test_loader_regions_parsed():
    # Use the people.csv sample which has regions configured (not team_config.json)
    team = load_from_csv(SAMPLE_DIR / "people.csv", SAMPLE_DIR / "schedule.json")
    avi = team.person_by_id("avi")
    assert "emea" in avi.regions


def test_loader_blackouts_parsed():
    team = load_from_csv(SAMPLE_DIR / "people.csv", SAMPLE_DIR / "schedule.json")
    from datetime import date
    avi = team.person_by_id("avi")
    assert date(2026, 9, 21) in avi.blackout_dates


def test_loader_simple_sample_has_no_regions():
    # team_config.json is the simple demo sample — no regions, global rotation
    team = load_from_json(SAMPLE_DIR / "team_config.json")
    assert team.schedule.required_regions == []
    assert all(p.regions == [] for p in team.people)


def test_loader_simple_sample_valid_countries():
    team = load_from_json(SAMPLE_DIR / "team_config.json")
    countries = {p.country for p in team.people}
    # All should be 2-letter uppercase ISO codes
    assert all(len(c) == 2 and c.isupper() for c in countries)
