"""Coupled longitudinal and battery-state Endurance integration."""

from math import ceil, floor, isfinite, sqrt

import numpy as np

from config.parameters import ASSUMPTIONS, SimulationConfig
from models import BatteryModel, BrakeModel, DrivetrainModel, MotorModel, VehicleModel
from .results import EnduranceResults
from .track import ReferenceTrack


class EnduranceSimulator:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.vehicle = VehicleModel(config.vehicle)
        self.drivetrain = DrivetrainModel(
            config.drivetrain, config.vehicle, config.motor)
        self.motor = MotorModel(config.motor)
        self.battery = BatteryModel(config.battery)
        self.brake = BrakeModel(
            config.brake, config.vehicle, config.tire, self.vehicle)
        self.track = ReferenceTrack(
            config.track_segments,
            config.vehicle,
            config.tire,
            config.motor,
            config.drivetrain.final_drive_ratio,
        )
        self._driver_state = "ACCELERATING"
        self._previous_throttle = 0.0
        self._corner_target: dict[str, float | int | str] | None = None

    def _maximum_available_drive_force(
        self, speed_m_s: float, previous_acceleration: float,
        lateral_force_n: float,
    ) -> float:
        motor_speed = self.drivetrain.motor_speed_rad_s(speed_m_s)
        maximum = self.motor.maximum_drive_torque(motor_speed)
        ideal_force = self.drivetrain.wheel_force_from_motor_torque(
            maximum.torque_nm, motor_speed)
        rear_normal = self.vehicle.rear_normal_load_n(
            previous_acceleration, speed_m_s)
        total_normal = self.vehicle.total_normal_load_n(speed_m_s)
        lateral_rear = (
            lateral_force_n * rear_normal / total_normal
            if total_normal > 0.0 else 0.0)
        tire_limit = self.vehicle.combined_grip_longitudinal_limit_n(
            self.config.tire.friction_coefficient,
            rear_normal,
            lateral_rear,
        )
        return min(ideal_force, tire_limit)

    def _driver_commands(
        self, distance_m: float, speed_m_s: float, previous_acceleration: float
    ) -> tuple[float, float, float, str, float, float]:
        cfg = self.config
        track_state = self.track.state_at(distance_m)
        straight_target = (
            cfg.straight_speed_target_fraction
            * self.track.powertrain_speed_limit_m_s)
        local_target = (
            straight_target if track_state.radius_m is None
            else track_state.local_speed_limit_m_s)

        lateral = self.vehicle.lateral_force_n(speed_m_s, track_state.radius_m)
        brake_capability = self.brake.apply(
            speed_m_s, lateral, max(-previous_acceleration, 0.0), 1.0)
        planning_deceleration = max(
            cfg.braking_safety_factor
            * (brake_capability.effective_wheel_force_n
               + self.vehicle.total_resistance_n(speed_m_s))
            / self.drivetrain.equivalent_mass_kg,
            0.1,
        )
        if (
            self._corner_target is not None
            and distance_m >= float(self._corner_target["exit_distance_m"]) - 1e-9
        ):
            self._corner_target = None
            self._driver_state = "ACCELERATING"

        if self._corner_target is None:
            segment_by_name = {
                segment.name: (index, segment)
                for index, segment in enumerate(cfg.track_segments)
            }
            for distance_ahead, limit, name in self.track.constraints_ahead(
                distance_m, cfg.lookahead_m
            ):
                index, segment = segment_by_name[name]
                if segment.radius_m is None or speed_m_s <= limit:
                    continue
                braking_distance = (
                    (speed_m_s**2 - limit**2)
                    / (2.0 * planning_deceleration)
                )
                release_distance = (
                    speed_m_s * self._previous_throttle
                    / cfg.throttle_rate_limit_per_s
                )
                if distance_ahead <= (
                    braking_distance + release_distance
                    + cfg.braking_distance_buffer_m
                ):
                    entry = distance_m + distance_ahead
                    self._corner_target = {
                        "segment_index": index,
                        "name": name,
                        "speed_limit_m_s": limit,
                        "entry_distance_m": entry,
                        "exit_distance_m": entry + segment.length_m,
                    }
                    self._driver_state = "BRAKING"
                    break

        distance_to_corner = -1.0
        braking_distance = 0.0
        target_speed = local_target
        if self._corner_target is not None:
            target_speed = float(self._corner_target["speed_limit_m_s"])
            distance_to_corner = max(
                float(self._corner_target["entry_distance_m"]) - distance_m,
                0.0,
            )
            if speed_m_s > target_speed:
                braking_distance = (
                    (speed_m_s**2 - target_speed**2)
                    / (2.0 * planning_deceleration)
                )

        maximum_force = self._maximum_available_drive_force(
            speed_m_s, previous_acceleration, lateral)
        resistance = self.vehicle.total_resistance_n(speed_m_s)
        if self._driver_state == "BRAKING":
            desired_throttle = 0.0
        else:
            if maximum_force > 0.0:
                feedforward = resistance / maximum_force
                proportional = (
                    cfg.driver_speed_kp * (target_speed - speed_m_s)
                    / self.track.powertrain_speed_limit_m_s
                )
                desired_throttle = min(max(feedforward + proportional, 0.0), 1.0)
                if (
                    self._corner_target is not None
                    and self._driver_state == "CRUISING"
                ):
                    # After one braking event, hold the corner speed with the
                    # resistive-force feedforward instead of reaccelerating
                    # into a second brake event for the same corner.
                    desired_throttle = feedforward
            else:
                desired_throttle = 0.0

        maximum_change = cfg.throttle_rate_limit_per_s * cfg.time_step_s
        throttle = min(
            max(
                desired_throttle,
                self._previous_throttle - maximum_change,
            ),
            self._previous_throttle + maximum_change,
        )
        throttle = min(max(throttle, 0.0), 1.0)
        self._previous_throttle = throttle

        brake_fraction = 0.0
        if self._driver_state == "BRAKING" and throttle <= 1e-12:
            brake_fraction = 1.0
            if speed_m_s <= target_speed:
                self._driver_state = "CRUISING"
                brake_fraction = 0.0
        elif self._driver_state != "BRAKING":
            if speed_m_s < target_speed - cfg.speed_control_band_m_s:
                self._driver_state = "ACCELERATING"
            else:
                self._driver_state = "CRUISING"

        return (
            throttle,
            brake_fraction,
            target_speed,
            self._driver_state,
            distance_to_corner,
            braking_distance,
        )

    @staticmethod
    def _time_to_distance(
        speed_m_s: float, acceleration_m_s2: float,
        remaining_distance_m: float, maximum_dt_s: float,
    ) -> float:
        if remaining_distance_m <= 0.0:
            return 0.0
        if abs(acceleration_m_s2) < 1e-14:
            return min(remaining_distance_m / max(speed_m_s, 1e-14), maximum_dt_s)
        discriminant = speed_m_s**2 + 2.0 * acceleration_m_s2 * remaining_distance_m
        if discriminant < 0.0:
            return maximum_dt_s
        root = (-speed_m_s + sqrt(discriminant)) / acceleration_m_s2
        if 0.0 <= root <= maximum_dt_s:
            return root
        return maximum_dt_s

    def run(self) -> EnduranceResults:
        cfg = self.config
        t = 0.0
        distance = 0.0
        speed = 0.0
        previous_acceleration = 0.0
        status = "completed"
        reason = "target_distance_reached"
        max_residual = 0.0

        history = {name: [] for name in (
            "time", "distance", "speed", "acceleration", "power", "current",
            "voltage", "soc", "energy", "loss", "torque", "drive_force",
            "brake_force", "lateral_force", "speed_limit",
            "target_speed", "throttle", "brake_command",
            "distance_to_corner", "braking_distance",
        )}
        controller_states: list[str] = []

        maximum_steps = int(ceil(cfg.maximum_time_s / cfg.time_step_s)) + 1
        for _step in range(maximum_steps):
            if distance >= cfg.target_distance_m - 1e-9:
                distance = cfg.target_distance_m
                break
            if t >= cfg.maximum_time_s:
                status, reason = "interrupted", "maximum_time_reached"
                break
            if self.battery.usable_energy_exhausted:
                status, reason = "interrupted", "minimum_usable_soc_reached"
                break

            track_state = self.track.state_at(distance)
            lateral_force = self.vehicle.lateral_force_n(speed, track_state.radius_m)
            (
                throttle,
                brake_fraction,
                target_speed,
                controller_state,
                distance_to_corner,
                braking_distance,
            ) = self._driver_commands(
                distance, speed, previous_acceleration)
            motor_speed = self.drivetrain.motor_speed_rad_s(speed)
            motor_maximum = self.motor.maximum_drive_torque(motor_speed)

            ideal_drive_force = self.drivetrain.wheel_force_from_motor_torque(
                motor_maximum.torque_nm, motor_speed)
            rear_normal = self.vehicle.rear_normal_load_n(
                previous_acceleration, speed)
            total_normal = self.vehicle.total_normal_load_n(speed)
            lateral_rear = (
                lateral_force * rear_normal / total_normal
                if total_normal > 0.0 else 0.0)
            traction_limit = self.vehicle.combined_grip_longitudinal_limit_n(
                cfg.tire.friction_coefficient,
                rear_normal,
                lateral_rear,
            )
            drive_force = throttle * min(ideal_drive_force, traction_limit)

            brake_output = self.brake.apply(
                speed, lateral_force, max(-previous_acceleration, 0.0), brake_fraction)
            brake_force = brake_output.effective_wheel_force_n
            resistance = self.vehicle.total_resistance_n(speed)
            net_force = drive_force - brake_force - resistance
            acceleration = net_force / self.drivetrain.equivalent_mass_kg
            if speed <= 1e-10 and acceleration < 0.0:
                acceleration = 0.0

            if drive_force > 0.0:
                actual_motor_torque = (
                    drive_force * cfg.vehicle.wheel_radius_m
                    / (cfg.drivetrain.final_drive_ratio * self.drivetrain.efficiency)
                    + cfg.motor.viscous_friction_nms * motor_speed)
            else:
                actual_motor_torque = 0.0
            motor_mechanical_power = actual_motor_torque * motor_speed
            electrical_power = (
                motor_mechanical_power
                / (cfg.motor.motor_efficiency * cfg.motor.inverter_efficiency)
                if motor_mechanical_power > 0.0 else 0.0)
            if electrical_power > cfg.motor.max_dc_power_w * (1.0 + 1e-10):
                status, reason = "interrupted", "dc_power_limit_exceeded"
                break

            try:
                battery_point = self.battery.solve_power(electrical_power)
            except (ValueError, FloatingPointError):
                status, reason = "interrupted", "invalid_battery_operating_point"
                break
            if not battery_point.feasible:
                status, reason = "interrupted", "battery_power_capability_exceeded"
                break
            max_residual = max(max_residual, abs(battery_point.residual_w))

            dt = cfg.time_step_s
            if acceleration < 0.0 and speed + acceleration * dt < 0.0:
                moving_dt = -speed / acceleration if acceleration != 0.0 else 0.0
                step_distance = speed * moving_dt + 0.5 * acceleration * moving_dt**2
                next_speed = 0.0
            else:
                step_distance = speed * dt + 0.5 * acceleration * dt**2
                next_speed = max(speed + acceleration * dt, 0.0)

            remaining = cfg.target_distance_m - distance
            if step_distance > remaining:
                dt = self._time_to_distance(speed, acceleration, remaining, dt)
                step_distance = remaining
                next_speed = max(speed + acceleration * dt, 0.0)

            values = (
                t, distance, speed, acceleration, electrical_power,
                battery_point.current_a, battery_point.terminal_voltage_v,
                self.battery.soc, self.battery.energy_delivered_wh,
            )
            if not all(isfinite(value) for value in values):
                status, reason = "interrupted", "non_finite_state"
                break

            self.battery.advance(battery_point, dt)
            t += dt
            distance += max(step_distance, 0.0)
            speed = next_speed
            previous_acceleration = acceleration

            history["time"].append(t)
            history["distance"].append(distance)
            history["speed"].append(speed)
            history["acceleration"].append(acceleration)
            history["power"].append(electrical_power)
            history["current"].append(battery_point.current_a)
            history["voltage"].append(battery_point.terminal_voltage_v)
            history["soc"].append(self.battery.soc)
            history["energy"].append(self.battery.energy_delivered_wh)
            history["loss"].append(battery_point.resistive_loss_w)
            history["torque"].append(actual_motor_torque)
            history["drive_force"].append(drive_force)
            history["brake_force"].append(brake_force)
            history["lateral_force"].append(lateral_force)
            history["speed_limit"].append(track_state.local_speed_limit_m_s)
            history["target_speed"].append(target_speed)
            history["throttle"].append(throttle)
            history["brake_command"].append(brake_fraction)
            history["distance_to_corner"].append(distance_to_corner)
            history["braking_distance"].append(braking_distance)
            controller_states.append(controller_state)
        else:
            status, reason = "interrupted", "maximum_step_count_reached"

        if distance < cfg.target_distance_m - 1e-6 and status == "completed":
            status, reason = "interrupted", "target_not_reached"

        arrays = {key: np.asarray(value, dtype=float) for key, value in history.items()}
        lap_index = np.maximum(
            np.ceil(arrays["distance"] / self.track.lap_length_m).astype(int) - 1,
            0,
        )
        lap_position = (
            arrays["distance"] - lap_index * self.track.lap_length_m)
        pending = (
            "Tensão mínima e máxima da célula não informadas.",
            "Corrente contínua e de pico da célula não informadas.",
            "Limites térmicos do pack não modelados.",
            "Limite de potência de 80 kW é configuração do projeto, não validação regulamentar.",
        )
        return EnduranceResults(
            status=status,
            termination_reason=reason,
            time_s=arrays["time"],
            distance_m=arrays["distance"],
            speed_m_s=arrays["speed"],
            acceleration_m_s2=arrays["acceleration"],
            electrical_power_w=arrays["power"],
            battery_current_a=arrays["current"],
            battery_voltage_v=arrays["voltage"],
            soc=arrays["soc"],
            cumulative_energy_wh=arrays["energy"],
            battery_loss_w=arrays["loss"],
            motor_torque_nm=arrays["torque"],
            drive_force_n=arrays["drive_force"],
            brake_force_n=arrays["brake_force"],
            lateral_force_n=arrays["lateral_force"],
            speed_limit_m_s=arrays["speed_limit"],
            target_speed_m_s=arrays["target_speed"],
            throttle_command=arrays["throttle"],
            brake_command=arrays["brake_command"],
            controller_state=np.asarray(controller_states, dtype="U16"),
            distance_to_corner_m=arrays["distance_to_corner"],
            estimated_braking_distance_m=arrays["braking_distance"],
            lap_index=lap_index,
            lap_position_m=lap_position,
            segment_boundaries_m=np.asarray(self.track.boundaries_m, dtype=float),
            segment_is_corner=np.asarray([
                segment.radius_m is not None for segment in cfg.track_segments
            ], dtype=bool),
            segment_names=np.asarray([
                segment.name for segment in cfg.track_segments
            ], dtype="U64"),
            completed_laps=floor(distance / self.track.lap_length_m + 1e-10),
            lap_length_m=self.track.lap_length_m,
            nominal_pack_energy_wh=cfg.battery.nominal_energy_wh,
            sizing_margin_fraction=cfg.sizing_margin_fraction,
            usable_energy_fraction=cfg.usable_energy_fraction,
            max_power_residual_w=max_residual,
            max_dc_power_w=cfg.motor.max_dc_power_w,
            minimum_usable_soc=cfg.battery.minimum_usable_soc,
            vehicle_mass_kg=cfg.vehicle.mass_kg,
            gravity_m_s2=cfg.vehicle.gravity_m_s2,
            assumptions=ASSUMPTIONS,
            pending_limits=pending,
        )
