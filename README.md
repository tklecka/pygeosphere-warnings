# pygeosphere-warnings

[![PyPI](https://img.shields.io/pypi/v/pygeosphere-warnings)](https://pypi.org/project/pygeosphere-warnings/)
[![CI](https://github.com/tklecka/pygeosphere-warnings/actions/workflows/ci.yml/badge.svg)](https://github.com/tklecka/pygeosphere-warnings/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Asynchronous Python client for the [GeoSphere Austria Warn API](https://openapi.hub.geosphere.at/warnapi/v1/),
which provides the official GeoSphere Austria weather warnings for all
municipalities in Austria.

## Usage

```python
import asyncio

import aiohttp

from pygeosphere_warnings import GeoSphereWarningsClient


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        client = GeoSphereWarningsClient(session)

        # Cheap HEAD precheck: timestamp of the latest warning update
        last_modified = await client.get_last_modified()
        print(f"Warnings last updated: {last_modified}")

        # Warnings for the municipality at the given coordinates
        warnings = await client.get_warnings_for_coords(48.2486, 16.3564, "en")
        print(f"Municipality: {warnings.municipality.name}")
        for warning in warnings.warnings:
            print(
                f"- {warning.warning_type.name} ({warning.level.name}): {warning.text}"
            )

        # Automated thunderstorm warnings (municipality id -> intensity)
        thunderstorms = await client.get_thunderstorms()
        print(thunderstorms.get(warnings.municipality.municipality_id))


asyncio.run(main())
```

## License

MIT. Warning data: © GeoSphere Austria, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
