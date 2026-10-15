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
        self.brake = BrakeModel(config.brake, config.vehicle, self.vehicle)
        self.track = ReferenceTrack(
            config.track_segments,
            config.vehicle,
            config.motor,
            config.drivetrain.final_drive_ratio,
        )

    def _driver_commands(
        self, distance_m: float, speed_m_s: float, previous_acceleration: float
    ) -> tuple[float, float, float]:
        cfg = self.config
        track_state = self.track.state_at(distance_m)
        target_speed = track_state.local_speed_limit_m_s

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

        must_brake = speed_m_s > target_speed + cfg.speed_control_band_m_s
        for distance_ahead, limit, _name in self.track.constraints_ahead(
            distance_m, cfg.lookahead_m
        ):
            if speed_m_s <= limit:
                continue
            required_distance = (
                (speed_m_s**2 - limit**2) / (2.0 * planning_deceleration))
            if distance_ahead <= required_distance + cfg.braking_distance_buffer_m:
                must_brake = True
                target_speed = min(target_speed, limit)
                break

        if must_brake:
            return 0.0, 1.0, target_speed

        motor_speed = self.drivetrain.motor_speed_rad_s(speed_m_s)
        maximum = self.motor.maximum_drive_torque(motor_speed)
        maximum_force = self.drivetrain.wheel_force_from_motor_torque(
            maximum.torque_nm, motor_speed)
        resistance = self.vehicle.total_resistance_n(speed_m_s)
        if speed_m_s < target_speed - cfg.speed_control_band_m_s:
            throttle = 1.0
        elif maximum_force > 0.0:
            throttle = min(max(resistance / maximum_force, 0.0), 1.0)
        else:
            throttle = 0.0
        return throttle, 0.0, target_speed

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
        )}

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
            throttle, brake_fraction, target_speed = self._driver_commands(
                distance, speed, previous_acceleration)
            motor_speed = self.drivetrain.motor_speed_rad_s(speed)
            motor_maximum = self.motor.maximum_drive_torque(motor_speed)

            requested_torque = throttle * motor_maximum.torque_nm
            ideal_drive_force = self.drivetrain.wheel_force_from_motor_torque(
                requested_torque, motor_speed)
            rear_normal = self.vehicle.rear_normal_load_n(
                previous_acceleration, speed)
            total_normal = self.vehicle.total_normal_load_n(speed)
            lateral_rear = (
                lateral_force * rear_normal / total_normal
                if total_normal > 0.0 else 0.0)
            traction_limit = self.vehicle.friction_circle_longitudinal_limit_n(
                cfg.vehicle.tire_friction_coefficient,
                rear_normal,
                lateral_rear,
            )
            drive_force = min(ideal_drive_force, traction_limit)

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
            history["speed_limit"].append(target_speed)
        else:
            status, reason = "interrupted", "maximum_step_count_reached"

        if distance < cfg.target_distance_m - 1e-6 and status == "completed":
            status, reason = "interrupted", "target_not_reached"

        arrays = {key: np.asarray(value, dtype=float) for key, value in history.items()}
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
            completed_laps=floor(distance / self.track.lap_length_m + 1e-10),
            lap_length_m=self.track.lap_length_m,
            nominal_pack_energy_wh=cfg.battery.nominal_energy_wh,
            sizing_margin_fraction=cfg.sizing_margin_fraction,
            usable_energy_fraction=cfg.usable_energy_fraction,
            max_power_residual_w=max_residual,
            assumptions=ASSUMPTIONS,
            pending_limits=pending,
        )
