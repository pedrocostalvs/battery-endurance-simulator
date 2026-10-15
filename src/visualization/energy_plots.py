"""Energy plots built from the measured histories of the 75 m sprint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


def _as_valid_history(values: Any, name: str) -> np.ndarray:
    """Return a one-dimensional, finite floating-point history."""
    history = np.asarray(values, dtype=float)
    if history.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional history.")
    if history.size < 2:
        raise ValueError(f"{name} must contain at least two samples.")
    if not np.all(np.isfinite(history)):
        raise ValueError(f"{name} contains non-finite values.")
    return history


def sprint_energy_data(simulation: Any) -> dict[str, np.ndarray]:
    """Build electrical series exclusively from the simulated sprint histories.

    Power is calculated point by point from terminal voltage and DC battery
    current. Cumulative energy uses the same trapezoidal rule as
    ``BatteryCapacity.py``, expressed in Wh.
    """
    time_s = _as_valid_history(simulation.tempo, "tempo")
    voltage_v = _as_valid_history(
        simulation.battery_voltage_hist, "battery_voltage_hist"
    )
    current_a = _as_valid_history(
        simulation.battery_current_hist, "battery_current_hist"
    )
    soc = _as_valid_history(simulation.soc_hist, "soc_hist")

    lengths = {time_s.size, voltage_v.size, current_a.size, soc.size}
    if len(lengths) != 1:
        raise ValueError("Sprint histories must have the same number of samples.")

    delta_time_s = np.diff(time_s)
    if np.any(delta_time_s <= 0.0):
        raise ValueError("tempo must be strictly increasing.")

    power_w = voltage_v * current_a
    energy_increments_wh = (
        0.5 * (power_w[:-1] + power_w[1:]) * delta_time_s / 3600.0
    )
    energy_wh = np.concatenate(([0.0], np.cumsum(energy_increments_wh)))

    return {
        "time_s": time_s,
        "voltage_v": voltage_v,
        "current_a": current_a,
        "power_kw": power_w / 1000.0,
        "soc_percent": soc * 100.0,
        "energy_wh": energy_wh,
    }


def plot_sprint_energy(
    simulation: Any,
    *,
    show: bool = False,
    save_path: str | Path | None = None,
) -> tuple[plt.Figure, dict[str, np.ndarray]]:
    """Create the five energy plots for the simulated 75 m sprint.

    The function does not display a window by default, keeping command-line
    runs and automated tests non-blocking. Pass ``show=True`` for an
    interactive, non-blocking display, or ``save_path`` to write the figure.
    """
    data = sprint_energy_data(simulation)
    time_s = data["time_s"]

    figure, axes_grid = plt.subplots(3, 2, figsize=(14, 12), sharex=True)
    axes = axes_grid.ravel()
    plots = (
        (data["voltage_v"], "Tensão da bateria", "Tensão (V)"),
        (data["current_a"], "Corrente da bateria", "Corrente (A)"),
        (data["power_kw"], "Potência elétrica", "Potência (kW)"),
        (data["soc_percent"], "Estado de carga", "SoC (%)"),
        (data["energy_wh"], "Energia acumulada", "Energia (Wh)"),
    )

    for axis, (values, title, ylabel) in zip(axes, plots):
        axis.plot(time_s, values, linewidth=1.2)
        axis.set_title(title)
        axis.set_xlabel("Tempo (s)")
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.3)

    axes[-1].set_visible(False)
    figure.suptitle("Análise energética — Sprint de aceleração de 75 m")
    figure.tight_layout()

    if save_path is not None:
        figure.savefig(Path(save_path), dpi=150, bbox_inches="tight")
    if show:
        plt.show(block=False)

    return figure, data
