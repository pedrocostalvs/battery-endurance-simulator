# Dimensionamento energético preliminar — Endurance 22 km

> **Cenário hipotético.** Este relatório não usa o Sprint de 75 m repetido e não
> substitui telemetria, datasheet de célula, análise térmica ou validação elétrica.

## Resultado principal

| Resultado | Valor |
|---|---:|
| Distância integrada | 22000.000000 m |
| Duração estimada | 1395.55 s |
| Energia elétrica efetivamente consumida | 1828.53 Wh |
| Energia elétrica efetivamente consumida | 1.8285 kWh |
| Consumo específico | 83.12 Wh/km |
| Potência elétrica máxima | 23.50 kW |
| Potência elétrica média | 4.72 kW |
| Energia utilizável requerida, com margem | 2194.24 Wh |
| Energia nominal mínima | 2742.80 Wh |

A energia nominal mínima é maior que a energia utilizável requerida porque somente
80% da energia nominal foi considerada utilizável.
Isso não constitui aprovação elétrica ou de segurança do pack.

## Perfil velocidade–tempo

- Nome: Ciclo hipotético de Endurance
- Origem: Cenário sintético; não deriva do Sprint de 75 m
- Distância do ciclo hipotético: 1026.00 m
- Duração do ciclo: 65.00 s
- Velocidade máxima assumida: 22.00 m/s
- O último trecho foi encurtado analiticamente para terminar em 22.000 m.

- Perfil linear por trechos com velocidades entre 0 e 22 m/s.
- O ciclo contém aceleração, retas, curvas lentas e frenagem.
- A frenagem não recupera energia.
- O ciclo é repetido como volta representativa apenas neste cenário hipotético.

## Parâmetros longitudinais

| Parâmetro | Valor |
|---|---:|
| Massa | 240.00 kg |
| Coeficiente de arrasto | 0.7789 |
| Área frontal | 0.6800 m² |
| Coeficiente de rolamento | 0.0150 |
| Densidade do ar | 1.225 kg/m³ |
| Inclinação | 0.0000 rad |
| Eficiência da transmissão | 0.9506 |
| Eficiência do motor | 0.9000 |
| Eficiência do inversor | 0.9500 |
| Eficiência total | 0.8128 |
| Regeneração | Não |
| Potência auxiliar | 0.00 W |
| Margem energética | 20% |
| Fração utilizável | 80% |

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
| Célula | Li-ion genérica do modelo existente (sem datasheet) |
| Células | 720 |
| Tensão nominal | 532.80 V |
| Capacidade nominal | 15.00 Ah |
| Energia nominal | 7992.00 Wh |
| Energia considerada utilizável | 6393.60 Wh |
| Faixa operacional de tensão | Não conhecida: faltam tensões mínima e máxima da célula. |
| Corrente de pico estimada em Vnom | 44.10 A |
| Corrente por célula estimada em Vnom | 8.82 A |
| C-rate estimado em Vnom | 2.94 C |
| Massa apenas das células | 32.40 kg |
| Volume apenas das células | 18.00 L |
| Estado geral | **PENDENTE** |

As estimativas de corrente usam a tensão nominal. Sem tensão mínima e curva sob
carga, elas não representam o pior caso e não podem aprovar a configuração.

| Verificação | Estado | Detalhe |
|---|---|---|
| Energia utilizável | APROVADO | 6393.60 Wh disponíveis vs. 2194.24 Wh requeridos com margem. |
| Faixa de tensão das células | PENDENTE | Tensões mínima e/ou máxima da célula não foram fornecidas. |
| Corrente contínua | PENDENTE | Estimativa no Vnom: 44.10 A no pack e 8.82 A/célula; limites não informados. |
| C-rate contínuo | PENDENTE | Estimativa no Vnom: 2.94 C; limite não informado. |
| Potência do pack | PENDENTE | Pico solicitado 23.50 kW; limite do pack não informado. |

## Configurações 144s candidatas por energia

Esta tabela filtra somente energia nominal. Nenhuma configuração é declarada
eletricamente segura sem limites de tensão, corrente, potência, temperatura e C-rate.

| Configuração | Células | V nominal (V) | Energia nominal (Wh) |
|---|---:|---:|---:|
| 144s2p | 288 | 532.80 | 3196.80 |
| 144s3p | 432 | 532.80 | 4795.20 |
| 144s4p | 576 | 532.80 | 6393.60 |

## Análise de sensibilidade

Variação one-at-a-time de ±10%. A faixa é exploratória e não representa tolerância
de fabricação nem incerteza estatística.

| Parâmetro | Fator | Energia (Wh) | Wh/km | Energia nominal mínima (Wh) |
|---|---:|---:|---:|---:|
| mass | 0.90 | 1713.78 | 77.90 | 2570.67 |
| mass | 1.00 | 1828.53 | 83.12 | 2742.80 |
| mass | 1.10 | 1943.29 | 88.33 | 2914.93 |
| drag_coefficient | 0.90 | 1760.44 | 80.02 | 2640.65 |
| drag_coefficient | 1.00 | 1828.53 | 83.12 | 2742.80 |
| drag_coefficient | 1.10 | 1896.63 | 86.21 | 2844.95 |
| rolling_resistance | 0.90 | 1806.56 | 82.12 | 2709.85 |
| rolling_resistance | 1.00 | 1828.53 | 83.12 | 2742.80 |
| rolling_resistance | 1.10 | 1850.50 | 84.11 | 2775.76 |
| motor_efficiency | 0.90 | 2031.70 | 92.35 | 3047.56 |
| motor_efficiency | 1.00 | 1828.53 | 83.12 | 2742.80 |
| motor_efficiency | 1.10 | 1662.30 | 75.56 | 2493.46 |

## Parâmetros conhecidos

- Massa, Cd, área frontal e Crr copiados da configuração atual.
- Eficiência da transmissão: 0,98 × 0,97 = 0,9506.
- Pack atual: 144s5p; célula genérica: 3,7 V e 3,0 Ah.
- Distância-alvo solicitada: 22.000 m.

## Hipóteses

- Perfil velocidade-tempo sintético, não medido e não derivado do Sprint.
- Eficiência constante do motor: 90% (hipótese).
- Eficiência constante do inversor: 95% (hipótese existente na interface).
- Margem energética: 20% (hipótese configurável).
- Fração utilizável da energia nominal: 80% (hipótese configurável).
- Potência auxiliar: 0 W; cargas auxiliares ainda não informadas.
- Pista plana e frenagem sem regeneração.
- Sensibilidade one-at-a-time de ±10% (faixa exploratória, não tolerância).

## Informações ainda necessárias

- Telemetria ou perfil de velocidade real do Endurance.
- Modelo/datasheet da célula e tensões mínima e máxima.
- Limites contínuos e de pico de corrente e C-rate da célula.
- Faixa de tensão, corrente e potência permitida pelo sistema.
- Mapa de eficiência do motor e do inversor.
- Consumo dos sistemas auxiliares.
- Efeito térmico, degradação, desbalanceamento e queda de tensão sob carga.

## Limitações

- Modelo longitudinal prescrito; não verifica aderência nem capacidade de seguir o perfil.
- Eficiências constantes, sem mapas de rotação, torque ou temperatura.
- Não inclui perdas térmicas, degradação, desbalanceamento ou consumo auxiliar real.
- Não calcula queda de tensão do pack nem evolução de SoC.
- A aprovação energética não implica aprovação de tensão, corrente, potência ou segurança.
