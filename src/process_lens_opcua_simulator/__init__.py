"""Public API for the integrated process-plant benchmark."""

from .catalog import Catalog, load_catalog
from .engine import Observation, PlantSimulator, SimulationFrame, TruthEvent

__all__ = [
    "Catalog",
    "Observation",
    "PlantSimulator",
    "SimulationFrame",
    "TruthEvent",
    "load_catalog",
]

__version__ = "0.2.0"
