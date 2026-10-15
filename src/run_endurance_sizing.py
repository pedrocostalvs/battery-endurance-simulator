from pathlib import Path

from endurance_sizing.report import write_markdown_report
from endurance_sizing.scenario import run_initial_hypothetical_scenario


def main() -> int:
    result = run_initial_hypothetical_scenario()
    repository_root = Path(__file__).resolve().parents[1]
    report_path = repository_root / "results" / "endurance_sizing_report.md"
    write_markdown_report(result, report_path)

    energy = result.energy
    pack = result.pack_assessment
    print("=== Dimensionamento preliminar do Endurance ===")
    print("CENÁRIO HIPOTÉTICO")
    print(f"Distância: {energy.distance_m:.6f} m")
    print(f"Tempo: {energy.duration_s:.2f} s")
    print(f"Energia: {energy.energy_wh:.2f} Wh ({energy.energy_kwh:.4f} kWh)")
    print(f"Consumo específico: {energy.specific_energy_wh_km:.2f} Wh/km")
    print(f"Potência DC máxima: {energy.peak_electrical_power_w / 1000:.2f} kW")
    print(f"Potência DC média: {energy.mean_electrical_power_w / 1000:.2f} kW")
    print(f"Energia utilizável requerida com margem: "
          f"{energy.required_usable_energy_wh:.2f} Wh")
    print(f"Energia nominal mínima: {energy.minimum_nominal_energy_wh:.2f} Wh")
    print("Pack genérico atual 144s5p")
    print(f"Energia nominal: {pack.nominal_energy_wh:.2f} Wh")
    print(f"Energia considerada utilizável: {pack.usable_energy_wh:.2f} Wh")
    print(f"Estado geral: {pack.overall_status.value}")
    for check in pack.checks:
        print(f"  {check.name}: {check.status.value} — {check.detail}")
    print(f"Relatório: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
