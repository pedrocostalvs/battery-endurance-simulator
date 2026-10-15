"""One-at-a-time energy-sizing sensitivity for the 22 km reference case."""

from csv import DictWriter
from dataclasses import replace
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.sizing import assess_battery  # noqa: E402
from config.parameters import SimulationConfig  # noqa: E402
from simulation.endurance import EnduranceSimulator  # noqa: E402


SCENARIOS = (
    ("reference", "reference", 1.00),
    ("mass_minus_10pct", "mass", 0.90),
    ("mass_plus_10pct", "mass", 1.10),
    ("grip_minus_10pct", "grip", 0.90),
    ("grip_plus_10pct", "grip", 1.10),
    ("rolling_minus_20pct", "rolling", 0.80),
    ("rolling_plus_20pct", "rolling", 1.20),
    ("drag_minus_20pct", "drag", 0.80),
    ("drag_plus_20pct", "drag", 1.20),
    ("efficiency_minus_5pct", "efficiency", 0.95),
    ("efficiency_plus_5pct", "efficiency", 1.05),
    ("resistance_minus_20pct", "resistance", 0.80),
    ("resistance_plus_20pct", "resistance", 1.20),
    ("capacity_minus_20pct", "capacity", 0.80),
    ("capacity_plus_20pct", "capacity", 1.20),
)


def _scenario_config(
    base: SimulationConfig, variable: str, scale: float
) -> SimulationConfig:
    if variable == "mass":
        return replace(
            base, vehicle=replace(base.vehicle, mass_kg=base.vehicle.mass_kg * scale))
    if variable == "grip":
        return replace(
            base,
            tire=replace(
                base.tire,
                friction_coefficient=base.tire.friction_coefficient * scale,
            ),
        )
    if variable == "rolling":
        return replace(
            base,
            vehicle=replace(
                base.vehicle,
                rolling_resistance=base.vehicle.rolling_resistance * scale,
            ),
        )
    if variable == "drag":
        return replace(
            base,
            vehicle=replace(
                base.vehicle,
                drag_coefficient=base.vehicle.drag_coefficient * scale,
            ),
        )
    if variable == "efficiency":
        return replace(
            base,
            motor=replace(
                base.motor,
                motor_efficiency=min(base.motor.motor_efficiency * scale, 1.0),
            ),
        )
    if variable == "resistance":
        return replace(
            base,
            battery=replace(
                base.battery,
                cell_resistance_ohm=base.battery.cell_resistance_ohm * scale,
            ),
        )
    if variable == "capacity":
        return replace(
            base,
            battery=replace(
                base.battery,
                cell_capacity_ah=base.battery.cell_capacity_ah * scale,
            ),
        )
    if variable == "reference":
        return base
    raise ValueError(f"unknown sensitivity variable: {variable}")


def run_sensitivity(output_dir: Path | None = None) -> tuple[dict[str, object], ...]:
    base = SimulationConfig()
    rows = []
    for name, variable, scale in SCENARIOS:
        config = _scenario_config(base, variable, scale)
        result = EnduranceSimulator(config).run()
        sizing = assess_battery(result, config)
        row = {
            "scenario": name,
            "variable": variable,
            "scale": scale,
            "status": result.status,
            "time_s": result.total_time_s,
            "terminal_energy_wh": result.energy_wh,
            "internal_loss_wh": result.internal_loss_wh,
            "internal_energy_estimate_wh": result.internal_energy_estimate_wh,
            "required_nominal_energy_wh": sizing.required_nominal_energy_wh,
            "maximum_dc_power_w": float(np.max(result.electrical_power_w)),
            "maximum_current_a": float(np.max(result.battery_current_a)),
            "final_soc": float(result.soc[-1]),
        }
        rows.append(row)
        print(
            f"{name}: {result.status}, "
            f"E_internal={result.internal_energy_estimate_wh:.2f} Wh")

    reference_energy = float(rows[0]["internal_energy_estimate_wh"])
    for row in rows:
        row["internal_energy_change_percent"] = (
            (float(row["internal_energy_estimate_wh"]) / reference_energy - 1.0)
            * 100.0)

    destination = output_dir or ROOT / "results"
    destination.mkdir(parents=True, exist_ok=True)
    fieldnames = tuple(rows[0])
    with (destination / "energy_sensitivity.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    markdown = [
        "# Sensibilidade energética",
        "",
        "Variação de um parâmetro por vez sobre o cenário hipotético. Os fatores",
        "não representam incertezas medidas e não constituem calibração.",
        "",
        "| Cenário | Tempo (s) | E terminal (Wh) | Perdas (Wh) | "
        "E interna estim. (Wh) | Variação (%) | Nominal mín. (Wh) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        markdown.append(
            f"| {row['scenario']} | {row['time_s']:.2f} | "
            f"{row['terminal_energy_wh']:.2f} | {row['internal_loss_wh']:.2f} | "
            f"{row['internal_energy_estimate_wh']:.2f} | "
            f"{row['internal_energy_change_percent']:+.2f} | "
            f"{row['required_nominal_energy_wh']:.2f} |"
        )
    ranked = sorted(
        rows[1:],
        key=lambda item: abs(float(item["internal_energy_change_percent"])),
        reverse=True,
    )
    markdown.extend((
        "",
        "## Maiores variações absolutas de energia interna estimada",
        "",
    ))
    for row in ranked:
        markdown.append(
            f"- `{row['scenario']}`: "
            f"{row['internal_energy_change_percent']:+.2f}%")
    (destination / "energy_sensitivity.md").write_text(
        "\n".join(markdown) + "\n", encoding="utf-8")
    return tuple(rows)


if __name__ == "__main__":
    run_sensitivity()
