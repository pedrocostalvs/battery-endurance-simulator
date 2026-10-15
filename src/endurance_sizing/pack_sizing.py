"""Series/parallel pack sizing and explicitly qualified checks."""

from dataclasses import dataclass
from enum import Enum
from math import ceil
from typing import Iterable, Optional, Tuple

from .energy import EnergyResult
from .parameters import CellSpecifications, PackConfiguration, SizingParameters


class CheckStatus(str, Enum):
    PASS = "APROVADO"
    FAIL = "REPROVADO"
    PENDING = "PENDENTE"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class PackAssessment:
    configuration: PackConfiguration
    nominal_voltage_v: float
    nominal_capacity_ah: float
    nominal_energy_wh: float
    usable_energy_wh: float
    min_voltage_v: Optional[float]
    max_voltage_v: Optional[float]
    peak_current_at_nominal_voltage_a: float
    peak_cell_current_at_nominal_voltage_a: float
    peak_c_rate_at_nominal_voltage: float
    cell_count: int
    cell_mass_kg: Optional[float]
    cell_volume_l: Optional[float]
    checks: Tuple[CheckResult, ...]
    overall_status: CheckStatus


def _combine_status(checks: Iterable[CheckResult]) -> CheckStatus:
    statuses = {check.status for check in checks}
    if CheckStatus.FAIL in statuses:
        return CheckStatus.FAIL
    if CheckStatus.PENDING in statuses:
        return CheckStatus.PENDING
    return CheckStatus.PASS


