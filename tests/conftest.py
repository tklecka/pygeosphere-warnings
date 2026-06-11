"""Shared fixtures for the pygeosphere-warnings tests."""

from collections.abc import AsyncGenerator, Awaitable, Callable

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from pygeosphere_warnings import GeoSphereWarningsClient

ClientFactory = Callable[..., Awaitable[GeoSphereWarningsClient]]


@pytest.fixture
async def session() -> AsyncGenerator[aiohttp.ClientSession]:
    """Provide an aiohttp session."""
    async with aiohttp.ClientSession() as client_session:
        yield client_session


@pytest.fixture
async def make_client(
    session: aiohttp.ClientSession,
) -> AsyncGenerator[ClientFactory]:
    """Provide a factory that serves the given routes and returns a client."""
    servers: list[TestServer] = []

    async def factory(*routes: web.RouteDef) -> GeoSphereWarningsClient:
        app = web.Application()
        app.add_routes(list(routes))
        server = TestServer(app)
        servers.append(server)
        await server.start_server()
        return GeoSphereWarningsClient(session, base_url=str(server.make_url("/")))

    yield factory

    for server in servers:
        await server.close()
