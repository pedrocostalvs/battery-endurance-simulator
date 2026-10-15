"""Saved and interactive Matplotlib output for the Endurance simulation."""

from pathlib import Path

import matplotlib.pyplot as plt

from simulation.results import EnduranceResults


def _plot_definitions(results: EnduranceResults):
    return (
        ("01_speed_distance.png", results.distance_m, results.speed_m_s,
         "Velocidade × distância", "Distância (m)", "Velocidade (m/s)",
         "Velocidade"),
        ("02_acceleration_time.png", results.time_s, results.acceleration_m_s2,
         "Aceleração longitudinal × tempo", "Tempo (s)", "Aceleração (m/s²)",
         "Aceleração"),
        ("03_electrical_power_time.png", results.time_s,
         results.electrical_power_w / 1000.0,
         "Potência elétrica DC × tempo", "Tempo (s)", "Potência (kW)",
         "Potência DC"),
        ("04_battery_current_time.png", results.time_s, results.battery_current_a,
         "Corrente DC da bateria × tempo", "Tempo (s)", "Corrente (A)",
         "Corrente DC"),
        ("05_battery_voltage_time.png", results.time_s, results.battery_voltage_v,
         "Tensão terminal da bateria × tempo", "Tempo (s)", "Tensão (V)",
         "Tensão terminal"),
        ("06_soc_distance.png", results.distance_m, results.soc * 100.0,
         "Estado de carga × distância", "Distância (m)", "SoC (%)", "SoC"),
        ("07_energy_distance.png", results.distance_m, results.cumulative_energy_wh,
         "Energia acumulada × distância", "Distância (m)", "Energia (Wh)",
         "Energia acumulada"),
    )


def _draw_axis(axis, x, y, title: str, xlabel: str, ylabel: str, label: str) -> None:
    axis.plot(x, y, linewidth=1.0, label=label)
    axis.set_title(title, fontsize=10)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.grid(True, alpha=0.3)
    axis.legend(loc="best", fontsize=8)


def _save_plot(
    path: Path, x, y, title: str, xlabel: str, ylabel: str, label: str
) -> None:
    figure, axis = plt.subplots(figsize=(10, 5.2), constrained_layout=True)
    _draw_axis(axis, x, y, title, xlabel, ylabel, label)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def generate_all_plots(results: EnduranceResults, output_dir: Path) -> tuple[Path, ...]:
    if len(results.time_s) == 0:
        raise ValueError("cannot plot an empty simulation")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for definition in _plot_definitions(results):
        filename, x, y, title, xlabel, ylabel, label = definition
        path = output_dir / filename
        _save_plot(path, x, y, title, xlabel, ylabel, label)
        paths.append(path)
    return tuple(paths)


def create_interactive_dashboard(results: EnduranceResults):
    """Create the single 4×2 dashboard without displaying or closing it."""
    if len(results.time_s) == 0:
        raise ValueError("cannot plot an empty simulation")
    figure, axes = plt.subplots(4, 2, figsize=(15, 9), constrained_layout=True)
    flat_axes = axes.ravel()
    for axis, definition in zip(flat_axes, _plot_definitions(results)):
        _filename, x, y, title, xlabel, ylabel, label = definition
        _draw_axis(axis, x, y, title, xlabel, ylabel, label)
    flat_axes[-1].set_visible(False)
    figure.suptitle(
        "Xangô e-Racing — Endurance de referência (22 km)", fontsize=14)
    return figure


def _try_maximize_current_window() -> None:
    """Best-effort maximize for Tk, Qt and wx without backend assumptions."""
    manager = plt.get_current_fig_manager()
    try:
        manager.set_window_title("Xangô e-Racing — Endurance 22 km")
    except (AttributeError, NotImplementedError):
        pass
    window = getattr(manager, "window", None)
    frame = getattr(manager, "frame", None)
    try:
        if window is not None and hasattr(window, "showMaximized"):
            window.showMaximized()                 # Qt
        elif window is not None and hasattr(window, "state"):
            window.state("zoomed")                 # Tk on Windows
        elif frame is not None and hasattr(frame, "Maximize"):
            frame.Maximize(True)                   # wx
    except Exception:
        # Maximization is optional; an unsupported backend must still display.
        pass


def show_interactive_dashboard(
    results: EnduranceResults, *, block: bool = True, show: bool = True
):
    """Display one interactive window and keep it open until the user closes it.

    ``show=False`` is the automation hook: tests can validate the complete
    figure structure without creating a GUI window or blocking execution.
    """
    figure = create_interactive_dashboard(results)
    if not show:
        return figure
    figure.canvas.draw_idle()
    _try_maximize_current_window()
    plt.show(block=block)
    return figure
