"""Non-blocking Matplotlib output for the Endurance simulation."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simulation.results import EnduranceResults


def _save_plot(path: Path, x, y, title: str, xlabel: str, ylabel: str) -> None:
    figure, axis = plt.subplots(figsize=(10, 5.2), constrained_layout=True)
    axis.plot(x, y, linewidth=1.0)
    axis.set_title(title)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.grid(True, alpha=0.3)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def generate_all_plots(results: EnduranceResults, output_dir: Path) -> tuple[Path, ...]:
    if len(results.time_s) == 0:
        raise ValueError("cannot plot an empty simulation")
    output_dir.mkdir(parents=True, exist_ok=True)
    definitions = (
        ("01_speed_distance.png", results.distance_m, results.speed_m_s,
         "Velocidade × distância — Endurance de referência",
         "Distância (m)", "Velocidade (m/s)"),
        ("02_acceleration_time.png", results.time_s, results.acceleration_m_s2,
         "Aceleração longitudinal × tempo", "Tempo (s)", "Aceleração (m/s²)"),
        ("03_electrical_power_time.png", results.time_s,
         results.electrical_power_w / 1000.0,
         "Potência elétrica DC × tempo", "Tempo (s)", "Potência (kW)"),
        ("04_battery_current_time.png", results.time_s, results.battery_current_a,
         "Corrente DC da bateria × tempo", "Tempo (s)", "Corrente (A)"),
        ("05_battery_voltage_time.png", results.time_s, results.battery_voltage_v,
         "Tensão terminal da bateria × tempo", "Tempo (s)", "Tensão (V)"),
        ("06_soc_distance.png", results.distance_m, results.soc * 100.0,
         "Estado de carga × distância", "Distância (m)", "SoC (%)"),
        ("07_energy_distance.png", results.distance_m, results.cumulative_energy_wh,
         "Energia acumulada × distância", "Distância (m)", "Energia (Wh)"),
    )
    paths = []
    for filename, x, y, title, xlabel, ylabel in definitions:
        path = output_dir / filename
        _save_plot(path, x, y, title, xlabel, ylabel)
        paths.append(path)
    return tuple(paths)
