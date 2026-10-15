"""Validated input data for preliminary endurance battery sizing."""

from dataclasses import dataclass
from math import isfinite
from typing import Optional


def _positive(name: str, value: float) -> None:
    if not isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")


def _fraction(name: str, value: float) -> None:
    if not isfinite(value) or not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]")


@dataclass(frozen=True)
class VehicleParameters:
    mass_kg: float
    drag_coefficient: float
    frontal_area_m2: float
    rolling_resistance_coefficient: float
    air_density_kg_m3: float = 1.225
    road_grade_rad: float = 0.0
    gravity_m_s2: float = 9.81

    def __post_init__(self) -> None:
        _positive("mass_kg", self.mass_kg)
        _positive("frontal_area_m2", self.frontal_area_m2)
        _positive("air_density_kg_m3", self.air_density_kg_m3)
        _positive("gravity_m_s2", self.gravity_m_s2)
        if not isfinite(self.drag_coefficient) or self.drag_coefficient < 0.0:
            raise ValueError("drag_coefficient must be finite and non-negative")
        if (not isfinite(self.rolling_resistance_coefficient)
                or self.rolling_resistance_coefficient < 0.0):
            raise ValueError(
                "rolling_resistance_coefficient must be finite and non-negative")
        if not isfinite(self.road_grade_rad):
            raise ValueError("road_grade_rad must be finite")


@dataclass(frozen=True)
class DrivetrainEfficiencies:
    transmission: float
    motor: float
    inverter: float

    def __post_init__(self) -> None:
        _fraction("transmission efficiency", self.transmission)
        _fraction("motor efficiency", self.motor)
        _fraction("inverter efficiency", self.inverter)

    @property
    def total(self) -> float:
        return self.transmission * self.motor * self.inverter


@dataclass(frozen=True)
class SizingParameters:
    target_distance_m: float = 22_000.0
    sizing_margin_fraction: float = 0.20
    usable_battery_fraction: float = 0.80
    auxiliary_power_w: float = 0.0
    regenerative_braking: bool = False

    def __post_init__(self) -> None:
        _positive("target_distance_m", self.target_distance_m)
        _fraction("usable_battery_fraction", self.usable_battery_fraction)
        if (not isfinite(self.sizing_margin_fraction)
                or self.sizing_margin_fraction < 0.0):
            raise ValueError("sizing_margin_fraction must be non-negative")
        if not isfinite(self.auxiliary_power_w) or self.auxiliary_power_w < 0.0:
            raise ValueError("auxiliary_power_w must be non-negative")
        if self.regenerative_braking:
            raise ValueError("this preliminary model does not implement regeneration")


@dataclass(frozen=True)
class CellSpecifications:
    name: str
    nominal_voltage_v: float
    capacity_ah: float
    min_voltage_v: Optional[float] = None
    max_voltage_v: Optional[float] = None
    max_continuous_current_a: Optional[float] = None
    max_pulse_current_a: Optional[float] = None
    max_continuous_c_rate: Optional[float] = None
    mass_kg: Optional[float] = None
    volume_l: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("cell name must not be empty")
        _positive("nominal_voltage_v", self.nominal_voltage_v)
        _positive("capacity_ah", self.capacity_ah)
        for name in (
            "min_voltage_v", "max_voltage_v", "max_continuous_current_a",
            "max_pulse_current_a", "max_continuous_c_rate", "mass_kg",
            "volume_l",
        ):
            value = getattr(self, name)
            if value is not None:
                _positive(name, value)
        if (self.min_voltage_v is not None and self.max_voltage_v is not None
                and self.min_voltage_v >= self.max_voltage_v):
            raise ValueError("min_voltage_v must be lower than max_voltage_v")


@dataclass(frozen=True)
class PackConfiguration:
    series: int
    parallel: int
    max_pack_current_a: Optional[float] = None
    max_pack_power_w: Optional[float] = None
    allowed_min_voltage_v: Optional[float] = None
    allowed_max_voltage_v: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.series, int) or self.series <= 0:
            raise ValueError("series must be a positive integer")
        if not isinstance(self.parallel, int) or self.parallel <= 0:
            raise ValueError("parallel must be a positive integer")
        for name in (
            "max_pack_current_a", "max_pack_power_w",
            "allowed_min_voltage_v", "allowed_max_voltage_v",
        ):
            value = getattr(self, name)
            if value is not None:
                _positive(name, value)
