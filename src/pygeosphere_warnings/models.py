"""Models for the GeoSphere Austria Warn API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any, Self
from zoneinfo import ZoneInfo

TZ_VIENNA = ZoneInfo("Europe/Vienna")

# Format of the human readable begin/end fields ("27.03.2023 08:00"),
# used as fallback when rawinfo epoch timestamps are missing.
_LOCAL_DATETIME_FORMAT = "%d.%m.%Y %H:%M"


class WarningType(IntEnum):
    """Type of a weather warning."""

    STORM = 1
    RAIN = 2
    SNOW = 3
    BLACK_ICE = 4
    THUNDERSTORM = 5
    HEAT = 6
    COLD = 7


class WarningLevel(IntEnum):
    """Severity level of a weather warning."""

    YELLOW = 1
    ORANGE = 2
    RED = 3


@dataclass(frozen=True, slots=True, kw_only=True)
class Municipality:
    """An Austrian municipality."""

    municipality_id: str
    name: str
    url_name: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        """Parse a municipality from a location object."""
        return cls(
            municipality_id=str(data["gemeindenr"]),
            name=data["name"],
            url_name=data["urlname"],
        )


def _parse_time(raw_epoch: str | None, local_time: str | None) -> datetime:
    """Parse a warning timestamp.

    Prefers the unix epoch from rawinfo; falls back to the human readable
    local time string interpreted as Europe/Vienna.
    """
    if raw_epoch is not None:
        return datetime.fromtimestamp(int(raw_epoch), tz=UTC)
    if local_time is None:
        raise ValueError("No timestamp available")
    return datetime.strptime(local_time, _LOCAL_DATETIME_FORMAT).replace(
        tzinfo=TZ_VIENNA
    )


def _parse_created(created: str | None) -> datetime | None:
    """Parse the time the warning was issued ("2023-03-27 06:00:00+00")."""
    if created is None:
        return None
    return datetime.fromisoformat(created)


@dataclass(frozen=True, slots=True, kw_only=True)
class WeatherWarning:
    """A single weather warning."""

    warning_id: int
    change_id: int
    course_id: int
    warning_type: WarningType
    level: WarningLevel
    created: datetime | None
    start: datetime
    end: datetime
    text: str
    impacts: str
    recommendations: str
    meteo_text: str
    update_reason: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        """Parse a warning from a warning feature's properties."""
        rawinfo: dict[str, Any] = data.get("rawinfo") or {}
        return cls(
            warning_id=data["warnid"],
            change_id=data["chgid"],
            course_id=data["verlaufid"],
            warning_type=WarningType(data["warntypid"]),
            level=WarningLevel(data["warnstufeid"]),
            created=_parse_created(data.get("create")),
            start=_parse_time(rawinfo.get("start"), data.get("begin")),
            end=_parse_time(rawinfo.get("end"), data.get("end")),
            text=data.get("text") or "",
            impacts=data.get("auswirkungen") or "",
            recommendations=data.get("empfehlungen") or "",
            meteo_text=data.get("meteotext") or "",
            update_reason=data.get("updategrund") or "",
        )

    def is_active(self, now: datetime) -> bool:
        """Return whether the warning is active at the given time."""
        return self.start <= now <= self.end

    def is_upcoming(self, now: datetime) -> bool:
        """Return whether the warning starts after the given time."""
        return now < self.start


@dataclass(frozen=True, slots=True, kw_only=True)
class LocationWarnings:
    """Warnings for a municipality."""

    municipality: Municipality
    warnings: list[WeatherWarning]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Self:
        """Parse the response of getWarningsForCoords."""
        properties = data["properties"]
        return cls(
            municipality=Municipality.from_api(properties["location"]["properties"]),
            warnings=[
                WeatherWarning.from_api(warning["properties"])
                for warning in properties.get("warnings") or []
            ],
        )
