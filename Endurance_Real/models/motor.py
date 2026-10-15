"""Quasi-static PMSM envelope using parameters from the existing model."""

from dataclasses import dataclass
from math import isfinite

from config.parameters import MotorConfig


@dataclass(frozen=True)
class MotorOperatingPoint:
    speed_rad_s: float
    torque_nm: float
    mechanical_power_w: float
    dc_power_w: float
    phase_current_peak_a: float
    torque_limited: bool
    power_limited: bool
    speed_limited: bool


class MotorModel:
    def __init__(self, config: MotorConfig):
        self.config = config

    def maximum_drive_torque(self, speed_rad_s: float) -> MotorOperatingPoint:
        speed = max(float(speed_rad_s), 0.0)
        if not isfinite(speed):
            raise ValueError("motor speed must be finite")
        cfg = self.config
        speed_limited = speed >= cfg.max_speed_rad_s
        if speed_limited:
            torque = 0.0
            power_limited = False
        else:
            mechanical_power_limit = (
                cfg.max_dc_power_w * cfg.motor_efficiency
                * cfg.inverter_efficiency)
            power_torque = (
                mechanical_power_limit / speed if speed > 1e-9
                else cfg.max_torque_nm)
            torque = min(cfg.max_torque_nm, power_torque)
            power_limited = power_torque < cfg.max_torque_nm
        mechanical_power = torque * speed
        dc_power = (
            mechanical_power / (cfg.motor_efficiency * cfg.inverter_efficiency)
            if mechanical_power > 0.0 else 0.0)
        current = torque / cfg.torque_constant_nm_a if cfg.torque_constant_nm_a > 0 else 0.0
        return MotorOperatingPoint(
            speed_rad_s=speed,
            torque_nm=torque,
            mechanical_power_w=mechanical_power,
            dc_power_w=dc_power,
            phase_current_peak_a=current,
            torque_limited=torque >= cfg.max_torque_nm * (1.0 - 1e-12),
            power_limited=power_limited,
            speed_limited=speed_limited,
        )
