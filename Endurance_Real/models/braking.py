"""Dimensionally explicit hydraulic brake adapter.

This replaces, only inside ``Endurance_Real``, the ambiguous force paths in
the original ``BrakeSystem.apply_brake``. Rolling resistance is intentionally
not subtracted here; the vehicle model applies it once in Newton's equation.
"""

from dataclasses import dataclass

from config.parameters import BrakeConfig, VehicleConfig
from .vehicle import VehicleModel


@dataclass(frozen=True)
class BrakeOutput:
    pedal_force_n: float
    master_pressure_pa: float
    total_pad_normal_force_n: float
    total_disc_torque_nm: float
    commanded_wheel_force_n: float
    adhesion_limit_n: float
    effective_wheel_force_n: float
    front_normal_load_n: float
    rear_normal_load_n: float


class BrakeModel:
    def __init__(
        self,
        config: BrakeConfig,
        vehicle_config: VehicleConfig,
        vehicle_model: VehicleModel,
    ):
        self.config = config
        self.vehicle_config = vehicle_config
        self.vehicle_model = vehicle_model

    def apply(
        self,
        speed_m_s: float,
        lateral_force_n: float,
        previous_deceleration_m_s2: float,
        pedal_fraction: float = 1.0,
    ) -> BrakeOutput:
        cfg = self.config
        vehicle = self.vehicle_config
        pedal_fraction = min(max(float(pedal_fraction), 0.0), 1.0)
        pedal_force = cfg.pedal_force_n * pedal_fraction
        master_force = pedal_force * cfg.pedal_ratio
        pressure = master_force / cfg.master_area_m2
        piston_force = pressure * cfg.wheel_cylinder_area_m2 * cfg.hydraulic_efficiency
        pad_normal_per_disc = piston_force * cfg.pads_per_disc
        total_pad_normal = pad_normal_per_disc * cfg.number_of_discs
        total_disc_torque = (
            total_pad_normal * cfg.pad_friction_coefficient
            * cfg.effective_disc_radius_m)
        commanded_force = total_disc_torque / vehicle.wheel_radius_m

        total_normal = self.vehicle_model.total_normal_load_n(speed_m_s)
        adhesion_limit = self.vehicle_model.friction_circle_longitudinal_limit_n(
            vehicle.tire_friction_coefficient, total_normal, lateral_force_n)
        effective_force = min(commanded_force, adhesion_limit)

        transfer = (vehicle.mass_kg * max(previous_deceleration_m_s2, 0.0)
                    * vehicle.cg_height_m / vehicle.wheelbase_m)
        rear_static = (vehicle.mass_kg * vehicle.gravity_m_s2
                       * vehicle.cg_from_front_axle_m / vehicle.wheelbase_m)
        front_static = vehicle.mass_kg * vehicle.gravity_m_s2 - rear_static
        front_normal = max(front_static + transfer, 0.0)
        rear_normal = max(rear_static - transfer, 0.0)
        normal_sum = front_normal + rear_normal
        if normal_sum > 0.0:
            scale = total_normal / normal_sum
            front_normal *= scale
            rear_normal *= scale

        return BrakeOutput(
            pedal_force_n=pedal_force,
            master_pressure_pa=pressure,
            total_pad_normal_force_n=total_pad_normal,
            total_disc_torque_nm=total_disc_torque,
            commanded_wheel_force_n=commanded_force,
            adhesion_limit_n=adhesion_limit,
            effective_wheel_force_n=effective_force,
            front_normal_load_n=front_normal,
            rear_normal_load_n=rear_normal,
        )
