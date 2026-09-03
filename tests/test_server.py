import asyncio
import socket
from pathlib import Path

from asyncua import Client, ua
from process_lens_opcua_simulator.server import NAMESPACE_URI, OpcUaPlantServer


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_opcua_server_publishes_all_nodes_and_supports_current_reads(tmp_path: Path) -> None:
    async def exercise() -> tuple[int, float, str]:
        port = _free_port()
        endpoint = f"opc.tcp://127.0.0.1:{port}/process-plant-simulator/"
        server = OpcUaPlantServer(
            endpoint=endpoint,
            history_db=tmp_path / "history.sqlite3",
            history_hours=0,
            sample_seconds=1,
            reset=True,
        )
        await server.start()
        try:
            async with Client(endpoint, timeout=3) as client:
                namespace = await client.get_namespace_index(NAMESPACE_URI)
                node = client.get_node(ua.NodeId("Plant.ControlLoops.FIC-101.PV", namespace))
                value = await node.read_value()
                unit_children = await node.get_properties()
                properties = {
                    await item.read_browse_name(): await item.read_value() for item in unit_children
                }
                engineering_unit = next(
                    value for name, value in properties.items() if name.Name == "EngineeringUnit"
                )
                return len(server.nodes), float(value), str(engineering_unit)
        finally:
            await server.stop()

    node_count, value, engineering_unit = asyncio.run(exercise())
    assert node_count == 500
    assert value >= 0
    assert engineering_unit == "m³/h"
