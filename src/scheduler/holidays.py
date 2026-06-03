"""
Holiday fetching for the OnCall Planner.

Primary source: `holidays` Python library (60+ countries, offline, fast).
Fallback: Nager.Date public API (for countries not in the library).

For countries where the eve (day before) a public holiday is also a non-working
day (e.g. Israel), eves are automatically added to the returned dict with a
" (Eve)" suffix so they appear in the schedule calendar.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

import requests

try:
    import holidays as holidays_lib
    _HOLIDAYS_LIB_AVAILABLE = True
except ImportError:
    _HOLIDAYS_LIB_AVAILABLE = False

logger = logging.getLogger(__name__)

NAGER_BASE_URL = "https://date.nager.at/api/v3/PublicHolidays"

# Countries where the eve (day before) each public holiday is also non-working.
# For these countries, eves are automatically inserted into the returned dict.
_COUNTRIES_WITH_HOLIDAY_EVES: frozenset[str] = frozenset({"IL"})

# Countries supported by the `holidays` library (representative list)
_HOLIDAYS_LIB_COUNTRIES = {
    "AR", "AU", "AT", "BY", "BE", "BR", "CA", "CL", "CN", "CO", "HR", "CZ",
    "DK", "EG", "EE", "FI", "FR", "DE", "GR", "HK", "HU", "IS", "IN", "IE",
    "IL", "IT", "JP", "KZ", "KR", "LV", "LT", "LU", "MX", "MD", "MA", "NL",
    "NZ", "NG", "NO", "PK", "PY", "PE", "PH", "PL", "PT", "RO", "RU", "SA",
    "RS", "SG", "SK", "SI", "ZA", "ES", "SE", "CH", "TW", "TH", "TR", "UA",
    "GB", "US", "UY", "VN", "ZW",
}


def _add_holiday_eves(holidays: dict[date, str]) -> dict[date, str]:
    """
    Return a new dict that includes the original holidays plus the eve (day before)
    of each holiday entry.  If the eve date is already in the dict (e.g. a multi-day
    holiday like Rosh Hashana where day-2 eve == day-1 holiday), it is not overwritten.
    Eve entries get a " (Eve)" suffix on the name.
    """
    eves: dict[date, str] = {}
    for d, name in holidays.items():
        eve = d - timedelta(days=1)
        if eve not in holidays and eve not in eves:
            eves[eve] = f"{name} (Eve)"
    return {**holidays, **eves}


def get_non_working_days_with_names(country: str, year: int) -> Optional[dict[date, str]]:
    """
    Public entry point for the Holidays UI tab.
    Returns raw holidays + eves for countries in _COUNTRIES_WITH_HOLIDAY_EVES.
    Always fetches fresh (no module-level cache) so the result is never stale.
    """
    country = country.upper()
    raw = _fetch_from_lib_with_names(country, year)
    if raw is None:
        raw = _fetch_from_nager_with_names(country, year)
    if raw is None:
        return None
    if country in _COUNTRIES_WITH_HOLIDAY_EVES:
        return _add_holiday_eves(raw)
    return raw


def get_public_holidays(country: str, year: int) -> frozenset[date]:
    """
    Return a frozenset of public holiday dates for the given country and year.
    Uses `holidays` library first; falls back to Nager.Date API.
    Includes holiday eves for countries in _COUNTRIES_WITH_HOLIDAY_EVES.
    """
    country = country.upper()
    named = get_public_holidays_with_names(country, year)
    if named is None:
        logger.warning("No holiday data available for %s %d", country, year)
        return frozenset()
    return frozenset(named.keys())


# Increment this when the holiday logic changes — busts all in-process caches.
_CACHE_VERSION = 2

_holiday_cache: dict[tuple[str, int, int], Optional[dict[date, str]]] = {}


def get_public_holidays_with_names(country: str, year: int) -> Optional[dict[date, str]]:
    """
    Return a dict of {date: holiday_name} for the given country and year.
    Returns None if no data is available from any source.
    For countries in _COUNTRIES_WITH_HOLIDAY_EVES, the eve of each holiday is
    also included (e.g. Israel: erev Yom Kippur is a non-working day).
    """
    country = country.upper()
    key = (country, year, _CACHE_VERSION)
    if key in _holiday_cache:
        return _holiday_cache[key]
    result = _fetch_from_lib_with_names(country, year)
    if result is None:
        result = _fetch_from_nager_with_names(country, year)
    if result is not None:
        if country in _COUNTRIES_WITH_HOLIDAY_EVES:
            result = _add_holiday_eves(result)
        _holiday_cache[key] = result
    return result


def _fetch_from_lib_with_names(country: str, year: int) -> Optional[dict[date, str]]:
    if not _HOLIDAYS_LIB_AVAILABLE:
        return None
    if country not in _HOLIDAYS_LIB_COUNTRIES:
        return None
    try:
        h = holidays_lib.country_holidays(country, years=year)
        return dict(h.items())  # {date: name}
    except Exception as exc:
        logger.debug("holidays lib failed for %s %d: %s", country, year, exc)
        return None


def _fetch_from_nager_with_names(country: str, year: int) -> Optional[dict[date, str]]:
    url = f"{NAGER_BASE_URL}/{year}/{country}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                date.fromisoformat(item["date"]): item.get("localName") or item.get("name", "")
                for item in data
            }
        logger.debug("Nager.Date returned %d for %s %d", resp.status_code, country, year)
        return None
    except Exception as exc:
        logger.debug("Nager.Date fetch failed for %s %d: %s", country, year, exc)
        return None


# Keep old internal helpers as thin wrappers for any direct callers
def _fetch_from_lib(country: str, year: int) -> Optional[list[date]]:
    result = _fetch_from_lib_with_names(country, year)
    return list(result.keys()) if result else None


def _fetch_from_nager(country: str, year: int) -> Optional[list[date]]:
    result = _fetch_from_nager_with_names(country, year)
    return list(result.keys()) if result else None


def person_has_holiday_in_week(
    country: str, week_start: date, week_end: date
) -> bool:
    """Return True if the country has any public holiday in [week_start, week_end]."""
    years = {week_start.year, week_end.year}
    for year in years:
        holidays = get_public_holidays(country, year)
        current = week_start
        while current <= week_end:
            if current in holidays:
                return True
            from datetime import timedelta
            current += timedelta(days=1)
    return False


def get_holidays_in_range(country: str, start: date, end: date) -> list[date]:
    """Return all public holidays for a country between start and end (inclusive)."""
    years = range(start.year, end.year + 1)
    result = []
    for year in years:
        for h in get_public_holidays(country, year):
            if start <= h <= end:
                result.append(h)
    return sorted(result)
