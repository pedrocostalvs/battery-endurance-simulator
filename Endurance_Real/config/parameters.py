"""Known project values and explicit reference-scenario assumptions.

Values marked KNOWN are copied from the existing repository. Values marked
ASSUMPTION are configurable placeholders, not validated component or track data.
"""

from dataclasses import dataclass, field
from math import pi


@dataclass(frozen=True)
class VehicleConfig:
    mass_kg: float = 240.0                 # KNOWN
    wheel_radius_m: float = 0.26           # KNOWN
    wheel_mass_kg: float = 5.0             # KNOWN, each wheel
    drag_coefficient: float = 0.7789       # KNOWN
    frontal_area_m2: float = 0.68          # KNOWN
    rolling_resistance: float = 0.015      # KNOWN
    rolling_speed_reference_m_s: float = 150.0  # KNOWN model convention
    air_density_kg_m3: float = 1.225       # KNOWN model default
    gravity_m_s2: float = 9.81
    road_grade_rad: float = 0.0            # ASSUMPTION: flat reference track
    wheelbase_m: float = 1.5               # KNOWN
    cg_height_m: float = 0.28              # KNOWN
    cg_from_front_axle_m: float = 0.6      # KNOWN
    driven_wheels: int = 2
    tire_friction_coefficient: float = 0.6 # KNOWN configured value
    lift_coefficient_front: float = 1.0    # KNOWN configured value
    lift_area_front_m2: float = 0.35       # KNOWN configured value
    lift_coefficient_rear: float = 1.0     # KNOWN configured value
    lift_area_rear_m2: float = 0.35        # KNOWN configured value


@dataclass(frozen=True)
class DrivetrainConfig:
    final_drive_ratio: float = 5.0         # KNOWN
    chain_efficiency: float = 0.98         # KNOWN
    differential_efficiency: float = 0.97  # KNOWN
    axle_inertia_kg_m2: float = 0.0015     # KNOWN, each driven axle
    differential_inertia_kg_m2: float = 0.012
    motor_sprocket_inertia_kg_m2: float = 0.0002
    crown_inertia_kg_m2: float = 0.0015


@dataclass(frozen=True)
class MotorConfig:
    pole_pairs: int = 10                   # KNOWN
    flux_linkage_wb: float = 0.04748       # KNOWN
    max_phase_current_peak_a: float = 323.0 # KNOWN configured limit
    max_speed_rad_s: float = 575.96        # KNOWN configured reference
    rotor_inertia_kg_m2: float = 0.02521   # KNOWN
    viscous_friction_nms: float = 0.005    # KNOWN
    motor_efficiency: float = 0.90         # ASSUMPTION: constant
    inverter_efficiency: float = 0.95      # ASSUMPTION from unused UI value
    max_dc_power_w: float = 80_000.0       # KNOWN project simulation setting

    @property
    def torque_constant_nm_a(self) -> float:
        return 1.5 * self.pole_pairs * self.flux_linkage_wb

    @property
    def max_torque_nm(self) -> float:
        return self.torque_constant_nm_a * self.max_phase_current_peak_a


@dataclass(frozen=True)
class BatteryConfig:
    series_cells: int = 144                # KNOWN
    parallel_cells: int = 5                # KNOWN
    initial_soc: float = 1.0
    minimum_usable_soc: float = 0.20       # ASSUMPTION, configurable
    cell_nominal_voltage_v: float = 3.7    # generic existing model
    cell_capacity_ah: float = 3.0          # generic existing model
    cell_resistance_ohm: float = 0.02      # generic existing model
    polarization_constant_v: float = 0.005
    exponential_voltage_v: float = 0.1
    exponential_capacity_inv_ah: float = 0.01
    cell_min_voltage_v: float | None = None  # PENDING: no datasheet
    cell_max_voltage_v: float | None = None
    cell_max_current_a: float | None = None

    @property
    def nominal_voltage_v(self) -> float:
        return self.series_cells * self.cell_nominal_voltage_v

    @property
    def nominal_energy_wh(self) -> float:
        return (self.nominal_voltage_v * self.parallel_cells
                * self.cell_capacity_ah)


@dataclass(frozen=True)
class BrakeConfig:
    pedal_force_n: float = 500.0           # KNOWN current script input
    pedal_ratio: float = 4.0               # KNOWN
    master_cylinder_diameter_m: float = 0.02
    wheel_cylinder_diameter_m: float = 0.032
    pads_per_disc: int = 2
    pad_friction_coefficient: float = 0.35 # KNOWN configured value
    effective_disc_radius_m: float = 0.075
    number_of_discs: int = 4               # ASSUMPTION: one per wheel
    hydraulic_efficiency: float = 1.0      # ASSUMPTION: ideal hydraulics
    pressure_bias_front: float = 0.60      # ASSUMPTION, explicit

    @property
    def master_area_m2(self) -> float:
        return pi * self.master_cylinder_diameter_m**2 / 4.0

    @property
    def wheel_cylinder_area_m2(self) -> float:
        return pi * self.wheel_cylinder_diameter_m**2 / 4.0


@dataclass(frozen=True)
class TrackSegmentConfig:
    name: str
    length_m: float
    radius_m: float | None = None


def reference_track_segments() -> tuple[TrackSegmentConfig, ...]:
    """Hypothetical 1 km lap; not an official or measured track."""
    return (
        TrackSegmentConfig("Reta principal", 180.0),
        TrackSegmentConfig("Curva A", 80.0, 25.0),
        TrackSegmentConfig("Reta curta", 150.0),
        TrackSegmentConfig("Curva B", 100.0, 35.0),
        TrackSegmentConfig("Reta oposta", 200.0),
        TrackSegmentConfig("Curva lenta", 70.0, 18.0),
        TrackSegmentConfig("Reta final", 140.0),
        TrackSegmentConfig("Curva de retorno", 80.0, 30.0),
    )


@dataclass(frozen=True)
class SimulationConfig:
    target_distance_m: float = 22_000.0
    time_step_s: float = 0.02              # ASSUMPTION, convergence tested
    maximum_time_s: float = 4_000.0
    sizing_margin_fraction: float = 0.20   # ASSUMPTION
    usable_energy_fraction: float = 0.80   # ASSUMPTION
    braking_safety_factor: float = 0.82    # ASSUMPTION: driver uses 82% available
    braking_distance_buffer_m: float = 4.0 # ASSUMPTION
    speed_control_band_m_s: float = 0.25
    lookahead_m: float = 220.0
    vehicle: VehicleConfig = field(default_factory=VehicleConfig)
    drivetrain: DrivetrainConfig = field(default_factory=DrivetrainConfig)
    motor: MotorConfig = field(default_factory=MotorConfig)
    battery: BatteryConfig = field(default_factory=BatteryConfig)
    brake: BrakeConfig = field(default_factory=BrakeConfig)
    track_segments: tuple[TrackSegmentConfig, ...] = field(
        default_factory=reference_track_segments)


ASSUMPTIONS = (
    "Percurso de referência hipotético de 1 km; não representa pista oficial.",
    "Eficiências de motor e inversor constantes em 90% e 95%.",
    "SoC mínimo utilizável de 20% e margem energética de 20%.",
    "Pista plana, sem vento e sem frenagem regenerativa.",
    "Controle de condução determinístico com antecipação de curvas.",
    "Sem limites de tensão/corrente de datasheet: essas verificações ficam pendentes.",
)