def assess_pack(
    cell: CellSpecifications,
    pack: PackConfiguration,
    energy: EnergyResult,
    sizing: SizingParameters,
) -> PackAssessment:
    nominal_voltage = cell.nominal_voltage_v * pack.series
    nominal_capacity = cell.capacity_ah * pack.parallel
    nominal_energy = nominal_voltage * nominal_capacity
    usable_energy = nominal_energy * sizing.usable_battery_fraction
    min_voltage = (
        cell.min_voltage_v * pack.series
        if cell.min_voltage_v is not None else None
    )
    max_voltage = (
        cell.max_voltage_v * pack.series
        if cell.max_voltage_v is not None else None
    )
    peak_pack_current = energy.peak_electrical_power_w / nominal_voltage
    peak_cell_current = peak_pack_current / pack.parallel
    peak_c_rate = peak_cell_current / cell.capacity_ah

    checks = []
    enough_energy = usable_energy >= energy.required_usable_energy_wh
    checks.append(CheckResult(
        "Energia utilizável",
        CheckStatus.PASS if enough_energy else CheckStatus.FAIL,
        f"{usable_energy:.2f} Wh disponíveis vs. "
        f"{energy.required_usable_energy_wh:.2f} Wh requeridos com margem.",
    ))

    if min_voltage is None or max_voltage is None:
        checks.append(CheckResult(
            "Faixa de tensão das células",
            CheckStatus.PENDING,
            "Tensões mínima e/ou máxima da célula não foram fornecidas.",
        ))
    elif (pack.allowed_min_voltage_v is None
          or pack.allowed_max_voltage_v is None):
        checks.append(CheckResult(
            "Compatibilidade de tensão",
            CheckStatus.PENDING,
            f"Faixa calculada {min_voltage:.2f}–{max_voltage:.2f} V; "
            "faixa permitida pelo sistema não informada.",
        ))
    else:
        voltage_ok = (
            min_voltage >= pack.allowed_min_voltage_v
            and max_voltage <= pack.allowed_max_voltage_v
        )
        checks.append(CheckResult(
            "Compatibilidade de tensão",
            CheckStatus.PASS if voltage_ok else CheckStatus.FAIL,
            f"Pack {min_voltage:.2f}–{max_voltage:.2f} V; sistema "
            f"{pack.allowed_min_voltage_v:.2f}–{pack.allowed_max_voltage_v:.2f} V.",
        ))

    available_current_limits = [
        value for value in (
            pack.max_pack_current_a,
            (cell.max_continuous_current_a * pack.parallel
             if cell.max_continuous_current_a is not None else None),
        ) if value is not None
    ]
    if not available_current_limits:
        checks.append(CheckResult(
            "Corrente contínua",
            CheckStatus.PENDING,
            f"Estimativa no Vnom: {peak_pack_current:.2f} A no pack e "
            f"{peak_cell_current:.2f} A/célula; limites não informados.",
        ))
    else:
        current_limit = min(available_current_limits)
        checks.append(CheckResult(
            "Corrente contínua",
            (CheckStatus.PASS if peak_pack_current <= current_limit
             else CheckStatus.FAIL),
            f"Estimativa no Vnom {peak_pack_current:.2f} A; "
            f"limite aplicável {current_limit:.2f} A.",
        ))

    if cell.max_continuous_c_rate is None:
        checks.append(CheckResult(
            "C-rate contínuo",
            CheckStatus.PENDING,
            f"Estimativa no Vnom: {peak_c_rate:.2f} C; limite não informado.",
        ))
    else:
        checks.append(CheckResult(
            "C-rate contínuo",
            (CheckStatus.PASS if peak_c_rate <= cell.max_continuous_c_rate
             else CheckStatus.FAIL),
            f"Estimativa no Vnom {peak_c_rate:.2f} C; "
            f"limite {cell.max_continuous_c_rate:.2f} C.",
        ))

    if pack.max_pack_power_w is None:
        checks.append(CheckResult(
            "Potência do pack",
            CheckStatus.PENDING,
            f"Pico solicitado {energy.peak_electrical_power_w / 1000:.2f} kW; "
            "limite do pack não informado.",
        ))
    else:
        checks.append(CheckResult(
            "Potência do pack",
            (CheckStatus.PASS
             if energy.peak_electrical_power_w <= pack.max_pack_power_w
             else CheckStatus.FAIL),
            f"Pico {energy.peak_electrical_power_w / 1000:.2f} kW; "
            f"limite {pack.max_pack_power_w / 1000:.2f} kW.",
        ))

    check_tuple = tuple(checks)
    count = pack.series * pack.parallel
    return PackAssessment(
        configuration=pack,
        nominal_voltage_v=nominal_voltage,
        nominal_capacity_ah=nominal_capacity,
        nominal_energy_wh=nominal_energy,
        usable_energy_wh=usable_energy,
        min_voltage_v=min_voltage,
        max_voltage_v=max_voltage,
        peak_current_at_nominal_voltage_a=peak_pack_current,
        peak_cell_current_at_nominal_voltage_a=peak_cell_current,
        peak_c_rate_at_nominal_voltage=peak_c_rate,
        cell_count=count,
        cell_mass_kg=(count * cell.mass_kg if cell.mass_kg is not None else None),
        cell_volume_l=(count * cell.volume_l if cell.volume_l is not None else None),
        checks=check_tuple,
        overall_status=_combine_status(check_tuple),
    )


def enumerate_energy_candidates(
    cell: CellSpecifications,
    minimum_nominal_energy_wh: float,
    series_options: Iterable[int],
    extra_parallel_options: int = 2,
) -> tuple[PackConfiguration, ...]:
    """Enumerate energy-only candidates; electrical approval remains separate."""
    if minimum_nominal_energy_wh <= 0.0:
        raise ValueError("minimum_nominal_energy_wh must be positive")
    if extra_parallel_options < 0:
        raise ValueError("extra_parallel_options must be non-negative")
    candidates = []
    for series in series_options:
        if not isinstance(series, int) or series <= 0:
            raise ValueError("series options must be positive integers")
        energy_per_parallel_wh = series * cell.nominal_voltage_v * cell.capacity_ah
        minimum_parallel = max(1, ceil(minimum_nominal_energy_wh / energy_per_parallel_wh))
        for parallel in range(
            minimum_parallel, minimum_parallel + extra_parallel_options + 1
        ):
            candidates.append(PackConfiguration(series=series, parallel=parallel))
    return tuple(candidates)
