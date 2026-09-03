"""Container health check."""

from __future__ import annotations

import asyncio
import os

from asyncua import Client

from .server import DEFAULT_ENDPOINT


async def _check() -> None:
    endpoint = os.environ.get("PROCESS_SIMULATOR_ENDPOINT", DEFAULT_ENDPOINT)
    async with Client(endpoint, timeout=3) as client:
        await client.nodes.server_state.read_value()


def main() -> int:
    try:
        asyncio.run(_check())
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
