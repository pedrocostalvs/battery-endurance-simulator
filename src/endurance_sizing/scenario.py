"""Explicit baseline assumptions for the initial hypothetical scenario."""

from dataclasses import dataclass

from .energy import EnergyResult, calculate_energy_demand
from .pack_sizing import PackAssessment, assess_pack, enumerate_energy_candidates
from .parameters import (
    CellSpecifications,
    DrivetrainEfficiencies,
    PackConfiguration,
    SizingParameters,
    VehicleParameters,
)
from .profiles import (
    VelocityProfile,
    build_hypothetical_endurance_cycle,
    repeat_to_exact_distance,
)
from .sensitivity import SensitivityPoint, run_sensitivity


@dataclass(frozen=True)
class ScenarioResult:
    cycle: VelocityProfile
    profile: VelocityProfile
    vehicle: VehicleParameters
    efficiencies: DrivetrainEfficiencies
    sizing: SizingParameters
    cell: CellSpecifications
    pack: PackConfiguration
    energy: EnergyResult
    pack_assessment: PackAssessment
    energy_candidates: tuple[PackConfiguration, ...]
    sensitivity: tuple[SensitivityPoint, ...]
    known_parameters: tuple[str, ...]
    assumptions: tuple[str, ...]
    missing_information: tuple[str, ...]


def run_initial_hypothetical_scenario() -> ScenarioResult:
    """Run the transparent baseline scenario used by the command-line tool."""
    vehicle = VehicleParameters(
        mass_kg=240.0,
        drag_coefficient=0.7789,
        frontal_area_m2=0.68,
        rolling_resistance_coefficient=0.015,
        air_density_kg_m3=1.225,
        road_grade_rad=0.0,
    )
    efficiencies = DrivetrainEfficiencies(
        transmission=0.98 * 0.97,
        motor=0.90,
        inverter=0.95,
    )
    sizing = SizingParameters(
        target_distance_m=22_000.0,
        sizing_margin_fraction=0.20,
        usable_battery_fraction=0.80,
        auxiliary_power_w=0.0,
        regenerative_braking=False,
    )
    cell = CellSpecifications(
        name="Li-ion genérica do modelo existente (sem datasheet)",
        nominal_voltage_v=3.7,
        capacity_ah=3.0,
        mass_kg=0.045,
        volume_l=0.025,
    )
    pack = PackConfiguration(series=144, parallel=5)

    cycle = build_hypothetical_endurance_cycle(sample_dt_s=0.1)
    profile = repeat_to_exact_distance(cycle, sizing.target_distance_m)
    energy = calculate_energy_demand(profile, vehicle, efficiencies, sizing)
    assessment = assess_pack(cell, pack, energy, sizing)
    candidates = enumerate_energy_candidates(
        cell,
        energy.minimum_nominal_energy_wh,
        series_options=(pack.series,),
        extra_parallel_options=2,
    )
    sensitivity = run_sensitivity(
        profile,
        vehicle,
        efficiencies,
        sizing,
        factors={
            "mass": (0.90, 1.00, 1.10),
            "drag_coefficient": (0.90, 1.00, 1.10),
            "rolling_resistance": (0.90, 1.00, 1.10),
            "motor_efficiency": (0.90, 1.00, 1.10),
        },
    )

    return ScenarioResult(
        cycle=cycle,
        profile=profile,
        vehicle=vehicle,
        efficiencies=efficiencies,
        sizing=sizing,
        cell=cell,
        pack=pack,
        energy=energy,
        pack_assessment=assessment,
        energy_candidates=candidates,
        sensitivity=sensitivity,
        known_parameters=(
            "Massa, Cd, área frontal e Crr copiados da configuração atual.",
            "Eficiência da transmissão: 0,98 × 0,97 = 0,9506.",
            "Pack atual: 144s5p; célula genérica: 3,7 V e 3,0 Ah.",
            "Distância-alvo solicitada: 22.000 m.",
        ),
        assumptions=(
            "Perfil velocidade-tempo sintético, não medido e não derivado do Sprint.",
            "Eficiência constante do motor: 90% (hipótese).",
            "Eficiência constante do inversor: 95% (hipótese existente na interface).",
            "Margem energética: 20% (hipótese configurável).",
            "Fração utilizável da energia nominal: 80% (hipótese configurável).",
            "Potência auxiliar: 0 W; cargas auxiliares ainda não informadas.",
            "Pista plana e frenagem sem regeneração.",
            "Sensibilidade one-at-a-time de ±10% (faixa exploratória, não tolerância).",
        ),
        missing_information=(
            "Telemetria ou perfil de velocidade real do Endurance.",
            "Modelo/datasheet da célula e tensões mínima e máxima.",
            "Limites contínuos e de pico de corrente e C-rate da célula.",
            "Faixa de tensão, corrente e potência permitida pelo sistema.",
            "Mapa de eficiência do motor e do inversor.",
            "Consumo dos sistemas auxiliares.",
            "Efeito térmico, degradação, desbalanceamento e queda de tensão sob carga.",
        ),
    )
