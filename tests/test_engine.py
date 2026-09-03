from datetime import UTC, datetime
from math import isfinite

from process_lens_opcua_simulator import PlantSimulator, load_catalog
from process_lens_opcua_simulator.engine import SUPPORTED_SCENARIOS


def test_simulation_is_bitwise_reproducible_for_same_inputs() -> None:
    first = PlantSimulator(seed=17)
    second = PlantSimulator(seed=17)

    for step in (1, 9, 30, 120, 600):
        left = first.advance(step)
        right = second.advance(step)
        assert left == right
        assert left.state_digest == right.state_digest


def test_different_seeds_change_measurements_not_catalog() -> None:
    first = PlantSimulator(seed=17)
    second = PlantSimulator(seed=18)

    left = first.advance(30)
    right = second.advance(30)
    assert left.state_digest != right.state_digest
    assert first.catalog.digest == second.catalog.digest


def test_values_are_typed_finite_and_bounded_by_extended_model_domain() -> None:
    simulator = PlantSimulator(seed=7)
    frame = simulator.advance(1_000)

    assert frame.observations
    for observation in frame.observations:
        if isinstance(observation.value, float):
            assert isfinite(observation.value)
    for state in simulator.truth_state().values():
        assert -0.05 <= float(state["true_pv_normalized"]) <= 1.05
        assert -0.05 <= float(state["measured_pv_normalized"]) <= 1.05
        assert 0.0 <= float(state["controller_output_normalized"]) <= 1.0
        assert 0.0 <= float(state["actuator_position_normalized"]) <= 1.0


def test_fault_truth_is_separate_from_observations() -> None:
    simulator = PlantSimulator(
        seed=5,
        start_at=datetime(2026, 1, 1, tzinfo=UTC),
        scenario_cycle_seconds=3_600,
    )
    frame = simulator.advance(1_100)
    truth = simulator.truth_state()

    assert truth["LIC-103"]["scenario_active"] is True
    assert truth["LIC-205"]["mode"] == "MAN"
    assert not any(
        "scenario" in observation.signal_id.lower() for observation in frame.observations
    )
    assert not any("truth" in observation.node_id.lower() for observation in frame.observations)


def test_data_failure_scenarios_affect_transport_semantics() -> None:
    simulator = PlantSimulator(seed=5, scenario_cycle_seconds=3_600)
    frame = simulator.advance(1_110)
    by_loop = {
        loop.loop_id: {
            signal.signal_id
            for signal in simulator.catalog.signals
            if signal.loop_id == loop.loop_id
        }
        for loop in simulator.catalog.loops
    }
    observed = {item.signal_id for item in frame.observations}

    assert not (by_loop["AIC-105"] & observed)
    bad_ids = by_loop["PIC-605"] & observed
    assert bad_ids
    assert all(item.quality == "BAD" for item in frame.observations if item.signal_id in bad_ids)


def test_coupling_graph_is_sparse_directed_and_crosses_plant_areas() -> None:
    simulator = PlantSimulator()
    catalog = load_catalog()
    areas = {loop.loop_id: loop.area_code for loop in catalog.loops}

    assert 40 <= len(simulator.coupling_edges) < 100
    assert any(
        areas[edge.source_loop_id] != areas[edge.target_loop_id]
        for edge in simulator.coupling_edges
    )
    assert all(abs(edge.gain) <= 0.1 for edge in simulator.coupling_edges)
    assert all(edge.delay_seconds > 0 for edge in simulator.coupling_edges)


def test_every_declared_scenario_has_an_implementation_path() -> None:
    catalog = load_catalog()
    assert {item.scenario_id for item in catalog.scenarios} == SUPPORTED_SCENARIOS
