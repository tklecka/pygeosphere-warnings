"""Asynchronous client for the GeoSphere Austria Warn API."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

from .exceptions import (
    GeoSphereApiError,
    GeoSphereConnectionError,
    GeoSphereMunicipalityNotFoundError,
)
from .models import LocationWarnings

DEFAULT_BASE_URL = "https://warnungen.zamg.at/wsapp/api"
DEFAULT_TIMEOUT = 10


class GeoSphereWarningsClient:
    """Client for the GeoSphere Austria Warn API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the client with an externally managed session."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> aiohttp.ClientResponse:
        """Perform a request and handle transport errors."""
        try:
            response = await self._session.request(
                method,
                f"{self._base_url}{path}",
                params=params,
                timeout=self._timeout,
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise GeoSphereConnectionError(
                f"Error communicating with the GeoSphere Warn API: {err}"
            ) from err
        return response

    async def get_last_modified(self) -> datetime | None:
        """Return the timestamp of the latest warning update.

        Issues a cheap HEAD request that can be used to decide whether a
        full warning fetch is necessary.
        """
        response = await self._request("HEAD", "/getWarnstatus")
        if response.status >= 400:
            raise GeoSphereApiError(
                f"Unexpected response from the GeoSphere Warn API: {response.status}"
            )
        if (last_modified := response.headers.get("Last-Modified")) is None:
            return None
        try:
            return parsedate_to_datetime(last_modified)
        except ValueError as err:
            raise GeoSphereApiError(
                f"Invalid Last-Modified header: {last_modified}"
            ) from err

    async def get_warnings_for_coords(
        self, latitude: float, longitude: float, language: str = "en"
    ) -> LocationWarnings:
        """Return the warnings for the municipality at the given coordinates."""
        response = await self._request(
            "GET",
            "/getWarningsForCoords",
            params={"lat": latitude, "lon": longitude, "lang": language},
        )
        if response.status == 404:
            raise GeoSphereMunicipalityNotFoundError(
                f"No Austrian municipality found at {latitude}, {longitude}"
            )
        data = await self._parse_json(response)
        try:
            return LocationWarnings.from_api(data)
        except (KeyError, TypeError, ValueError) as err:
            raise GeoSphereApiError(f"Could not parse warning response: {err}") from err

    async def get_thunderstorms(self) -> dict[str, int]:
        """Return automated thunderstorm warnings by municipality id."""
        response = await self._request("GET", "/getGewitterAuto")
        data = await self._parse_json(response)
        try:
            return {
                str(properties["gemeinde"]): int(properties["intensitaet"])
                for feature in data.get("features") or []
                if (properties := feature.get("properties")) is not None
            }
        except (KeyError, TypeError, ValueError) as err:
            raise GeoSphereApiError(
                f"Could not parse thunderstorm response: {err}"
            ) from err

    async def _parse_json(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        """Validate the response and decode it as JSON."""
        if response.status >= 400:
            raise GeoSphereApiError(
                f"Unexpected response from the GeoSphere Warn API: {response.status}"
            )
        try:
            data: dict[str, Any] = await response.json()
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise GeoSphereApiError(
                f"Invalid JSON response from the GeoSphere Warn API: {err}"
            ) from err
        if data.get("type") == "error":
            raise GeoSphereApiError(
                f"The GeoSphere Warn API returned an error: {data.get('msg')}"
            )
        return data
