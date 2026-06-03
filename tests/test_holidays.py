from datetime import date
from src.scheduler.holidays import get_public_holidays, get_public_holidays_with_names, person_has_holiday_in_week


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


def test_il_includes_holiday_eves():
    from src.scheduler.holidays import _holiday_cache
    _holiday_cache.clear()
    named = get_public_holidays_with_names("IL", 2026)
    # Yom Kippur is Sep 21; its eve (Sep 20) must be present
    assert date(2026, 9, 20) in named
    assert "(Eve)" in named[date(2026, 9, 20)]
    # Yom Kippur itself must still be present
    assert date(2026, 9, 21) in named
    assert "(Eve)" not in named[date(2026, 9, 21)]


def test_il_rosh_hashana_eve_no_duplicate():
    # Rosh Hashana is a 2-day holiday: Sep 12 + Sep 13.
    # Eve of Sep 12 = Sep 11 (should be added).
    # Eve of Sep 13 = Sep 12 (already the holiday itself — must not be overwritten).
    from src.scheduler.holidays import _holiday_cache
    _holiday_cache.clear()
    named = get_public_holidays_with_names("IL", 2026)
    assert date(2026, 9, 11) in named        # eve of day-1 added
    assert "(Eve)" in named[date(2026, 9, 11)]
    assert date(2026, 9, 12) in named        # day-1 holiday still present
    assert "(Eve)" not in named[date(2026, 9, 12)]  # not overwritten with "(Eve)"


def test_us_has_no_eves():
    from src.scheduler.holidays import _holiday_cache
    _holiday_cache.clear()
    named = get_public_holidays_with_names("US", 2026)
    eves = [v for v in named.values() if "(Eve)" in v]
    assert eves == []


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
