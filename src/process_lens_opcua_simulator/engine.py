"""Deterministic plant-wide simulation and observation pipeline."""

from __future__ import annotations

import hashlib
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal

from .catalog import Catalog, LoopDefinition, SignalDefinition, load_catalog
from .model import CouplingEdge, build_coupling_graph, parameters_for

Quality = Literal["GOOD", "UNCERTAIN", "BAD", "BAD_NO_COMMUNICATION"]

SUPPORTED_SCENARIOS = frozenset(
    {
        "normal.steady",
        "normal.load_change",
        "control.aggressive_tuning",
        "control.sluggish_tuning",
        "control.oscillation",
        "control.propagated_oscillation",
        "valve.stiction",
        "valve.backlash",
        "actuator.saturation",
        "operations.manual",
        "operations.setpoint_activity",
        "sensor.noise",
        "sensor.drift",
        "sensor.frozen",
        "data.gap",
        "data.bad_quality",
        "data.communication_loss",
        "data.irregular_cadence",
        "process.disturbance",
        "process.interaction",
    }
)


@dataclass(frozen=True)
class Observation:
    signal_id: str
    node_id: str
    timestamp: datetime
    value: float | str | bool
    quality: Quality
    engineering_unit: str


@dataclass(frozen=True)
class TruthEvent:
    scenario_id: str
    loop_id: str
    cycle: int
    active: bool
    elapsed_seconds: float
    parameters: tuple[tuple[str, float | str], ...] = ()


@dataclass(frozen=True)
class SimulationFrame:
    timestamp: datetime
    observations: tuple[Observation, ...]
    truth_events: tuple[TruthEvent, ...]
    state_digest: str


@dataclass
class _LoopState:
    true_pv: float = 0.55
    measured_pv: float = 0.55
    setpoint: float = 0.55
    integral: float = 0.0
    output: float = 0.50
    actuator: float = 0.50
    mode: str = "AUTO"
    sensor_bias: float = 0.0
    frozen_measurement: float | None = None
    delay: deque[tuple[float, float]] = field(default_factory=deque)


def _stable_fraction(*parts: object) -> float:
    encoded = "|".join(str(part) for part in parts).encode()
    raw = int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")
    return raw / float(2**64 - 1)


