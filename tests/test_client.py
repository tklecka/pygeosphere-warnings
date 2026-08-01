"""Tests for the GeoSphere Austria Warn API client."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import aiohttp
import pytest
from aiohttp import web

from pygeosphere_warnings import (
    GeoSphereApiError,
    GeoSphereConnectionError,
    GeoSphereMunicipalityNotFoundError,
    GeoSphereWarningsClient,
    WarningLevel,
    WarningType,
)
from pygeosphere_warnings.models import TZ_VIENNA

from .conftest import ClientFactory

WARNINGS_RESPONSE: dict[str, Any] = {
    "type": "Feature",
    "properties": {
        "location": {
            "properties": {
                "gemeindenr": 90001,
                "name": "Wien",
                "urlname": "wien",
            }
        },
        "warnings": [
            {
                "properties": {
                    "warnid": 123,
                    "chgid": 456,
                    "verlaufid": 789,
                    "warntypid": 1,
                    "warnstufeid": 2,
                    "create": "2023-11-14 20:00:00+00",
                    "rawinfo": {"start": "1700000000", "end": "1700010000"},
                    "begin": "14.11.2023 23:13",
                    "end": "15.11.2023 02:00",
                    "text": "Storm warning",
                    "auswirkungen": "Falling branches",
                    "empfehlungen": "Stay inside",
                    "meteotext": "Strong westerly winds",
                    "updategrund": "",
                }
            }
        ],
    },
}


async def test_get_warnings_for_coords(make_client: ClientFactory) -> None:
    received: dict[str, str] = {}

    async def handler(request: web.Request) -> web.Response:
        received.update(request.query)
        return web.json_response(WARNINGS_RESPONSE)

    client = await make_client(web.get("/getWarningsForCoords", handler))

    result = await client.get_warnings_for_coords(48.2, 16.37)

    assert received == {"lat": "48.2", "lon": "16.37", "lang": "en"}
    assert result.municipality.municipality_id == "90001"
    assert result.municipality.name == "Wien"
    assert result.municipality.url_name == "wien"
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.warning_type is WarningType.STORM
    assert warning.level is WarningLevel.ORANGE
    assert warning.start == datetime.fromtimestamp(1700000000, tz=UTC)
    assert warning.end == datetime.fromtimestamp(1700010000, tz=UTC)
    assert warning.text == "Storm warning"


async def test_get_warnings_for_coords_no_warnings(
    make_client: ClientFactory,
) -> None:
    payload: dict[str, Any] = {
        "properties": {
            "location": {
                "properties": {
                    "gemeindenr": 90001,
                    "name": "Wien",
                    "urlname": "wien",
                }
            },
            "warnings": None,
        }
    }

    async def handler(request: web.Request) -> web.Response:
        return web.json_response(payload)

    client = await make_client(web.get("/getWarningsForCoords", handler))

    result = await client.get_warnings_for_coords(48.2, 16.37)

    assert result.warnings == []


async def test_get_warnings_for_coords_not_found(
    make_client: ClientFactory,
) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=404)

    client = await make_client(web.get("/getWarningsForCoords", handler))

    with pytest.raises(GeoSphereMunicipalityNotFoundError):
        await client.get_warnings_for_coords(52.52, 13.40)


async def test_get_warnings_for_coords_malformed(
    make_client: ClientFactory,
) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"properties": {}})

    client = await make_client(web.get("/getWarningsForCoords", handler))

    with pytest.raises(GeoSphereApiError, match="Could not parse"):
        await client.get_warnings_for_coords(48.2, 16.37)


async def test_api_error_response(make_client: ClientFactory) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"type": "error", "msg": "something broke"})

    client = await make_client(web.get("/getWarningsForCoords", handler))

    with pytest.raises(GeoSphereApiError, match="something broke"):
        await client.get_warnings_for_coords(48.2, 16.37)


async def test_http_error_status(make_client: ClientFactory) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=500)

    client = await make_client(web.get("/getWarningsForCoords", handler))

    with pytest.raises(GeoSphereApiError, match="500"):
        await client.get_warnings_for_coords(48.2, 16.37)


async def test_invalid_json(make_client: ClientFactory) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(text="not json", content_type="text/plain")

    client = await make_client(web.get("/getWarningsForCoords", handler))

    with pytest.raises(GeoSphereApiError, match="Invalid JSON"):
        await client.get_warnings_for_coords(48.2, 16.37)


async def test_connection_error(session: aiohttp.ClientSession) -> None:
    client = GeoSphereWarningsClient(session, base_url="http://127.0.0.1:1")

    with pytest.raises(GeoSphereConnectionError):
        await client.get_warnings_for_coords(48.2, 16.37)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        pytest.param(
            "Tue, 14 Nov 2023 22:13:20 GMT",
            datetime.fromtimestamp(1700000000, tz=UTC),
            id="gmt",
        ),
        # The production API labels the header with the zone name instead of
        # an offset, which RFC 2822 parsing cannot resolve.
        pytest.param(
            "Tue, 14 Nov 2023 23:13:20 CET",
            datetime(2023, 11, 14, 23, 13, 20, tzinfo=TZ_VIENNA),
            id="cet",
        ),
        pytest.param(
            "Sat, 01 Aug 2026 13:22:06 CEST",
            datetime(2026, 8, 1, 13, 22, 6, tzinfo=TZ_VIENNA),
            id="cest",
        ),
    ],
)
async def test_get_last_modified(
    make_client: ClientFactory, header: str, expected: datetime
) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(headers={"Last-Modified": header})

    client = await make_client(web.head("/getWarnstatus", handler))

    result = await client.get_last_modified()

    assert result == expected
    assert result is not None
    assert result.tzinfo is not None


async def test_get_last_modified_missing_header(
    make_client: ClientFactory,
) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response()

    client = await make_client(web.head("/getWarnstatus", handler))

    assert await client.get_last_modified() is None


async def test_get_last_modified_invalid_header(make_client: ClientFactory) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(headers={"Last-Modified": "not a date"})

    client = await make_client(web.head("/getWarnstatus", handler))

    with pytest.raises(GeoSphereApiError, match="Invalid Last-Modified"):
        await client.get_last_modified()


async def test_get_last_modified_error(make_client: ClientFactory) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=503)

    client = await make_client(web.head("/getWarnstatus", handler))

    with pytest.raises(GeoSphereApiError, match="503"):
        await client.get_last_modified()


async def test_get_thunderstorms(make_client: ClientFactory) -> None:
    payload: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": [
            {"properties": {"gemeindenr": 90001, "intensitaet": "2"}},
            {"properties": {"gemeindenr": 10101, "intensitaet": 1}},
            # The schema declares intensitaet as a number, not an integer.
            {"properties": {"gemeindenr": 70804, "intensitaet": 3.0}},
            {"properties": None},
        ],
    }

    async def handler(request: web.Request) -> web.Response:
        return web.json_response(payload)

    client = await make_client(web.get("/getGewitterAuto", handler))

    result = await client.get_thunderstorms()

    assert result == {"90001": 2, "10101": 1, "70804": 3}


async def test_get_thunderstorms_malformed(make_client: ClientFactory) -> None:
    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"features": [{"properties": {"gemeindenr": 1}}]})

    client = await make_client(web.get("/getGewitterAuto", handler))

    with pytest.raises(GeoSphereApiError, match="Could not parse"):
        await client.get_thunderstorms()


@pytest.mark.parametrize(
    ("status", "expected_error"),
    [
        (404, GeoSphereMunicipalityNotFoundError),
        (500, GeoSphereApiError),
    ],
    ids=["not-found", "http-error"],
)
async def test_error_paths_release_the_connection(
    make_client: ClientFactory,
    single_connection_session: aiohttp.ClientSession,
    status: int,
    expected_error: type[Exception],
) -> None:
    """An error response with an unfinished body must not keep its connection.

    aiohttp only returns a connection to the pool on its own once the payload
    reaches EOF, so an error raised before the whole body arrived holds the
    connector slot for as long as the exception - and with it the traceback
    referencing the response - is retained by the caller.
    """
    stall = asyncio.Event()

    async def handler(request: web.Request) -> web.StreamResponse:
        if request.query["lat"] == "1.0":
            return web.json_response(WARNINGS_RESPONSE)
        response = web.StreamResponse(status=status)
        await response.prepare(request)
        await response.write(b"error page fragment")
        await stall.wait()
        return response

    client = await make_client(
        web.get("/getWarningsForCoords", handler),
        client_session=single_connection_session,
    )

    # A Home Assistant coordinator keeps the last exception around, which is
    # what keeps the response alive. With a single allowed connection the
    # leaked slot starves every following request, so the timeout fails the
    # test instead of hanging it.
    retained: list[BaseException] = []
    try:
        async with asyncio.timeout(5):
            for _ in range(3):
                with pytest.raises(expected_error) as excinfo:
                    await client.get_warnings_for_coords(48.2, 16.37)
                retained.append(excinfo.value)

            result = await client.get_warnings_for_coords(1.0, 16.37)
    finally:
        stall.set()

    assert len(retained) == 3
    assert result.municipality.name == "Wien"
