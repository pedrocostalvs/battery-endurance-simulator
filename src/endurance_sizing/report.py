from pathlib import Path

from .scenario import ScenarioResult


def _fmt_optional(value, unit: str) -> str:
    return "Não conhecida" if value is None else f"{value:.2f} {unit}"


def render_markdown(result: ScenarioResult) -> str:
    energy = result.energy
    assessment = result.pack_assessment
    vehicle = result.vehicle
    efficiencies = result.efficiencies
    sizing = result.sizing

    check_rows = "\n".join(
        f"| {check.name} | {check.status.value} | {check.detail} |"
        for check in assessment.checks
    )
    candidate_rows = "\n".join(
        f"| {candidate.series}s{candidate.parallel}p | "
        f"{candidate.series * candidate.parallel} | "
        f"{candidate.series * result.cell.nominal_voltage_v:.2f} | "
        f"{candidate.series * candidate.parallel * result.cell.nominal_voltage_v * result.cell.capacity_ah:.2f} |"
        for candidate in result.energy_candidates
    )
    sensitivity_rows = "\n".join(
        f"| {point.parameter} | {point.factor:.2f} | {point.energy_wh:.2f} | "
        f"{point.specific_energy_wh_km:.2f} | {point.minimum_nominal_energy_wh:.2f} |"
        for point in result.sensitivity
    )
    known = "\n".join(f"- {item}" for item in result.known_parameters)
    assumptions = "\n".join(f"- {item}" for item in result.assumptions)
    missing = "\n".join(f"- {item}" for item in result.missing_information)
    profile_assumptions = "\n".join(
        f"- {item}" for item in result.cycle.assumptions)

    voltage_range = (
        "Não conhecida: faltam tensões mínima e máxima da célula."
        if assessment.min_voltage_v is None or assessment.max_voltage_v is None
        else f"{assessment.min_voltage_v:.2f}–{assessment.max_voltage_v:.2f} V"
    )

    return f"""# Dimensionamento energético preliminar — Endurance 22 km

> **Cenário hipotético.** Este relatório não usa o Sprint de 75 m repetido e não
> substitui telemetria, datasheet de célula, análise térmica ou validação elétrica.

## Resultado principal

| Resultado | Valor |
|---|---:|
| Distância integrada | {energy.distance_m:.6f} m |
| Duração estimada | {energy.duration_s:.2f} s |
| Energia elétrica efetivamente consumida | {energy.energy_wh:.2f} Wh |
| Energia elétrica efetivamente consumida | {energy.energy_kwh:.4f} kWh |
| Consumo específico | {energy.specific_energy_wh_km:.2f} Wh/km |
| Potência elétrica máxima | {energy.peak_electrical_power_w / 1000:.2f} kW |
| Potência elétrica média | {energy.mean_electrical_power_w / 1000:.2f} kW |
| Energia utilizável requerida, com margem | {energy.required_usable_energy_wh:.2f} Wh |
| Energia nominal mínima | {energy.minimum_nominal_energy_wh:.2f} Wh |

A energia nominal mínima é maior que a energia utilizável requerida porque somente
{sizing.usable_battery_fraction:.0%} da energia nominal foi considerada utilizável.
Isso não constitui aprovação elétrica ou de segurança do pack.

## Perfil velocidade–tempo

- Nome: {result.cycle.name}
- Origem: {result.cycle.source}
- Distância do ciclo hipotético: {result.cycle.distance_m:.2f} m
- Duração do ciclo: {result.cycle.duration_s:.2f} s
- Velocidade máxima assumida: {result.cycle.velocity_m_s.max():.2f} m/s
- O último trecho foi encurtado analiticamente para terminar em 22.000 m.

{profile_assumptions}

## Parâmetros longitudinais

| Parâmetro | Valor |
|---|---:|
| Massa | {vehicle.mass_kg:.2f} kg |
| Coeficiente de arrasto | {vehicle.drag_coefficient:.4f} |
| Área frontal | {vehicle.frontal_area_m2:.4f} m² |
| Coeficiente de rolamento | {vehicle.rolling_resistance_coefficient:.4f} |
| Densidade do ar | {vehicle.air_density_kg_m3:.3f} kg/m³ |
| Inclinação | {vehicle.road_grade_rad:.4f} rad |
| Eficiência da transmissão | {efficiencies.transmission:.4f} |
| Eficiência do motor | {efficiencies.motor:.4f} |
| Eficiência do inversor | {efficiencies.inverter:.4f} |
| Eficiência total | {efficiencies.total:.4f} |
| Regeneração | Não |
| Potência auxiliar | {sizing.auxiliary_power_w:.2f} W |
| Margem energética | {sizing.sizing_margin_fraction:.0%} |
| Fração utilizável | {sizing.usable_battery_fraction:.0%} |

## Equações

```text
F_dem = m·a + Crr·m·g·cos(θ) + 0,5·ρ·Cd·A·v² + m·g·sin(θ)
P_roda = F_dem·v
P_DC = max(P_roda, 0)/(η_trans·η_motor·η_inv) + P_aux
E_DC = Σ(P_DC·Δt)/3600
E_util_requerida = E_DC·(1 + margem)
E_nominal_mínima = E_util_requerida/fração_utilizável
```

Potência mecânica negativa é descartada: não há crédito de regeneração.

## Comparação com o pack genérico 144s5p

| Propriedade | Valor |
|---|---:|
| Célula | {result.cell.name} |
| Células | {assessment.cell_count} |
| Tensão nominal | {assessment.nominal_voltage_v:.2f} V |
| Capacidade nominal | {assessment.nominal_capacity_ah:.2f} Ah |
| Energia nominal | {assessment.nominal_energy_wh:.2f} Wh |
| Energia considerada utilizável | {assessment.usable_energy_wh:.2f} Wh |
| Faixa operacional de tensão | {voltage_range} |
| Corrente de pico estimada em Vnom | {assessment.peak_current_at_nominal_voltage_a:.2f} A |
| Corrente por célula estimada em Vnom | {assessment.peak_cell_current_at_nominal_voltage_a:.2f} A |
| C-rate estimado em Vnom | {assessment.peak_c_rate_at_nominal_voltage:.2f} C |
| Massa apenas das células | {_fmt_optional(assessment.cell_mass_kg, 'kg')} |
| Volume apenas das células | {_fmt_optional(assessment.cell_volume_l, 'L')} |
| Estado geral | **{assessment.overall_status.value}** |

As estimativas de corrente usam a tensão nominal. Sem tensão mínima e curva sob
carga, elas não representam o pior caso e não podem aprovar a configuração.

| Verificação | Estado | Detalhe |
|---|---|---|
{check_rows}

## Configurações 144s candidatas por energia

Esta tabela filtra somente energia nominal. Nenhuma configuração é declarada
eletricamente segura sem limites de tensão, corrente, potência, temperatura e C-rate.

| Configuração | Células | V nominal (V) | Energia nominal (Wh) |
|---|---:|---:|---:|
{candidate_rows}

## Análise de sensibilidade

Variação one-at-a-time de ±10%. A faixa é exploratória e não representa tolerância
de fabricação nem incerteza estatística.

| Parâmetro | Fator | Energia (Wh) | Wh/km | Energia nominal mínima (Wh) |
|---|---:|---:|---:|---:|
{sensitivity_rows}

## Parâmetros conhecidos

{known}

## Hipóteses

{assumptions}

## Informações ainda necessárias

{missing}

## Limitações

- Modelo longitudinal prescrito; não verifica aderência nem capacidade de seguir o perfil.
- Eficiências constantes, sem mapas de rotação, torque ou temperatura.
- Não inclui perdas térmicas, degradação, desbalanceamento ou consumo auxiliar real.
- Não calcula queda de tensão do pack nem evolução de SoC.
- A aprovação energética não implica aprovação de tensão, corrente, potência ou segurança.
"""


def write_markdown_report(result: ScenarioResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(result), encoding="utf-8")
    return path
