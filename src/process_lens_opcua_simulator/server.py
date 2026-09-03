"""OPC UA Data Access and Historical Access surface for all 500 signals."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from asyncua import Server, ua

from .catalog import SignalDefinition, load_catalog
from .engine import Observation, PlantSimulator, SimulationFrame
from .storage import BulkHistorySQLite

LOGGER = logging.getLogger(__name__)
NAMESPACE_URI = "https://github.com/jonathanwvd/process-lens-opcua-simulator"
DEFAULT_ENDPOINT = "opc.tcp://127.0.0.1:4840/process-plant-simulator/"


def _variant_type(signal: SignalDefinition) -> ua.VariantType:
    return {
        "number": ua.VariantType.Double,
        "string": ua.VariantType.String,
        "boolean": ua.VariantType.Boolean,
    }[signal.data_type]


def _status_code(quality: str) -> ua.StatusCode:
    return {
        "GOOD": ua.StatusCode(ua.StatusCodes.Good),
        "UNCERTAIN": ua.StatusCode(ua.StatusCodes.Uncertain),
        "BAD": ua.StatusCode(ua.StatusCodes.Bad),
        "BAD_NO_COMMUNICATION": ua.StatusCode(ua.StatusCodes.BadNoCommunication),
    }[quality]


def _data_value(observation: Observation, signal: SignalDefinition) -> ua.DataValue:
    stamp = observation.timestamp.astimezone(UTC).replace(tzinfo=None)
    return ua.DataValue(
        ua.Variant(observation.value, _variant_type(signal)),
        StatusCode_=_status_code(observation.quality),
        SourceTimestamp=stamp,
        ServerTimestamp=stamp,
    )


class OpcUaPlantServer:
    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        history_db: str | Path = "var/history.sqlite3",
        history_hours: float = 1.0,
        sample_seconds: float = 10.0,
        seed: int = 20260903,
        reset: bool = False,
    ) -> None:
        self.endpoint = endpoint
        self.history_db = Path(history_db).expanduser().resolve()
        self.history_hours = max(float(history_hours), 0.0)
        self.sample_seconds = max(float(sample_seconds), 1.0)
        self.seed = int(seed)
        self.reset = reset
        self.catalog = load_catalog()
        self.signal_by_id = {item.signal_id: item for item in self.catalog.signals}
        self.server: Server | None = None
        self.history: BulkHistorySQLite | None = None
        self.nodes: dict[str, Any] = {}
        self.simulator: PlantSimulator | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.history_db.parent.mkdir(parents=True, exist_ok=True)
        if self.reset:
            self.history_db.unlink(missing_ok=True)
        server = Server()
        await server.init()
        server.set_endpoint(self.endpoint)
        server.set_server_name("Integrated Process Plant Scientific Benchmark")
        server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        namespace = await server.register_namespace(NAMESPACE_URI)
        history = BulkHistorySQLite(self.history_db)
        await history.init()
        server.iserver.history_manager.set_storage(history)
        self.server = server
        self.history = history
        await self._create_address_space(namespace)
        now = datetime.now(UTC).replace(microsecond=0)
        start = now - timedelta(hours=self.history_hours)
        self.simulator = PlantSimulator(seed=self.seed, start_at=start)
        await self._prepare_history()
        await server.start()
        self._task = asyncio.create_task(self._realtime_loop())
        LOGGER.info("OPC UA server ready at %s with %d signals", self.endpoint, len(self.nodes))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self.server:
            await self.server.stop()
        if self.history:
            await self.history.stop()

    async def _create_address_space(self, namespace: int) -> None:
        assert self.server is not None
        root = await self.server.nodes.objects.add_object(namespace, "Plant")
        areas = await root.add_object(namespace, "Areas")
        loops = await root.add_object(namespace, "ControlLoops")
        area_nodes: dict[str, Any] = {}
        equipment_nodes: dict[tuple[str, str], Any] = {}
        loop_nodes: dict[str, Any] = {}
        for signal in self.catalog.signals:
            if signal.scope == "control_loop":
                parent = loop_nodes.get(signal.equipment_id)
                if parent is None:
                    parent = await loops.add_object(namespace, signal.equipment_id)
                    loop_nodes[signal.equipment_id] = parent
            else:
                area_parent = area_nodes.get(signal.area_code)
                if area_parent is None:
                    area_parent = await areas.add_object(namespace, signal.area_code)
                    area_nodes[signal.area_code] = area_parent
                key = (signal.area_code, signal.equipment_id)
                parent = equipment_nodes.get(key)
                if parent is None:
                    parent = await area_parent.add_object(namespace, signal.equipment_id)
                    equipment_nodes[key] = parent
            initial: float | str | bool = 0.0
            if signal.data_type == "string":
                initial = "NORMAL"
            elif signal.data_type == "boolean":
                initial = True
            node = await parent.add_variable(
                ua.NodeId(signal.node_identifier, namespace),
                signal.node_identifier.rsplit(".", 1)[-1],
                ua.Variant(initial, _variant_type(signal)),
            )
            await node.add_property(namespace, "SignalId", signal.signal_id)
            await node.add_property(namespace, "EngineeringUnit", signal.engineering_unit)
            await node.add_property(namespace, "DescriptionPtBr", signal.description)
            self.nodes[signal.signal_id] = node

    async def _prepare_history(self) -> None:
        assert self.history is not None
        assert self.simulator is not None
        for node in self.nodes.values():
            await self.history.new_historized_node(node.nodeid, period=None, count=0)
        if self.history_hours <= 0:
            await self._write_frame(self.simulator.snapshot(), history=False)
            return
        frames = int(self.history_hours * 3600 / self.sample_seconds)
        pending: dict[str, list[ua.DataValue]] = defaultdict(list)
        for _ in range(frames):
            frame = self.simulator.advance(self.sample_seconds)
            for observation in frame.observations:
                signal = self.signal_by_id[observation.signal_id]
                pending[observation.signal_id].append(_data_value(observation, signal))
            if sum(map(len, pending.values())) >= 20_000:
                await self._flush(pending)
        await self._flush(pending)
        await self._write_frame(self.simulator.snapshot(), history=False)

    async def _flush(self, pending: dict[str, list[ua.DataValue]]) -> None:
        assert self.history is not None
        for signal_id, values in pending.items():
            await self.history.save_node_values(self.nodes[signal_id].nodeid, values, commit=False)
        await self.history.commit_pending()
        pending.clear()

    async def _write_frame(self, frame: SimulationFrame, *, history: bool) -> None:
        assert self.history is not None
        for observation in frame.observations:
            signal = self.signal_by_id[observation.signal_id]
            value = _data_value(observation, signal)
            await self.nodes[observation.signal_id].write_value(value)
            if history:
                await self.history.save_node_values(
                    self.nodes[observation.signal_id].nodeid,
                    (value,),
                )

    async def _realtime_loop(self) -> None:
        assert self.simulator is not None
        while True:
            started = asyncio.get_running_loop().time()
            await self._write_frame(self.simulator.advance(self.sample_seconds), history=True)
            elapsed = asyncio.get_running_loop().time() - started
            await asyncio.sleep(max(self.sample_seconds - elapsed, 0.05))
