"""Numerical parameterization for the grey-box plant model.

All dynamic states are normalized before conversion to engineering units.  This
keeps the benchmark readable while the catalog retains physical names, units,
and normal ranges.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import pairwise

from .catalog import Catalog, LoopDefinition


@dataclass(frozen=True)
class LoopParameters:
    process_gain: float
    time_constant_seconds: float
    dead_time_seconds: float
    controller_gain: float
    integral_time_seconds: float
    actuator_time_seconds: float
    noise_standard_deviation: float
    lower_limit: float = 0.0
    upper_limit: float = 1.0


@dataclass(frozen=True)
class CouplingEdge:
    source_loop_id: str
    target_loop_id: str
    gain: float
    delay_seconds: float
    mechanism: str


_KIND_PARAMETERS: dict[str, LoopParameters] = {
    "flow": LoopParameters(0.82, 65.0, 6.0, 1.15, 55.0, 5.0, 0.0025),
    "pressure": LoopParameters(0.70, 105.0, 12.0, 1.25, 80.0, 7.0, 0.0020),
    "temperature": LoopParameters(0.58, 310.0, 35.0, 1.05, 220.0, 12.0, 0.0015),
    "level": LoopParameters(0.42, 420.0, 8.0, 0.70, 360.0, 8.0, 0.0012),
    "analyzer": LoopParameters(0.45, 480.0, 75.0, 0.85, 420.0, 15.0, 0.0030),
    "ratio": LoopParameters(0.76, 95.0, 10.0, 1.00, 80.0, 6.0, 0.0020),
    "speed": LoopParameters(0.88, 45.0, 4.0, 1.10, 35.0, 3.0, 0.0015),
}


def parameters_for(loop: LoopDefinition) -> LoopParameters:
    """Return transparent, deterministic parameters for a loop class."""

    base = _KIND_PARAMETERS[loop.loop_kind]
    digest = hashlib.sha256(loop.loop_id.encode()).digest()
    spread = (digest[0] / 255.0) - 0.5
    time_scale = 1.0 + 0.24 * spread
    gain_scale = 1.0 + 0.16 * ((digest[1] / 255.0) - 0.5)
    controller_scale = 1.0
    integral_scale = 1.0
    if loop.primary_scenario == "control.aggressive_tuning":
        controller_scale = 2.1
        integral_scale = 0.55
    elif loop.primary_scenario == "control.sluggish_tuning":
        controller_scale = 0.38
        integral_scale = 2.4
    elif loop.primary_scenario in {"control.oscillation", "control.propagated_oscillation"}:
        controller_scale = 1.75
        integral_scale = 0.72
    return LoopParameters(
        process_gain=base.process_gain * gain_scale,
        time_constant_seconds=base.time_constant_seconds * time_scale,
        dead_time_seconds=base.dead_time_seconds,
        controller_gain=base.controller_gain * controller_scale,
        integral_time_seconds=base.integral_time_seconds * integral_scale,
        actuator_time_seconds=base.actuator_time_seconds,
        noise_standard_deviation=base.noise_standard_deviation,
    )


def build_coupling_graph(catalog: Catalog) -> tuple[CouplingEdge, ...]:
    """Build a sparse declared plant-wide graph from process order and utilities."""

    by_area: dict[str, list[str]] = {}
    for loop in catalog.loops:
        by_area.setdefault(loop.area_code, []).append(loop.loop_id)
    edges: list[CouplingEdge] = []
    for area, loop_ids in by_area.items():
        for source, target in pairwise(loop_ids):
            edges.append(CouplingEdge(source, target, 0.035, 45.0, f"within_{area.lower()}"))
    cross_area = (
        ("FIC-101", "FIC-201", 0.085, 90.0, "feed_to_distillation"),
        ("FIC-201", "FIC-301", 0.060, 180.0, "distillation_to_hydrotreating"),
        ("FIC-301", "FIC-403", 0.055, 120.0, "hydrogen_demand"),
        ("AIC-405", "AIC-307", 0.045, 240.0, "hydrogen_purity_to_product_quality"),
        ("PIC-502", "TIC-104", 0.050, 75.0, "fuel_header_to_furnace"),
        ("PIC-601", "TIC-204", 0.050, 100.0, "steam_header_to_reboiler"),
        ("FIC-701", "PIC-202", -0.055, 80.0, "cooling_water_to_column_pressure"),
        ("PIC-703", "LIC-103", 0.050, 40.0, "instrument_air_to_valve_response"),
        ("FIC-901", "AIC-904", 0.045, 300.0, "wastewater_load_to_quality"),
        ("PIC-1001", "LIC-1002", 0.055, 30.0, "flare_load_to_knockout_drum"),
    )
    edges.extend(CouplingEdge(*edge) for edge in cross_area)
    return tuple(edges)
