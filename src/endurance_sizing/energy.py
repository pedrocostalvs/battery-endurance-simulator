from dataclasses import dataclass
from math import cos, sin

import numpy as np

from .parameters import DrivetrainEfficiencies, SizingParameters, VehicleParameters
from .profiles import VelocityProfile


@dataclass(frozen=True)
class EnergyResult:
    distance_m: float
    duration_s: float
    energy_wh: float
    energy_kwh: float
    specific_energy_wh_km: float
    peak_electrical_power_w: float
    mean_electrical_power_w: float
    required_usable_energy_wh: float
    minimum_nominal_energy_wh: float
    interval_time_s: np.ndarray
    acceleration_m_s2: np.ndarray
    inertial_force_n: np.ndarray
    rolling_force_n: np.ndarray
    aerodynamic_force_n: np.ndarray
    grade_force_n: np.ndarray
    wheel_power_w: np.ndarray
    electrical_power_w: np.ndarray


def calculate_energy_demand(
    profile: VelocityProfile,
    vehicle: VehicleParameters,
    efficiencies: DrivetrainEfficiencies,
    sizing: SizingParameters,
) -> EnergyResult:
    
    dt = np.diff(profile.time_s)
    v0 = profile.velocity_m_s[:-1]
    v1 = profile.velocity_m_s[1:]
    velocity = 0.5 * (v0 + v1)
    acceleration = (v1 - v0) / dt

    inertial_force = vehicle.mass_kg * acceleration
    rolling_force = np.full_like(
        velocity,
        vehicle.rolling_resistance_coefficient
        * vehicle.mass_kg
        * vehicle.gravity_m_s2
        * cos(vehicle.road_grade_rad),
    )
    aerodynamic_force = (
        0.5
        * vehicle.air_density_kg_m3
        * vehicle.drag_coefficient
        * vehicle.frontal_area_m2
        * velocity**2
    )
    grade_force = np.full_like(
        velocity,
        vehicle.mass_kg
        * vehicle.gravity_m_s2
        * sin(vehicle.road_grade_rad),
    )

    required_force = (
        inertial_force + rolling_force + aerodynamic_force + grade_force
    )
    wheel_power = required_force * velocity
    traction_power = np.maximum(wheel_power, 0.0)
    electrical_power = (
        traction_power / efficiencies.total + sizing.auxiliary_power_w
    )

    energy_wh = float(np.sum(electrical_power * dt) / 3600.0)
    distance_m = profile.distance_m
    duration_s = profile.duration_s
    required_usable = energy_wh * (1.0 + sizing.sizing_margin_fraction)
    minimum_nominal = required_usable / sizing.usable_battery_fraction

    return EnergyResult(
        distance_m=distance_m,
        duration_s=duration_s,
        energy_wh=energy_wh,
        energy_kwh=energy_wh / 1000.0,
        specific_energy_wh_km=energy_wh / (distance_m / 1000.0),
        peak_electrical_power_w=float(np.max(electrical_power)),
        mean_electrical_power_w=float(
            np.sum(electrical_power * dt) / duration_s),
        required_usable_energy_wh=required_usable,
        minimum_nominal_energy_wh=minimum_nominal,
        interval_time_s=0.5 * (profile.time_s[:-1] + profile.time_s[1:]),
        acceleration_m_s2=acceleration,
        inertial_force_n=inertial_force,
        rolling_force_n=rolling_force,
        aerodynamic_force_n=aerodynamic_force,
        grade_force_n=grade_force,
        wheel_power_w=wheel_power,
        electrical_power_w=electrical_power,
    )
