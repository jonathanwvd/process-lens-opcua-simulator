"""Public API for the integrated process-plant benchmark."""

from .catalog import Catalog, load_catalog
from .contracts import BENCHMARK_VERSION, build_benchmark_manifest
from .engine import Observation, PlantSimulator, SimulationFrame, TruthEvent
from .profiles import RuntimeProfile, get_runtime_profile, load_runtime_profiles

__all__ = [
    "Catalog",
    "Observation",
    "PlantSimulator",
    "RuntimeProfile",
    "SimulationFrame",
    "TruthEvent",
    "build_benchmark_manifest",
    "get_runtime_profile",
    "load_catalog",
    "load_runtime_profiles",
]

__version__ = BENCHMARK_VERSION
