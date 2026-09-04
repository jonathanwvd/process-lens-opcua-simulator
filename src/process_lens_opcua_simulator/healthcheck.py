"""Container health check."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from asyncua import Client, ua
from asyncua.ua.uaerrors import UaError

from .contracts import NAMESPACE_URI
from .server import DEFAULT_ENDPOINT

HEALTH_SIGNAL_NODE_ID = "Plant.ControlLoops.FIC-101.PV"


def _source_is_fresh(
    source_timestamp: datetime | None,
    *,
    now: datetime,
    maximum_age_seconds: float,
) -> bool:
    if source_timestamp is None or maximum_age_seconds <= 0:
        return False
    normalized_source = (
        source_timestamp.replace(tzinfo=UTC)
        if source_timestamp.tzinfo is None
        else source_timestamp.astimezone(UTC)
    )
    normalized_now = now.astimezone(UTC)
    age_seconds = (normalized_now - normalized_source).total_seconds()
    return -maximum_age_seconds <= age_seconds <= maximum_age_seconds


async def _check() -> None:
    endpoint = os.environ.get("PROCESS_SIMULATOR_ENDPOINT", DEFAULT_ENDPOINT)
    maximum_age_seconds = float(
        os.environ.get("PROCESS_SIMULATOR_MAX_SAMPLE_AGE_SECONDS", "60")
    )
    async with Client(endpoint, timeout=3) as client:
        await client.nodes.server_state.read_value()
        namespace = await client.get_namespace_index(NAMESPACE_URI)
        value = await client.get_node(
            ua.NodeId(HEALTH_SIGNAL_NODE_ID, namespace)
        ).read_data_value()
        if not _source_is_fresh(
            value.SourceTimestamp,
            now=datetime.now(UTC),
            maximum_age_seconds=maximum_age_seconds,
        ):
            raise RuntimeError("representative simulator value is stale")


def main() -> int:
    try:
        asyncio.run(_check())
    except (OSError, RuntimeError, TimeoutError, UaError, ValueError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
