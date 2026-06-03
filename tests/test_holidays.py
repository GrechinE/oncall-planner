from datetime import date
from src.scheduler.holidays import get_public_holidays, person_has_holiday_in_week


def test_us_independence_day_2026():
    holidays = get_public_holidays("US", 2026)
    assert date(2026, 7, 4) in holidays


def test_us_christmas_2026():
    holidays = get_public_holidays("US", 2026)
    assert date(2026, 12, 25) in holidays


def test_in_republic_day_2026():
    holidays = get_public_holidays("IN", 2026)
    assert date(2026, 1, 26) in holidays


def test_il_has_holidays_2026():
    holidays = get_public_holidays("IL", 2026)
    assert len(holidays) > 0


def test_gb_has_holidays_2026():
    holidays = get_public_holidays("GB", 2026)
    assert len(holidays) > 0


def test_person_has_holiday_in_week_true():
    # July 4th 2026 is a Saturday; the Sun-to-Sat week starting Jun 28 contains it
    assert person_has_holiday_in_week("US", date(2026, 6, 28), date(2026, 7, 4))


def test_person_has_holiday_in_week_false():
    # Week with no known US holiday
    assert not person_has_holiday_in_week("US", date(2026, 3, 1), date(2026, 3, 7))


def test_caching_returns_same_object():
    from src.scheduler.holidays import get_public_holidays_with_names
    # with_names uses a dict cache — same dict object returned on second call
    h1 = get_public_holidays_with_names("US", 2026)
    h2 = get_public_holidays_with_names("US", 2026)
    assert h1 is h2  # cached dict, not rebuilt
    # get_public_holidays returns equal frozensets (rebuilt each call from cache)
    f1 = get_public_holidays("US", 2026)
    f2 = get_public_holidays("US", 2026)
    assert f1 == f2
