"""Continuous pack model adapted from ``src/Models/BatteryPack.py``.

The original Modified Shepherd discharge voltage is retained, evaluated per
cell and scaled to the pack. The DC current is the stable high-voltage root of
``P = (V_open - R_eq I) I``. No cell datasheet limits are fabricated.
"""

from dataclasses import dataclass
from math import exp, isfinite, sqrt

from config.parameters import BatteryConfig


@dataclass(frozen=True)
class BatteryOperatingPoint:
    requested_power_w: float
    delivered_power_w: float
    current_a: float
    terminal_voltage_v: float
    open_circuit_voltage_v: float
    resistive_loss_w: float
    maximum_mathematical_power_w: float
    residual_w: float
    feasible: bool


class BatteryModel:
    def __init__(self, config: BatteryConfig):
        self.config = config
        self.soc = float(config.initial_soc)
        self.accumulated_charge_c = 0.0
        self.elapsed_s = 0.0
        self.energy_delivered_wh = 0.0
        self.resistive_loss_wh = 0.0

    @property
    def equivalent_resistance_ohm(self) -> float:
        return (self.config.series_cells * self.config.cell_resistance_ohm
                / self.config.parallel_cells)

    def open_circuit_voltage(self) -> float:
        cfg = self.config
        used_ah_per_cell = (1.0 - self.soc) * cfg.cell_capacity_ah
        iast_cell_ah = (
            self.accumulated_charge_c / cfg.parallel_cells / 3600.0)
        denominator = max(cfg.cell_capacity_ah - used_ah_per_cell, 1e-9)
        polarization = (
            cfg.polarization_constant_v * cfg.cell_capacity_ah / denominator)
        cell_voltage = (
            cfg.cell_nominal_voltage_v
            - polarization * iast_cell_ah
            - polarization * used_ah_per_cell
            + cfg.exponential_voltage_v
            * exp(-cfg.exponential_capacity_inv_ah * used_ah_per_cell)
        )
        return cell_voltage * cfg.series_cells

    def solve_power(self, requested_power_w: float) -> BatteryOperatingPoint:
        if not isfinite(requested_power_w) or requested_power_w < 0.0:
            raise ValueError("battery discharge power must be finite and non-negative")
        open_voltage = self.open_circuit_voltage()
        resistance = self.equivalent_resistance_ohm
        maximum_power = open_voltage**2 / (4.0 * resistance)
        feasible = requested_power_w <= maximum_power
        delivered = min(requested_power_w, maximum_power)
        if delivered == 0.0:
            current = 0.0
        else:
            discriminant = max(open_voltage**2 - 4.0 * resistance * delivered, 0.0)
            current = 2.0 * delivered / (open_voltage + sqrt(discriminant))
        terminal_voltage = open_voltage - resistance * current
        residual = terminal_voltage * current - delivered
        values = (current, terminal_voltage, residual, maximum_power)
        if not all(isfinite(value) for value in values) or terminal_voltage <= 0.0:
            raise FloatingPointError("invalid battery operating point")
        return BatteryOperatingPoint(
            requested_power_w=requested_power_w,
            delivered_power_w=delivered,
            current_a=current,
            terminal_voltage_v=terminal_voltage,
            open_circuit_voltage_v=open_voltage,
            resistive_loss_w=current * current * resistance,
            maximum_mathematical_power_w=maximum_power,
            residual_w=residual,
            feasible=feasible,
        )

    def advance(self, point: BatteryOperatingPoint, dt_s: float) -> None:
        if dt_s <= 0.0 or not isfinite(dt_s):
            raise ValueError("dt_s must be finite and positive")
        if not point.feasible:
            raise ValueError("cannot integrate an infeasible battery point")
        charge_c = point.current_a * dt_s
        total_capacity_c = (
            self.config.cell_capacity_ah
            * self.config.parallel_cells
            * 3600.0
        )
        self.accumulated_charge_c += charge_c
        self.soc = max(0.0, self.soc - charge_c / total_capacity_c)
        self.elapsed_s += dt_s
        self.energy_delivered_wh += point.delivered_power_w * dt_s / 3600.0
        self.resistive_loss_wh += point.resistive_loss_w * dt_s / 3600.0

    @property
    def usable_energy_exhausted(self) -> bool:
        return self.soc <= self.config.minimum_usable_soc
