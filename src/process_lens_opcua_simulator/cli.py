"""Command-line interface for catalog, dataset, and OPC UA operation."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime

from .catalog import load_catalog
from .dataset import generate_dataset
from .server import DEFAULT_ENDPOINT, OpcUaPlantServer


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="process-plant-simulator",
        description="Deterministic 500-signal plant-wide process-control benchmark",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate-catalog", help="validate the bundled 50-loop catalog")
    inspect_parser = subparsers.add_parser("inspect", help="print catalog metadata")
    inspect_parser.add_argument("--json", action="store_true", dest="as_json")

    generate = subparsers.add_parser("generate", help="generate observations and hidden truth")
    generate.add_argument("--output", default="var/observations.csv")
    generate.add_argument("--truth-output", default="var/truth.jsonl")
    generate.add_argument("--duration-hours", type=float, default=6.0)
    generate.add_argument("--sample-seconds", type=float, default=30.0)
    generate.add_argument("--seed", type=int, default=20260903)
    generate.add_argument("--start-at", type=datetime.fromisoformat)

    serve = subparsers.add_parser("serve", help="serve the benchmark through OPC UA")
    serve.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    serve.add_argument("--history-db", default="var/history.sqlite3")
    serve.add_argument("--history-hours", type=float, default=1.0)
    serve.add_argument("--sample-seconds", type=float, default=10.0)
    serve.add_argument("--seed", type=int, default=20260903)
    serve.add_argument("--reset", action="store_true")
    return parser


async def _serve(args: argparse.Namespace) -> None:
    server = OpcUaPlantServer(
        endpoint=args.endpoint,
        history_db=args.history_db,
        history_hours=args.history_hours,
        sample_seconds=args.sample_seconds,
        seed=args.seed,
        reset=args.reset,
    )
    await server.start()
    try:
        await asyncio.Event().wait()
    finally:
        await server.stop()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    catalog = load_catalog()
    if args.command == "validate-catalog":
        errors = catalog.validate()
        if errors:
            for error in errors:
                print(error)
            return 1
        print(
            f"PASS: {len(catalog.loops)} loops, {len(catalog.signals)} signals, "
            f"{len(catalog.scenarios)} scenarios, digest={catalog.digest}"
        )
        return 0
    if args.command == "inspect":
        summary = {
            "loops": len(catalog.loops),
            "signals": len(catalog.signals),
            "scenarios": len(catalog.scenarios),
            "areas": sorted({item.area_code for item in catalog.loops}),
            "catalog_digest": catalog.digest,
        }
        print(json.dumps(summary, indent=2 if args.as_json else None))
        return 0
    if args.command == "generate":
        report = generate_dataset(
            args.output,
            args.truth_output,
            duration_seconds=args.duration_hours * 3600.0,
            sample_seconds=args.sample_seconds,
            seed=args.seed,
            start_at=args.start_at,
        )
        print(json.dumps(report, indent=2))
        return 0
    if args.command == "serve":
        try:
            asyncio.run(_serve(args))
        except KeyboardInterrupt:
            return 0
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
