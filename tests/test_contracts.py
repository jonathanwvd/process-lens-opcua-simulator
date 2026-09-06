import copy
import csv
import json
from datetime import datetime
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from process_lens_opcua_simulator import __version__
from process_lens_opcua_simulator.cli import main
from process_lens_opcua_simulator.contracts import (
    ContractValidationError,
    build_benchmark_manifest,
    document_digest,
    load_benchmark_manifest,
    validate_benchmark_manifest,
    validate_dataset_manifest,
    write_benchmark_manifest,
)
from process_lens_opcua_simulator.dataset import generate_dataset
from process_lens_opcua_simulator.engine import PlantSimulator
from process_lens_opcua_simulator.profiles import PROFILE_IDS, load_runtime_profiles
from process_lens_opcua_simulator.server import CHECKPOINT_SCHEMA


def _validate_schema(filename: str, value: object) -> None:
    root = files("process_lens_opcua_simulator").joinpath("schemas", "v1")
    schema_path = Path(str(root.joinpath(filename)))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    resources = []
    for candidate in Path(str(root)).glob("*.schema.json"):
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        resources.append((payload["$id"], Resource.from_contents(payload)))
    validator = Draft202012Validator(schema, registry=Registry().with_resources(resources))
    validator.validate(value)


def test_package_version_is_independent_from_benchmark_identity() -> None:
    assert __version__ == version("process-lens-opcua-simulator") == "0.3.7"


def test_all_bundled_json_schemas_are_valid() -> None:
    root = files("process_lens_opcua_simulator").joinpath("schemas", "v1")
    for candidate in Path(str(root)).glob("*.schema.json"):
        Draft202012Validator.check_schema(
            json.loads(candidate.read_text(encoding="utf-8"))
        )


def test_benchmark_manifest_is_schema_valid_and_byte_stable(tmp_path: Path) -> None:
    manifest = build_benchmark_manifest()
    _validate_schema("benchmark-manifest.schema.json", manifest)

    first = tmp_path / "a" / "benchmark.json"
    second = tmp_path / "b" / "benchmark.json"
    first_digest = write_benchmark_manifest(first, manifest)
    second_digest = write_benchmark_manifest(second, manifest)

    assert first.read_bytes() == second.read_bytes()
    assert first_digest == second_digest == document_digest(manifest)
    assert first_digest == "sha256:90ba4be9f5c743c434ae75be3d90cfb53bd925a795f4a7c890bd62ee23afc673"
    assert load_benchmark_manifest(first) == manifest
    assert manifest["catalog_digest"].startswith("sha256:")


def test_cli_exports_and_validates_the_release_manifest(tmp_path: Path) -> None:
    path = tmp_path / "benchmark.json"
    assert main(["export-manifest", "--output", str(path)]) == 0
    assert main(["validate-manifest", str(path)]) == 0


@pytest.mark.parametrize(
    "mutation",
    ["missing", "version", "digest", "duplicate", "model", "scenario", "profile"],
)
def test_incompatible_benchmark_manifests_fail_before_runtime(mutation: str) -> None:
    manifest = copy.deepcopy(build_benchmark_manifest())
    if mutation == "missing":
        del manifest["signals"]
    elif mutation == "version":
        manifest["benchmark_version"] = "9.0.0"
    elif mutation == "digest":
        manifest["catalog_digest"] = "sha256:" + "0" * 64
    elif mutation == "duplicate":
        manifest["loops"][1] = copy.deepcopy(manifest["loops"][0])
    elif mutation == "model":
        manifest["loop_models"][0]["parameters"]["process_gain"] = 99.0
    elif mutation == "scenario":
        manifest["scenario_parameterizations"][0]["parameters"] = {"unknown": 1.0}
    else:
        manifest["runtime_profiles"][0]["profile_id"] = "unknown"

    with pytest.raises(ContractValidationError):
        validate_benchmark_manifest(manifest)


def test_runtime_profiles_are_exact_and_schema_valid() -> None:
    profiles = load_runtime_profiles()
    assert tuple(item.profile_id for item in profiles) == PROFILE_IDS
    for profile in profiles:
        _validate_schema("runtime-profile.schema.json", profile.to_dict())


def test_server_checkpoint_schema_closes_restart_identity() -> None:
    _validate_schema(
        "server-checkpoint.schema.json",
        {
            "schema": CHECKPOINT_SCHEMA,
            "benchmark_version": "0.3.0",
            "namespace_uri": (
                "https://github.com/jonathanwvd/process-lens-opcua-simulator"
            ),
            "catalog_digest": "sha256:" + "0" * 64,
            "seed": 31,
            "start_at": "2026-01-01T00:00:00+00:00",
            "elapsed_seconds": 600.0,
            "integration_step_seconds": 1.0,
            "sample_seconds": 30.0,
            "scenario_cycle_seconds": 600.0,
        },
    )


def test_dataset_manifest_is_reproducible_and_schema_valid(tmp_path: Path) -> None:
    reports = []
    for directory in (tmp_path / "first", tmp_path / "second"):
        reports.append(
            generate_dataset(
                directory / "observations.csv",
                directory / "truth.jsonl",
                manifest_output=directory / "dataset.json",
                duration_seconds=60,
                sample_seconds=30,
                seed=42,
            )
        )

    first, second = reports
    assert first["dataset_manifest_digest"] == second["dataset_manifest_digest"]
    assert first["dataset_manifest_digest"] == (
        "sha256:1ce7dc41c863a8914cc05baab4b80e257202442e5adca5383be82408b01dee8c"
    )
    assert (tmp_path / "first/dataset.json").read_bytes() == (
        tmp_path / "second/dataset.json"
    ).read_bytes()
    manifest = json.loads((tmp_path / "first/dataset.json").read_text(encoding="utf-8"))
    assert validate_dataset_manifest(manifest) == manifest
    _validate_schema("dataset-manifest.schema.json", manifest)

    with (tmp_path / "first/observations.csv").open(encoding="utf-8", newline="") as stream:
        observation = next(csv.DictReader(stream))
    _validate_schema("observation.schema.json", observation)
    truth = json.loads((tmp_path / "first/truth.jsonl").read_text().splitlines()[0])
    _validate_schema("truth-frame.schema.json", truth)


def test_time_and_interval_semantics_reject_implicit_corrections(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        PlantSimulator(start_at=datetime(2026, 1, 1))  # noqa: DTZ001
    simulator = PlantSimulator()
    with pytest.raises(ValueError, match="non-negative"):
        simulator.advance(-1)
    with pytest.raises(ValueError, match="divisible"):
        generate_dataset(
            tmp_path / "observations.csv",
            tmp_path / "truth.jsonl",
            duration_seconds=61,
            sample_seconds=30,
            seed=1,
        )


def test_dataset_manifest_rejects_naive_time_and_unknown_fields(tmp_path: Path) -> None:
    report = generate_dataset(
        tmp_path / "observations.csv",
        tmp_path / "truth.jsonl",
        duration_seconds=30,
        sample_seconds=30,
        seed=1,
    )
    manifest = {
        key: value
        for key, value in report.items()
        if key
        not in {
            "dataset_manifest_digest",
            "manifest_output",
            "output",
            "truth_output",
        }
    }
    manifest["start_at"] = "2026-01-01T00:00:00"
    with pytest.raises(ContractValidationError, match="UTC offset"):
        validate_dataset_manifest(manifest)
    manifest["start_at"] = "2026-01-01T00:00:00+00:00"
    manifest["unexpected"] = True
    with pytest.raises(ContractValidationError, match="exact v1 fields"):
        validate_dataset_manifest(manifest)
