"""Configurable reference track and physically derived curve speed limits."""

from dataclasses import dataclass
from math import inf, sqrt

from config.parameters import MotorConfig, TrackSegmentConfig, VehicleConfig


@dataclass(frozen=True)
class TrackState:
    segment_index: int
    segment_name: str
    radius_m: float | None
    local_speed_limit_m_s: float
    lap_position_m: float


class ReferenceTrack:
    def __init__(
        self,
        segments: tuple[TrackSegmentConfig, ...],
        vehicle: VehicleConfig,
        motor: MotorConfig,
        final_drive_ratio: float,
    ):
        if not segments or any(segment.length_m <= 0.0 for segment in segments):
            raise ValueError("track segments must have positive length")
        self.segments = segments
        self.vehicle = vehicle
        self.motor = motor
        self.final_drive_ratio = final_drive_ratio
        cumulative = [0.0]
        for segment in segments:
            cumulative.append(cumulative[-1] + segment.length_m)
        self.boundaries_m = tuple(cumulative)
        self.lap_length_m = cumulative[-1]
        self.powertrain_speed_limit_m_s = (
            motor.max_speed_rad_s / final_drive_ratio * vehicle.wheel_radius_m)
        self.segment_speed_limits_m_s = tuple(
            self._speed_limit(segment.radius_m) for segment in segments)

    def _speed_limit(self, radius_m: float | None) -> float:
        if radius_m is None:
            return self.powertrain_speed_limit_m_s
        cfg = self.vehicle
        aero_vertical_coefficient = 0.5 * cfg.air_density_kg_m3 * (
            cfg.lift_coefficient_front * cfg.lift_area_front_m2
            + cfg.lift_coefficient_rear * cfg.lift_area_rear_m2)
        denominator = (
            cfg.mass_kg / radius_m
            - cfg.tire_friction_coefficient * aero_vertical_coefficient)
        if denominator <= 0.0:
            lateral_limit = inf
        else:
            lateral_limit = sqrt(
                cfg.tire_friction_coefficient * cfg.mass_kg
                * cfg.gravity_m_s2 / denominator)
        return min(lateral_limit, self.powertrain_speed_limit_m_s)

    def state_at(self, distance_m: float) -> TrackState:
        lap_position = max(distance_m, 0.0) % self.lap_length_m
        index = len(self.segments) - 1
        for candidate in range(len(self.segments)):
            if lap_position < self.boundaries_m[candidate + 1] - 1e-10:
                index = candidate
                break
        segment = self.segments[index]
        return TrackState(
            segment_index=index,
            segment_name=segment.name,
            radius_m=segment.radius_m,
            local_speed_limit_m_s=self.segment_speed_limits_m_s[index],
            lap_position_m=lap_position,
        )

    def constraints_ahead(
        self, distance_m: float, lookahead_m: float
    ) -> tuple[tuple[float, float, str], ...]:
        """Return upcoming segment-entry distance, limit and name."""
        state = self.state_at(distance_m)
        remaining_current = (
            self.boundaries_m[state.segment_index + 1] - state.lap_position_m)
        ahead = remaining_current
        next_index = (state.segment_index + 1) % len(self.segments)
        constraints = []
        while ahead <= lookahead_m + 1e-9:
            constraints.append((
                ahead,
                self.segment_speed_limits_m_s[next_index],
                self.segments[next_index].name,
            ))
            ahead += self.segments[next_index].length_m
            next_index = (next_index + 1) % len(self.segments)
        return tuple(constraints)
