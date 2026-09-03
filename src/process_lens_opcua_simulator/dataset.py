"""Streaming export of observations and hidden benchmark truth."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .engine import PlantSimulator


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_dataset(
    output: str | Path,
    truth_output: str | Path,
    *,
    duration_seconds: float,
    sample_seconds: float,
    seed: int,
    start_at: datetime | None = None,
) -> dict[str, object]:
    """Generate a long-form CSV plus a deliberately separate truth JSONL file."""

    output_path = Path(output).resolve()
    truth_path = Path(truth_output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    simulator = PlantSimulator(seed=seed, start_at=start_at or datetime(2026, 1, 1, tzinfo=UTC))
    observation_count = 0
    frame_count = 0
    with (
        output_path.open("w", encoding="utf-8", newline="") as data_stream,
        truth_path.open("w", encoding="utf-8", newline="") as truth_stream,
    ):
        writer = csv.DictWriter(
            data_stream,
            fieldnames=(
                "timestamp",
                "signal_id",
                "node_id",
                "value",
                "quality",
                "engineering_unit",
            ),
        )
        writer.writeheader()
        elapsed = 0.0
        while elapsed < duration_seconds - 1e-12:
            step = min(sample_seconds, duration_seconds - elapsed)
            frame = simulator.advance(step)
            frame_count += 1
            elapsed += step
            for observation in frame.observations:
                row = {
                    "timestamp": observation.timestamp.isoformat(),
                    "signal_id": observation.signal_id,
                    "node_id": observation.node_id,
                    "value": observation.value,
                    "quality": observation.quality,
                    "engineering_unit": observation.engineering_unit,
                }
                writer.writerow(row)
                observation_count += 1
            truth_row = {
                "timestamp": frame.timestamp.isoformat(),
                "state_digest": frame.state_digest,
                "loops": simulator.truth_state(),
                "transitions": [asdict(event) for event in frame.truth_events],
            }
            encoded_truth = json.dumps(truth_row, sort_keys=True, ensure_ascii=False)
            truth_stream.write(encoded_truth + "\n")
    observation_hash = _file_digest(output_path)
    truth_hash = _file_digest(truth_path)
    return {
        "seed": seed,
        "duration_seconds": duration_seconds,
        "sample_seconds": sample_seconds,
        "frames": frame_count,
        "observations": observation_count,
        "catalog_digest": simulator.catalog.digest,
        "observation_digest": observation_hash,
        "truth_digest": truth_hash,
        "output": str(output_path),
        "truth_output": str(truth_path),
    }
