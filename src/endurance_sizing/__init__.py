"""Preliminary energy sizing tools for a Formula SAE Electric endurance."""

from .energy import EnergyResult, calculate_energy_demand
from .pack_sizing import PackAssessment, assess_pack, enumerate_energy_candidates
from .parameters import (
    CellSpecifications,
    DrivetrainEfficiencies,
    PackConfiguration,
    SizingParameters,
    VehicleParameters,
)
from .profiles import VelocityProfile, build_hypothetical_endurance_cycle

__all__ = [
    "CellSpecifications",
    "DrivetrainEfficiencies",
    "EnergyResult",
    "PackAssessment",
    "PackConfiguration",
    "SizingParameters",
    "VehicleParameters",
    "VelocityProfile",
    "assess_pack",
    "build_hypothetical_endurance_cycle",
    "calculate_energy_demand",
    "enumerate_energy_candidates",
]
