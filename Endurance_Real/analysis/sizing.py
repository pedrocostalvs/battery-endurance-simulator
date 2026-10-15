"""Preliminary battery sizing derived from executed Endurance results."""

from dataclasses import dataclass
from math import ceil

import numpy as np

from config.parameters import SimulationConfig
from simulation.results import EnduranceResults


@dataclass(frozen=True)
class BatterySizingAssessment:
    terminal_energy_wh: float
    internal_loss_wh: float
    internal_energy_estimate_wh: float
    required_usable_energy_wh: float
    required_nominal_energy_wh: float
    minimum_pack_capacity_ah: float
    maximum_current_a: float
    mean_current_a: float
    required_peak_c_rate: float
    existing_pack_peak_c_rate: float
    energy_only_min_parallel_cells: int
    existing_nominal_energy_wh: float
    energy_sufficient: bool
    power_within_configured_limit: bool
    electrical_limits_status: str
    pending_limits: tuple[str, ...]


def assess_battery(
    results: EnduranceResults, config: SimulationConfig
) -> BatterySizingAssessment:
    """Assess energy and demand without inventing unavailable cell limits.

    ``energy_only_min_parallel_cells`` is not an approved pack design.  It
    ignores current, voltage, thermal, packaging and regulatory constraints.
    """
    maximum_current = (
        float(np.max(results.battery_current_a))
        if len(results.battery_current_a) else 0.0)
    minimum_parallel = ceil(
        results.minimum_pack_capacity_ah / config.battery.cell_capacity_ah)
    missing = []
    if config.battery.cell_min_voltage_v is None:
        missing.append("Tensão mínima da célula não informada.")
    if config.battery.cell_max_voltage_v is None:
        missing.append("Tensão máxima da célula não informada.")
    if config.battery.cell_max_current_a is None:
        missing.append("Corrente contínua/de pico da célula não informada.")
    missing.append("Limites térmicos e regulamentares não avaliados.")
    return BatterySizingAssessment(
        terminal_energy_wh=results.energy_wh,
        internal_loss_wh=results.internal_loss_wh,
        internal_energy_estimate_wh=results.internal_energy_estimate_wh,
        required_usable_energy_wh=results.required_internal_usable_energy_wh,
        required_nominal_energy_wh=results.required_internal_nominal_energy_wh,
        minimum_pack_capacity_ah=results.minimum_pack_capacity_ah,
        maximum_current_a=maximum_current,
        mean_current_a=results.mean_battery_current_a,
        required_peak_c_rate=results.required_peak_c_rate,
        existing_pack_peak_c_rate=results.existing_pack_peak_c_rate,
        energy_only_min_parallel_cells=minimum_parallel,
        existing_nominal_energy_wh=results.nominal_pack_energy_wh,
        energy_sufficient=(
            results.nominal_pack_energy_wh
            >= results.required_internal_nominal_energy_wh),
        power_within_configured_limit=(
            float(np.max(results.electrical_power_w))
            <= results.max_dc_power_w * (1.0 + 1e-10)),
        electrical_limits_status="PENDING" if missing else "PASS",
        pending_limits=tuple(missing),
    )
