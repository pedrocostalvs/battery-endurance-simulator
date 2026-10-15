"""Simulation result container and terminal summary formatting."""

from dataclasses import dataclass
from math import ceil
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class LapSummary:
    lap_index: int
    distance_m: float
    time_s: float
    terminal_energy_wh: float
    minimum_voltage_v: float
    maximum_voltage_v: float
    final_soc: float
    maximum_dc_power_w: float


@dataclass(frozen=True)
class EnduranceResults:
    status: str
    termination_reason: str
    time_s: np.ndarray
    distance_m: np.ndarray
    speed_m_s: np.ndarray
    acceleration_m_s2: np.ndarray
    electrical_power_w: np.ndarray
    battery_current_a: np.ndarray
    battery_voltage_v: np.ndarray
    soc: np.ndarray
    cumulative_energy_wh: np.ndarray
    battery_loss_w: np.ndarray
    motor_torque_nm: np.ndarray
    drive_force_n: np.ndarray
    brake_force_n: np.ndarray
    lateral_force_n: np.ndarray
    speed_limit_m_s: np.ndarray
    target_speed_m_s: np.ndarray
    throttle_command: np.ndarray
    brake_command: np.ndarray
    controller_state: np.ndarray
    distance_to_corner_m: np.ndarray
    estimated_braking_distance_m: np.ndarray
    lap_index: np.ndarray
    lap_position_m: np.ndarray
    segment_boundaries_m: np.ndarray
    segment_is_corner: np.ndarray
    segment_names: np.ndarray
    completed_laps: int
    lap_length_m: float
    nominal_pack_energy_wh: float
    sizing_margin_fraction: float
    usable_energy_fraction: float
    max_power_residual_w: float
    max_dc_power_w: float
    minimum_usable_soc: float
    vehicle_mass_kg: float
    gravity_m_s2: float
    assumptions: tuple[str, ...]
    pending_limits: tuple[str, ...]

    @property
    def final_distance_m(self) -> float:
        return float(self.distance_m[-1]) if len(self.distance_m) else 0.0

    @property
    def total_time_s(self) -> float:
        return float(self.time_s[-1]) if len(self.time_s) else 0.0

    @property
    def energy_wh(self) -> float:
        return float(self.cumulative_energy_wh[-1]) if len(self.cumulative_energy_wh) else 0.0

    @property
    def mean_speed_m_s(self) -> float:
        return self.final_distance_m / self.total_time_s if self.total_time_s > 0 else 0.0

    @property
    def mean_power_w(self) -> float:
        return self.energy_wh * 3600.0 / self.total_time_s if self.total_time_s > 0 else 0.0

    @property
    def specific_energy_wh_km(self) -> float:
        return self.energy_wh / (self.final_distance_m / 1000.0) if self.final_distance_m > 0 else 0.0

    @property
    def required_usable_energy_wh(self) -> float:
        return self.energy_wh * (1.0 + self.sizing_margin_fraction)

    @property
    def estimated_nominal_energy_wh(self) -> float:
        return self.required_usable_energy_wh / self.usable_energy_fraction

    def lap_summary(self) -> tuple[LapSummary, ...]:
        """Return boundary-safe per-lap metrics, including a partial last lap."""
        if self.final_distance_m <= 0.0 or self.lap_length_m <= 0.0:
            return ()
        count = int(ceil(self.final_distance_m / self.lap_length_m - 1e-12))
        boundaries = np.minimum(
            np.arange(count + 1, dtype=float) * self.lap_length_m,
            self.final_distance_m,
        )
        sample_distance = np.concatenate(([0.0], self.distance_m))
        sample_time = np.concatenate(([0.0], self.time_s))
        sample_energy = np.concatenate(([0.0], self.cumulative_energy_wh))
        boundary_time = np.interp(boundaries, sample_distance, sample_time)
        boundary_energy = np.interp(boundaries, sample_distance, sample_energy)
        summaries = []
        for lap in range(count):
            mask = self.lap_index == lap
            voltage = self.battery_voltage_v[mask]
            power = self.electrical_power_w[mask]
            soc = self.soc[mask]
            summaries.append(LapSummary(
                lap_index=lap,
                distance_m=float(boundaries[lap + 1] - boundaries[lap]),
                time_s=float(boundary_time[lap + 1] - boundary_time[lap]),
                terminal_energy_wh=float(
                    boundary_energy[lap + 1] - boundary_energy[lap]),
                minimum_voltage_v=float(np.min(voltage)),
                maximum_voltage_v=float(np.max(voltage)),
                final_soc=float(soc[-1]),
                maximum_dc_power_w=float(np.max(power)),
            ))
        return tuple(summaries)

    def save_npz(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            time_s=self.time_s,
            distance_m=self.distance_m,
            speed_m_s=self.speed_m_s,
            acceleration_m_s2=self.acceleration_m_s2,
            electrical_power_w=self.electrical_power_w,
            battery_current_a=self.battery_current_a,
            battery_voltage_v=self.battery_voltage_v,
            soc=self.soc,
            cumulative_energy_wh=self.cumulative_energy_wh,
            battery_loss_w=self.battery_loss_w,
            motor_torque_nm=self.motor_torque_nm,
            drive_force_n=self.drive_force_n,
            brake_force_n=self.brake_force_n,
            lateral_force_n=self.lateral_force_n,
            speed_limit_m_s=self.speed_limit_m_s,
            target_speed_m_s=self.target_speed_m_s,
            throttle_command=self.throttle_command,
            brake_command=self.brake_command,
            controller_state=self.controller_state,
            distance_to_corner_m=self.distance_to_corner_m,
            estimated_braking_distance_m=self.estimated_braking_distance_m,
            lap_index=self.lap_index,
            lap_position_m=self.lap_position_m,
            segment_boundaries_m=self.segment_boundaries_m,
            segment_is_corner=self.segment_is_corner,
            segment_names=self.segment_names,
            max_dc_power_w=np.asarray(self.max_dc_power_w),
            minimum_usable_soc=np.asarray(self.minimum_usable_soc),
        )
        return path
