"""One-at-a-time sensitivity analysis for preliminary sizing."""

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from .energy import calculate_energy_demand
from .parameters import DrivetrainEfficiencies, SizingParameters, VehicleParameters
from .profiles import VelocityProfile


@dataclass(frozen=True)
class SensitivityPoint:
    parameter: str
    factor: float
    energy_wh: float
    specific_energy_wh_km: float
    minimum_nominal_energy_wh: float


def run_sensitivity(
    profile: VelocityProfile,
    vehicle: VehicleParameters,
    efficiencies: DrivetrainEfficiencies,
    sizing: SizingParameters,
    factors: Mapping[str, Sequence[float]],
) -> tuple[SensitivityPoint, ...]:
    """Vary one parameter at a time around the supplied baseline."""
    supported = {
        "mass": ("vehicle", "mass_kg"),
        "drag_coefficient": ("vehicle", "drag_coefficient"),
        "rolling_resistance": ("vehicle", "rolling_resistance_coefficient"),
        "motor_efficiency": ("efficiency", "motor"),
    }
    points = []
    for parameter, parameter_factors in factors.items():
        if parameter not in supported:
            raise ValueError(f"unsupported sensitivity parameter: {parameter}")
        owner, field = supported[parameter]
        for factor in parameter_factors:
            if factor <= 0.0:
                raise ValueError("sensitivity factors must be positive")
            local_vehicle = vehicle
            local_efficiencies = efficiencies
            if owner == "vehicle":
                local_vehicle = replace(
                    vehicle, **{field: getattr(vehicle, field) * factor})
            else:
                varied = getattr(efficiencies, field) * factor
                if varied > 1.0:
                    raise ValueError(
                        f"{parameter} factor produces efficiency above 1")
                local_efficiencies = replace(efficiencies, **{field: varied})
            result = calculate_energy_demand(
                profile, local_vehicle, local_efficiencies, sizing)
            points.append(SensitivityPoint(
                parameter=parameter,
                factor=float(factor),
                energy_wh=result.energy_wh,
                specific_energy_wh_km=result.specific_energy_wh_km,
                minimum_nominal_energy_wh=result.minimum_nominal_energy_wh,
            ))
    return tuple(points)
