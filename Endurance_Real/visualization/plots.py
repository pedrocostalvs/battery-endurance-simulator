"""Saved and interactive Matplotlib dashboard for the Endurance simulation."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from simulation.results import EnduranceResults


PANEL_FILES = (
    "01_speed_lap.png",
    "02_dc_power_lap.png",
    "03_longitudinal_forces_lap.png",
    "04_voltage_current_lap.png",
    "05_lap_energy_time.png",
    "06_lap_soc.png",
    "07_gg_diagram.png",
    "08_power_speed.png",
)


def _reference_lap_mask(
    results: EnduranceResults, reference_lap: int
) -> tuple[np.ndarray, int]:
    available = max(int(np.max(results.lap_index)) + 1, 1)
    selected = min(max(int(reference_lap), 1), available)
    return results.lap_index == selected - 1, selected


def _shade_corners(axis, results: EnduranceResults) -> None:
    labelled = False
    for start, end, is_corner in zip(
        results.segment_boundaries_m[:-1],
        results.segment_boundaries_m[1:],
        results.segment_is_corner,
    ):
        if is_corner:
            axis.axvspan(
                start,
                end,
                color="tab:orange",
                alpha=0.13,
                label="Segmento de curva" if not labelled else None,
                zorder=0,
            )
            labelled = True


def _combined_legend(axis, secondary=None, *, location: str = "best") -> None:
    handles, labels = axis.get_legend_handles_labels()
    if secondary is not None:
        other_handles, other_labels = secondary.get_legend_handles_labels()
        handles += other_handles
        labels += other_labels
    if handles:
        axis.legend(handles, labels, loc=location, fontsize=8)


def _draw_panel(
    kind: int,
    figure,
    axis,
    results: EnduranceResults,
    reference_mask: np.ndarray,
) -> None:
    position = results.lap_position_m[reference_mask]
    lap_rows = results.lap_summary()
    laps = np.asarray([row.lap_index + 1 for row in lap_rows])

    if kind == 0:
        axis.plot(
            position, results.speed_m_s[reference_mask] * 3.6,
            label="Velocidade", linewidth=1.2)
        axis.step(
            position, results.speed_limit_m_s[reference_mask] * 3.6,
            where="post", linestyle="--", label="Limite local", linewidth=1.0)
        axis.set_title("Velocidade × posição na volta")
        axis.set_xlabel("Posição na volta (m)")
        axis.set_ylabel("Velocidade (km/h)")
        _shade_corners(axis, results)
        _combined_legend(axis)
    elif kind == 1:
        axis.plot(
            position, results.electrical_power_w[reference_mask] / 1000.0,
            label="Potência DC", linewidth=1.1)
        axis.axhline(
            results.max_dc_power_w / 1000.0, color="tab:red", linestyle="--",
            label=f"Limite configurado ({results.max_dc_power_w / 1000.0:.0f} kW)")
        axis.set_title("Potência DC × posição")
        axis.set_xlabel("Posição na volta (m)")
        axis.set_ylabel("Potência DC (kW)")
        _shade_corners(axis, results)
        _combined_legend(axis)
    elif kind == 2:
        axis.plot(
            position, results.drive_force_n[reference_mask],
            label="Tração", linewidth=1.1)
        axis.plot(
            position, -results.brake_force_n[reference_mask],
            label="Frenagem", linewidth=1.1)
        axis.axhline(0.0, color="black", linewidth=0.7)
        axis.set_title("Forças longitudinais × posição")
        axis.set_xlabel("Posição na volta (m)")
        axis.set_ylabel("Força longitudinal (N)")
        _shade_corners(axis, results)
        _combined_legend(axis)
    elif kind == 3:
        secondary = axis.twinx()
        axis.plot(
            position, results.battery_voltage_v[reference_mask],
            color="tab:blue", label="Tensão terminal", linewidth=1.1)
        secondary.plot(
            position, results.battery_current_a[reference_mask],
            color="tab:red", label="Corrente DC", linewidth=1.0)
        axis.set_title("Tensão e corrente × posição")
        axis.set_xlabel("Posição na volta (m)")
        axis.set_ylabel("Tensão terminal (V)", color="tab:blue")
        secondary.set_ylabel("Corrente DC (A)", color="tab:red")
        _shade_corners(axis, results)
        _combined_legend(axis, secondary)
    elif kind == 4:
        energy = np.asarray([row.terminal_energy_wh for row in lap_rows])
        lap_time = np.asarray([row.time_s for row in lap_rows])
        secondary = axis.twinx()
        axis.bar(laps, energy, color="tab:blue", alpha=0.75, label="Energia")
        secondary.plot(
            laps, lap_time, color="tab:red", marker="o", markersize=3,
            label="Tempo")
        axis.set_title("Energia e tempo por volta")
        axis.set_xlabel("Volta")
        axis.set_ylabel("Energia terminal (Wh)", color="tab:blue")
        secondary.set_ylabel("Tempo da volta (s)", color="tab:red")
        axis.set_xticks(laps)
        _combined_legend(axis, secondary)
    elif kind == 5:
        final_soc = np.asarray([row.final_soc for row in lap_rows]) * 100.0
        axis.plot(laps, final_soc, marker="o", markersize=3, label="SoC final")
        axis.axhline(
            results.minimum_usable_soc * 100.0,
            color="tab:red", linestyle="--",
            label="SoC mínimo utilizável")
        axis.set_title("SoC final de cada volta")
        axis.set_xlabel("Volta")
        axis.set_ylabel("SoC (%)")
        axis.set_xticks(laps)
        _combined_legend(axis)
    elif kind == 6:
        lateral_g = (
            results.lateral_force_n[reference_mask]
            / (results.vehicle_mass_kg * results.gravity_m_s2))
        longitudinal_g = (
            results.acceleration_m_s2[reference_mask] / results.gravity_m_s2)
        scatter = axis.scatter(
            lateral_g,
            longitudinal_g,
            c=results.speed_m_s[reference_mask] * 3.6,
            s=7,
            cmap="viridis",
            alpha=0.75,
        )
        colorbar = figure.colorbar(scatter, ax=axis)
        colorbar.set_label("Velocidade (km/h)")
        axis.axhline(0.0, color="black", linewidth=0.6)
        axis.axvline(0.0, color="black", linewidth=0.6)
        axis.set_title("Diagrama g-g simplificado")
        axis.set_xlabel("Aceleração lateral (g)")
        axis.set_ylabel("Aceleração longitudinal (g)")
    elif kind == 7:
        axis.scatter(
            results.speed_m_s * 3.6,
            results.electrical_power_w / 1000.0,
            s=4,
            alpha=0.35,
            label="Amostras da prova",
        )
        axis.axhline(
            results.max_dc_power_w / 1000.0,
            color="tab:red", linestyle="--",
            label=f"Limite configurado ({results.max_dc_power_w / 1000.0:.0f} kW)")
        axis.set_title("Potência DC × velocidade")
        axis.set_xlabel("Velocidade (km/h)")
        axis.set_ylabel("Potência DC (kW)")
        _combined_legend(axis)
    else:
        raise ValueError(f"unknown dashboard panel: {kind}")

    axis.grid(True, alpha=0.25)


def create_interactive_dashboard(
    results: EnduranceResults, reference_lap: int = 2
):
    """Create the 4×2 dashboard without displaying or closing it."""
    if len(results.time_s) == 0:
        raise ValueError("cannot plot an empty simulation")
    mask, selected_lap = _reference_lap_mask(results, reference_lap)
    figure, axes = plt.subplots(4, 2, figsize=(15, 11), constrained_layout=True)
    primary_axes = tuple(axes.ravel())
    for kind, axis in enumerate(primary_axes):
        _draw_panel(kind, figure, axis, results, mask)
    figure.suptitle(
        f"Xangô e-Racing — Endurance 22 km — volta de referência {selected_lap}",
        fontsize=14,
    )
    return figure


def generate_all_plots(
    results: EnduranceResults, output_dir: Path
) -> tuple[Path, ...]:
    """Save one complete dashboard and each of its eight panels."""
    if len(results.time_s) == 0:
        raise ValueError("cannot plot an empty simulation")
    output_dir.mkdir(parents=True, exist_ok=True)
    mask, _selected_lap = _reference_lap_mask(results, 2)
    paths = []

    dashboard_path = output_dir / "00_endurance_dashboard.png"
    dashboard = create_interactive_dashboard(results, reference_lap=2)
    dashboard.savefig(dashboard_path, dpi=180)
    plt.close(dashboard)
    paths.append(dashboard_path)

    for kind, filename in enumerate(PANEL_FILES):
        figure, axis = plt.subplots(figsize=(10, 5.8), constrained_layout=True)
        _draw_panel(kind, figure, axis, results, mask)
        path = output_dir / filename
        figure.savefig(path, dpi=180)
        plt.close(figure)
        paths.append(path)
    return tuple(paths)


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
            window.showMaximized()
        elif window is not None and hasattr(window, "state"):
            window.state("zoomed")
        elif frame is not None and hasattr(frame, "Maximize"):
            frame.Maximize(True)
    except Exception:
        pass


def show_interactive_dashboard(
    results: EnduranceResults,
    *,
    reference_lap: int = 2,
    block: bool = True,
    show: bool = True,
):
    """Display one interactive dashboard until the user closes it."""
    figure = create_interactive_dashboard(results, reference_lap=reference_lap)
    if not show:
        return figure
    figure.canvas.draw_idle()
    _try_maximize_current_window()
    plt.show(block=block)
    return figure
