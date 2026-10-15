"""Single-click entry point for the physical Xangô Endurance simulation.

Open this file in VS Code and click ``Run Python File``. No PYTHONPATH setup or
working-directory change is required.
"""

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from config.parameters import SimulationConfig  # noqa: E402
from simulation.endurance import EnduranceSimulator  # noqa: E402
from visualization.plots import generate_all_plots  # noqa: E402


def _maximum(values) -> float:
    return float(values.max()) if len(values) else 0.0


def _minimum(values) -> float:
    return float(values.min()) if len(values) else 0.0


def print_summary(results, config: SimulationConfig) -> None:
    print("\n" + "=" * 72)
    print("XANGÔ e-RACING — SIMULAÇÃO FÍSICA DE ENDURANCE")
    print("PERCURSO HIPOTÉTICO DE REFERÊNCIA; NÃO É UMA PISTA REAL VALIDADA")
    print("=" * 72)
    print("\n[Desempenho]")
    print(f"Status:                 {results.status.upper()}")
    print(f"Motivo:                 {results.termination_reason}")
    print(f"Distância:              {results.final_distance_m:.6f} m")
    print(f"Tempo total:            {results.total_time_s:.2f} s")
    print(f"Velocidade média:       {results.mean_speed_m_s:.2f} m/s")
    print(f"Velocidade máxima:      {_maximum(results.speed_m_s):.2f} m/s")
    print(f"Aceleração máxima:      {_maximum(results.acceleration_m_s2):.2f} m/s²")
    print(f"Desaceleração máxima:   {_minimum(results.acceleration_m_s2):.2f} m/s²")
    print(f"Voltas completas:       {results.completed_laps}")
    print(f"Comprimento da volta:   {results.lap_length_m:.2f} m")

    print("\n[Energia]")
    print(f"Energia consumida:      {results.energy_wh:.2f} Wh")
    print(f"Energia consumida:      {results.energy_wh / 1000.0:.4f} kWh")
    print(f"Consumo específico:     {results.specific_energy_wh_km:.2f} Wh/km")
    print(f"Potência DC média:      {results.mean_power_w / 1000.0:.2f} kW")
    print(f"Potência DC máxima:     {_maximum(results.electrical_power_w) / 1000.0:.2f} kW")
    print(f"Energia com margem:     {results.required_usable_energy_wh:.2f} Wh")
    print(f"Energia nominal estim.: {results.estimated_nominal_energy_wh:.2f} Wh")

    print("\n[Bateria]")
    print(f"Configuração:           {config.battery.series_cells}s{config.battery.parallel_cells}p")
    print(f"Energia nominal atual:  {results.nominal_pack_energy_wh:.2f} Wh")
    print(f"SoC inicial/final:      {config.battery.initial_soc * 100:.2f}% / "
          f"{(results.soc[-1] * 100 if len(results.soc) else config.battery.initial_soc * 100):.2f}%")
    print(f"Tensão mínima/máxima:   {_minimum(results.battery_voltage_v):.2f} / "
          f"{_maximum(results.battery_voltage_v):.2f} V")
    print(f"Corrente máxima:        {_maximum(results.battery_current_a):.2f} A")
    print(f"Potência máxima:        {_maximum(results.electrical_power_w) / 1000.0:.2f} kW")
    print(f"Residual elétrico máx.: {results.max_power_residual_w:.3e} W")
    print("Limites pendentes:")
    for item in results.pending_limits:
        print(f"  - {item}")

    print("\n[Hipóteses principais]")
    for item in results.assumptions:
        print(f"  - {item}")


def main() -> int:
    config = SimulationConfig()
    simulator = EnduranceSimulator(config)
    results = simulator.run()
    output_dir = HERE / "results"
    data_path = results.save_npz(output_dir / "endurance_results.npz")
    plot_paths = generate_all_plots(results, output_dir)
    print_summary(results, config)
    print("\n[Arquivos gerados]")
    print(f"  - {data_path}")
    for path in plot_paths:
        print(f"  - {path}")
    return 0 if results.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
