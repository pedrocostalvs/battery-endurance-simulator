"""Transmission kinematics and single-body equivalent rotating inertia."""

from config.parameters import DrivetrainConfig, MotorConfig, VehicleConfig


class DrivetrainModel:
    def __init__(
        self,
        config: DrivetrainConfig,
        vehicle: VehicleConfig,
        motor: MotorConfig,
    ):
        self.config = config
        self.vehicle = vehicle
        self.motor = motor

    @property
    def efficiency(self) -> float:
        return self.config.chain_efficiency * self.config.differential_efficiency

    def motor_speed_rad_s(self, vehicle_speed_m_s: float) -> float:
        return (max(vehicle_speed_m_s, 0.0) / self.vehicle.wheel_radius_m
                * self.config.final_drive_ratio)

    def wheel_force_from_motor_torque(
        self, motor_torque_nm: float, motor_speed_rad_s: float
    ) -> float:
        net_motor_torque = max(
            motor_torque_nm
            - self.motor.viscous_friction_nms * motor_speed_rad_s,
            0.0,
        )
        return (
            net_motor_torque * self.config.final_drive_ratio * self.efficiency
            / self.vehicle.wheel_radius_m
        )

    @property
    def equivalent_mass_kg(self) -> float:
        """Translational mass plus rotational terms, counted exactly once."""
        r = self.vehicle.wheel_radius_m
        ratio = self.config.final_drive_ratio
        wheel_inertia = 4.0 * 0.80 * self.vehicle.wheel_mass_kg * r**2
        slow_inertia = (
            wheel_inertia
            + self.vehicle.driven_wheels * self.config.axle_inertia_kg_m2
            + self.config.differential_inertia_kg_m2
            + self.config.crown_inertia_kg_m2
        )
        fast_inertia = (
            self.motor.rotor_inertia_kg_m2
            + self.config.motor_sprocket_inertia_kg_m2
        )
        rotational_equivalent = slow_inertia / r**2 + fast_inertia * ratio**2 / r**2
        return self.vehicle.mass_kg + rotational_equivalent