def _gaussian(seed: int, step: int, channel: str) -> float:
    u1 = max(_stable_fraction(seed, step, channel, 1), 1e-12)
    u2 = _stable_fraction(seed, step, channel, 2)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _bounded(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return min(max(value, low), high)


def _numeric_range(signal: SignalDefinition) -> tuple[float, float]:
    try:
        left, right = signal.normal_range.split("..", 1)
        return float(left), float(right)
    except (TypeError, ValueError):
        return 0.0, 100.0


class PlantSimulator:
    """A reproducible, sparse-coupled, nonlinear grey-box benchmark.

    The process model uses normalized first-order-plus-dead-time states, PI
    controllers with conditional-integration anti-windup, first-order
    actuators, and a sparse directed coupling graph. Measurement and transport
    faults are applied after physical-state integration so hidden truth remains
    distinct from observable data.
    """

    def __init__(
        self,
        *,
        catalog: Catalog | None = None,
        seed: int = 20260903,
        start_at: datetime | None = None,
        integration_step_seconds: float = 1.0,
        scenario_cycle_seconds: float = 21_600.0,
    ) -> None:
        self.catalog = catalog or load_catalog()
        errors = self.catalog.validate()
        if errors:
            raise ValueError("invalid catalog: " + "; ".join(errors))
        scenario_ids = {item.scenario_id for item in self.catalog.scenarios}
        if scenario_ids != SUPPORTED_SCENARIOS:
            raise ValueError(
                "scenario implementation mismatch: "
                f"missing={sorted(scenario_ids - SUPPORTED_SCENARIOS)}, "
                f"undeclared={sorted(SUPPORTED_SCENARIOS - scenario_ids)}"
            )
        self.seed = int(seed)
        self.start_at = (start_at or datetime(2026, 1, 1, tzinfo=UTC)).astimezone(UTC)
        self.integration_step_seconds = max(float(integration_step_seconds), 0.1)
        self.scenario_cycle_seconds = max(float(scenario_cycle_seconds), 600.0)
        self.elapsed_seconds = 0.0
        self._step_index = 0
        self._loops = {loop.loop_id: loop for loop in self.catalog.loops}
        self._parameters = {loop.loop_id: parameters_for(loop) for loop in self.catalog.loops}
        self._state = {loop.loop_id: _LoopState() for loop in self.catalog.loops}
        self._edges = build_coupling_graph(self.catalog)
        self._incoming: dict[str, list[CouplingEdge]] = {
            loop.loop_id: [] for loop in self.catalog.loops
        }
        for edge in self._edges:
            self._incoming[edge.target_loop_id].append(edge)
        self._signal_by_loop: dict[str, list[SignalDefinition]] = {}
        self._context_signals: list[SignalDefinition] = []
        for signal in self.catalog.signals:
            if signal.scope == "control_loop" and signal.loop_id:
                self._signal_by_loop.setdefault(signal.loop_id, []).append(signal)
            else:
                self._context_signals.append(signal)
        self._last_active: dict[str, bool] = {loop.loop_id: False for loop in self.catalog.loops}
        self._last_load_change = False

    @property
    def coupling_edges(self) -> tuple[CouplingEdge, ...]:
        return self._edges

    def _scenario_active(self, loop: LoopDefinition) -> tuple[bool, int, float]:
        cycle = int(self.elapsed_seconds // self.scenario_cycle_seconds)
        phase = (self.elapsed_seconds % self.scenario_cycle_seconds) / self.scenario_cycle_seconds
        offset = 0.08 * (_stable_fraction(loop.loop_id, "onset") - 0.5)
        active = (0.24 + offset) <= phase < (0.72 + offset)
        if loop.primary_scenario == "normal.steady":
            active = False
        return active, cycle, phase

    def _setpoint(self, loop: LoopDefinition, active: bool, phase: float) -> float:
        value = 0.55
        if loop.loop_id in {"FIC-101", "FIC-201", "FIC-301"} and self._load_change_active(phase):
            value += 0.08
        if loop.primary_scenario == "operations.setpoint_activity" and active:
            local = (phase - 0.24) / 0.48
            value += 0.10 * (2.0 * local - 1.0)
        return _bounded(value, 0.15, 0.90)

    @staticmethod
    def _load_change_active(phase: float) -> bool:
        return 0.45 <= phase < 0.68

    def _delayed_actuator(self, state: _LoopState, delay_seconds: float) -> float:
        target_time = self.elapsed_seconds - delay_seconds
        value = state.delay[0][1] if state.delay else state.actuator
        for stamp, candidate in state.delay:
            if stamp > target_time:
                break
            value = candidate
        while len(state.delay) > 2 and state.delay[1][0] < target_time - delay_seconds:
            state.delay.popleft()
        return value

    def _coupling(
        self,
        loop_id: str,
        active: bool,
        prior_state: dict[str, float],
    ) -> float:
        total = 0.0
        for edge in self._incoming[loop_id]:
            gain = edge.gain * (
                2.0
                if active and self._loops[loop_id].primary_scenario == "process.interaction"
                else 1.0
            )
            total += gain * (prior_state[edge.source_loop_id] - 0.55)
        return total

    def _advance_loop(
        self,
        loop: LoopDefinition,
        dt: float,
        prior_state: dict[str, float],
    ) -> None:
        state = self._state[loop.loop_id]
        params = self._parameters[loop.loop_id]
        active, _, phase = self._scenario_active(loop)
        state.setpoint = self._setpoint(loop, active, phase)
        state.mode = (
            "MAN"
            if loop.primary_scenario == "operations.manual" and active
            else (
                "CAS"
                if loop.control_structure in {"cascade_primary", "ratio_control", "three_element"}
                else "AUTO"
            )
        )

        measurement = state.true_pv
        noise_scale = params.noise_standard_deviation
        if loop.primary_scenario == "sensor.noise" and active:
            noise_scale *= 14.0
        if loop.primary_scenario == "sensor.drift" and active:
            state.sensor_bias += 0.000012 * dt
        else:
            state.sensor_bias *= math.exp(-dt / 1_800.0)
        measurement += state.sensor_bias + noise_scale * _gaussian(
            self.seed, self._step_index, loop.loop_id
        )
        if loop.primary_scenario == "sensor.frozen" and active:
            if state.frozen_measurement is None:
                state.frozen_measurement = state.measured_pv
            measurement = state.frozen_measurement
        else:
            state.frozen_measurement = None
        state.measured_pv = _bounded(measurement, -0.05, 1.05)

        error = state.setpoint - state.measured_pv
        if state.mode == "MAN":
            requested = 0.50 + 0.06 * math.sin(2.0 * math.pi * phase * 3.0)
        else:
            proposed_integral = (
                state.integral
                + (params.controller_gain / params.integral_time_seconds) * error * dt
            )
            requested = 0.50 + params.controller_gain * error + proposed_integral
            if 0.0 < requested < 1.0:
                state.integral = proposed_integral
        state.output = _bounded(requested)

        actuator_target = state.output
        if loop.primary_scenario == "actuator.saturation" and active:
            actuator_target = min(actuator_target, 0.67)
        delta = actuator_target - state.actuator
        if loop.primary_scenario == "valve.stiction" and active and abs(delta) < 0.055:
            delta = 0.0
        elif loop.primary_scenario == "valve.backlash" and active:
            deadband = 0.035
            delta = math.copysign(max(abs(delta) - deadband, 0.0), delta)
        state.actuator = _bounded(state.actuator + dt * delta / params.actuator_time_seconds)
        state.delay.append((self.elapsed_seconds, state.actuator))

        delayed = self._delayed_actuator(state, params.dead_time_seconds)
        disturbance = 0.0
        if active and loop.primary_scenario in {
            "control.oscillation",
            "control.propagated_oscillation",
        }:
            disturbance += 0.075 * math.sin(2.0 * math.pi * self.elapsed_seconds / 540.0)
        if active and loop.primary_scenario == "process.disturbance":
            disturbance += 0.085
        coupling = self._coupling(loop.loop_id, active, prior_state)
        equilibrium = 0.55 + params.process_gain * (delayed - 0.50) + disturbance + coupling
        state.true_pv = _bounded(
            state.true_pv + dt * (equilibrium - state.true_pv) / params.time_constant_seconds,
            -0.05,
            1.05,
        )

    def advance(self, seconds: float) -> SimulationFrame:
        """Advance physical time and return observations due at the final time."""

        remaining = max(float(seconds), 0.0)
        transitions: list[TruthEvent] = []
        while remaining > 1e-12:
            dt = min(remaining, self.integration_step_seconds)
            active_before = {
                loop.loop_id: self._scenario_active(loop)[0] for loop in self.catalog.loops
            }
            prior = {key: value.true_pv for key, value in self._state.items()}
            for loop in self.catalog.loops:
                self._advance_loop(loop, dt, prior)
            self.elapsed_seconds += dt
            self._step_index += 1
            remaining -= dt
            cycle = int(self.elapsed_seconds // self.scenario_cycle_seconds)
            phase = (
                self.elapsed_seconds % self.scenario_cycle_seconds
            ) / self.scenario_cycle_seconds
            load_change = self._load_change_active(phase)
            if load_change != self._last_load_change:
                transitions.extend(
                    TruthEvent(
                        scenario_id="normal.load_change",
                        loop_id=loop_id,
                        cycle=cycle,
                        active=load_change,
                        elapsed_seconds=self.elapsed_seconds,
                    )
                    for loop_id in ("FIC-101", "FIC-201", "FIC-301")
                )
            self._last_load_change = load_change
            for loop in self.catalog.loops:
                active, cycle, _ = self._scenario_active(loop)
                before = active_before[loop.loop_id]
                if active != before or active != self._last_active[loop.loop_id]:
                    transitions.append(
                        TruthEvent(
                            scenario_id=loop.primary_scenario,
                            loop_id=loop.loop_id,
                            cycle=cycle,
                            active=active,
                            elapsed_seconds=self.elapsed_seconds,
                        )
                    )
                self._last_active[loop.loop_id] = active
        timestamp = self.start_at + timedelta(seconds=self.elapsed_seconds)
        observations = self._observations(timestamp)
        digest_input = "|".join(
            f"{key}:{state.true_pv:.12f}:{state.output:.12f}:{state.actuator:.12f}"
            for key, state in sorted(self._state.items())
        )
        digest = hashlib.sha256(digest_input.encode()).hexdigest()
        return SimulationFrame(timestamp, observations, tuple(transitions), digest)

    def snapshot(self) -> SimulationFrame:
        return self.advance(0.0)

    def _loop_value(self, signal: SignalDefinition) -> float | str:
        assert signal.loop_id is not None
        state = self._state[signal.loop_id]
        suffix = signal.node_identifier.rsplit(".", 1)[-1]
        if suffix == "PV":
            normalized: float | str = state.measured_pv
        elif suffix == "SP":
            normalized = state.setpoint
        elif suffix == "OP":
            normalized = state.output
        elif suffix == "MVFB":
            normalized = state.actuator
        else:
            return state.mode
        low, high = _numeric_range(signal)
        return low + float(normalized) * (high - low)

    def _context_value(self, signal: SignalDefinition) -> float | str | bool:
        related = [self._state[item] for item in signal.context_for_loop_ids if item in self._state]
        normalized = sum(item.true_pv for item in related) / len(related) if related else 0.55
        channel = _stable_fraction(signal.signal_id, self._step_index)
        if signal.data_type == "boolean":
            return normalized > 0.12
        if signal.data_type == "string":
            options = signal.normal_range.split("|")
            return options[0] if options else "NORMAL"
        low, high = _numeric_range(signal)
        shaped = _bounded(normalized + 0.008 * (channel - 0.5))
        return low + shaped * (high - low)

    def _observations(self, timestamp: datetime) -> tuple[Observation, ...]:
        observations: list[Observation] = []
        elapsed = round(self.elapsed_seconds)
        for signal in self.catalog.signals:
            if elapsed and elapsed % signal.nominal_cadence_seconds != 0:
                continue
            loop = self._loops.get(signal.loop_id or "")
            active = self._scenario_active(loop)[0] if loop else False
            scenario = loop.primary_scenario if loop else ""
            if active and scenario in {"data.gap", "data.communication_loss"}:
                continue
            quality: Quality = "GOOD"
            if active and scenario == "data.bad_quality":
                quality = "BAD"
            observed_at = timestamp
            if active and scenario == "data.irregular_cadence":
                jitter = int(1 + 7 * _stable_fraction(signal.signal_id, elapsed))
                observed_at += timedelta(seconds=jitter)
                quality = "UNCERTAIN"
            value = (
                self._loop_value(signal)
                if signal.scope == "control_loop"
                else self._context_value(signal)
            )
            observations.append(
                Observation(
                    signal_id=signal.signal_id,
                    node_id=signal.opcua_node_id,
                    timestamp=observed_at,
                    value=value,
                    quality=quality,
                    engineering_unit=signal.engineering_unit,
                )
            )
        return tuple(observations)

    def truth_state(self) -> dict[str, dict[str, float | str | bool]]:
        """Return hidden state for benchmark scoring, never for OPC UA publication."""

        result: dict[str, dict[str, float | str | bool]] = {}
        for loop in self.catalog.loops:
            active, cycle, phase = self._scenario_active(loop)
            state = self._state[loop.loop_id]
            result[loop.loop_id] = {
                "scenario_id": loop.primary_scenario,
                "scenario_active": active,
                "load_change_active": (
                    loop.loop_id in {"FIC-101", "FIC-201", "FIC-301"}
                    and self._load_change_active(phase)
                ),
                "cycle": cycle,
                "cycle_phase": phase,
                "true_pv_normalized": state.true_pv,
                "measured_pv_normalized": state.measured_pv,
                "setpoint_normalized": state.setpoint,
                "controller_output_normalized": state.output,
                "actuator_position_normalized": state.actuator,
                "mode": state.mode,
            }
        return result
