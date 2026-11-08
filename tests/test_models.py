"""Tests for the GeoSphere Austria Warn API models."""

from datetime import UTC, datetime
from typing import Any

import pytest

from pygeosphere_warnings import WarningLevel, WarningType, WeatherWarning
from pygeosphere_warnings.models import TZ_VIENNA, _parse_time

WARNING_PROPERTIES: dict[str, Any] = {
    "warnid": 123,
    "chgid": 456,
    "verlaufid": 789,
    "warntypid": 5,
    "warnstufeid": 3,
    "create": "2023-11-14 20:00:00+00",
    "rawinfo": {"start": "1700000000", "end": "1700010000"},
    "begin": "14.11.2023 23:13",
    "end": "15.11.2023 02:00",
    "text": "Thunderstorm warning",
    "auswirkungen": None,
    "empfehlungen": None,
    "meteotext": None,
    "updategrund": None,
}


def test_warning_from_api() -> None:
    warning = WeatherWarning.from_api(WARNING_PROPERTIES)

    assert warning.warning_id == 123
    assert warning.warning_type is WarningType.THUNDERSTORM
    assert warning.level is WarningLevel.RED
    assert warning.impacts == ""
    assert warning.recommendations == ""
    assert warning.created == datetime(2023, 11, 14, 20, 0, tzinfo=UTC)


def test_warning_from_api_without_created() -> None:
    data = {k: v for k, v in WARNING_PROPERTIES.items() if k != "create"}

    assert WeatherWarning.from_api(data).created is None


def test_warning_from_api_without_rawinfo() -> None:
    data = {**WARNING_PROPERTIES, "rawinfo": None}

    warning = WeatherWarning.from_api(data)

    assert warning.start == datetime(2023, 11, 14, 23, 13, tzinfo=TZ_VIENNA)
    assert warning.end == datetime(2023, 11, 15, 2, 0, tzinfo=TZ_VIENNA)


def test_is_active() -> None:
    warning = WeatherWarning.from_api(WARNING_PROPERTIES)

    assert warning.is_active(datetime.fromtimestamp(1700005000, tz=UTC))
    assert not warning.is_active(datetime.fromtimestamp(1700020000, tz=UTC))


def test_is_upcoming() -> None:
    warning = WeatherWarning.from_api(WARNING_PROPERTIES)

    assert warning.is_upcoming(datetime.fromtimestamp(1699990000, tz=UTC))
    assert not warning.is_upcoming(datetime.fromtimestamp(1700005000, tz=UTC))
    assert not warning.is_upcoming(datetime.fromtimestamp(1700020000, tz=UTC))


def test_warning_created_defaults_to_none() -> None:
    """Constructing a warning without created keeps working (0.1.x API)."""
    warning = WeatherWarning(
        warning_id=1,
        change_id=2,
        course_id=3,
        warning_type=WarningType.STORM,
        level=WarningLevel.YELLOW,
        start=datetime.fromtimestamp(1700000000, tz=UTC),
        end=datetime.fromtimestamp(1700010000, tz=UTC),
        text="",
        impacts="",
        recommendations="",
        meteo_text="",
        update_reason="",
    )

    assert warning.created is None


def test_parse_time_prefers_epoch() -> None:
    result = _parse_time("1700000000", "14.11.2023 23:13")

    assert result == datetime.fromtimestamp(1700000000, tz=UTC)


def test_parse_time_no_timestamp() -> None:
    with pytest.raises(ValueError, match="No timestamp available"):
        _parse_time(None, None)
