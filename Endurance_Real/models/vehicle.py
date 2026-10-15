"""Longitudinal resistance, load transfer and combined-grip limits."""

from math import cos, sin, sqrt

from config.parameters import VehicleConfig


class VehicleModel:
    def __init__(self, config: VehicleConfig):
        self.config = config

    def aerodynamic_drag_n(self, speed_m_s: float) -> float:
        v = abs(speed_m_s)
        return (0.5 * self.config.air_density_kg_m3
                * self.config.drag_coefficient
                * self.config.frontal_area_m2 * v * v)

    def rolling_resistance_n(self, speed_m_s: float) -> float:
        cfg = self.config
        coefficient = cfg.rolling_resistance * (
            1.0 + abs(speed_m_s) / cfg.rolling_speed_reference_m_s)
        return coefficient * cfg.mass_kg * cfg.gravity_m_s2 * cos(cfg.road_grade_rad)

    def grade_resistance_n(self) -> float:
        cfg = self.config
        return cfg.mass_kg * cfg.gravity_m_s2 * sin(cfg.road_grade_rad)

    def total_resistance_n(self, speed_m_s: float) -> float:
        return (self.aerodynamic_drag_n(speed_m_s)
                + self.rolling_resistance_n(speed_m_s)
                + self.grade_resistance_n())

    def downforce_n(self, speed_m_s: float) -> float:
        cfg = self.config
        cl_area = (
            cfg.lift_coefficient_front * cfg.lift_area_front_m2
            + cfg.lift_coefficient_rear * cfg.lift_area_rear_m2)
        return 0.5 * cfg.air_density_kg_m3 * cl_area * speed_m_s**2

    def rear_normal_load_n(self, acceleration_m_s2: float, speed_m_s: float) -> float:
        cfg = self.config
        static = cfg.mass_kg * cfg.gravity_m_s2 * cfg.cg_from_front_axle_m / cfg.wheelbase_m
        transfer = cfg.mass_kg * acceleration_m_s2 * cfg.cg_height_m / cfg.wheelbase_m
        rear_downforce = (0.5 * cfg.air_density_kg_m3
                          * cfg.lift_coefficient_rear * cfg.lift_area_rear_m2
                          * speed_m_s**2)
        return max(static + transfer + rear_downforce, 0.0)

    def total_normal_load_n(self, speed_m_s: float) -> float:
        cfg = self.config
        return cfg.mass_kg * cfg.gravity_m_s2 + self.downforce_n(speed_m_s)

    @staticmethod
    def combined_grip_longitudinal_limit_n(
        friction_coefficient: float,
        normal_load_n: float,
        lateral_force_n: float,
    ) -> float:
        """Available Fx from an isotropic friction-circle approximation."""
        total_limit = max(friction_coefficient * normal_load_n, 0.0)
        return sqrt(max(total_limit**2 - lateral_force_n**2, 0.0))

    def lateral_force_n(self, speed_m_s: float, radius_m: float | None) -> float:
        if radius_m is None:
            return 0.0
        return self.config.mass_kg * speed_m_s**2 / radius_m
