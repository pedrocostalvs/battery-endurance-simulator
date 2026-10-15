# Relatório consolidado — revisão física e energética

## Escopo

Revisão executada exclusivamente em `Endurance_Real/`. O percurso continua
hipotético e nenhum resultado é apresentado como validação experimental.

## Itens A–E

### A — coeficiente de atrito

- Problema: aderência longitudinal próxima de 2 e lateral igual a 0,6.
- Causa: `lambda_mu` do Pacejka reinterpretado como coeficiente absoluto no
  caminho longitudinal.
- Correção: fonte única `TireConfig.friction_coefficient = 0,60` para tração,
  frenagem e curva, com downforce nas cargas normais.
- Arquivos principais: `config/parameters.py`, `models/vehicle.py`,
  `models/braking.py`, `simulation/track.py`, `simulation/endurance.py`.
- Testes: 16 específicos e 26 gerais aprovados.
- Commit: `51037ef` — `fix: unify tire friction coefficient consumers`.

### B — piloto virtual

- Problema: mais de 87 inversões tração↔freio por volta e potência oscilatória.
- Causa: comando sem estado, alvo futuro destravado e feedforward normalizado
  por uma força diferente daquela usada na atuação.
- Correção: máquina de estados, alvo de curva persistente, controle
  feedforward+P, alvo de reta em 99% e limite de taxa do acelerador.
- Arquivos principais: `config/parameters.py`, `simulation/endurance.py`,
  `simulation/results.py` e testes.
- Testes: 18 específicos e 26 gerais aprovados.
- Commit: `783cbb0` — `fix: stabilize virtual driver control`.

### C — voltas e dashboard

- Problema: 22 voltas sobrepostas e ausência de partição robusta por volta.
- Correção: metadados de volta/segmento, `lap_summary()`, dashboard 4×2,
  oito painéis individuais e imagem real em `docs/img/`.
- Arquivos principais: `simulation/results.py`, `visualization/plots.py`,
  `simulation/endurance.py`, README, testes e PNGs.
- Testes: 21 específicos e 26 gerais aprovados.
- Commit: `1c40823` — `feat: add lap analytics and endurance dashboard`.

### D — documentação

- Problema: hipóteses, limitações e interpretação dos resultados estavam
  dispersas.
- Correção: README técnico completo e fator de inércia `0,80` explicitado na
  configuração sem mudar seu valor.
- Arquivos principais: `README.md`, `config/parameters.py` e
  `models/drivetrain.py`.
- Testes: 21 específicos e 26 gerais aprovados.
- Commit: `9d0f7d4` — `docs: document endurance model and validation limits`.

### E — energia e dimensionamento

- Problema: energia terminal era exportada, mas OCV, queda resistiva, perdas
  acumuladas e estimativa interna não eram rastreáveis.
- Correção: históricos elétricos completos, testes de conservação, módulo de
  dimensionamento, diagnóstico de tensão e sensibilidade de sete variáveis.
- Arquivos principais: `models/battery.py` (auditado, equação preservada),
  `simulation/endurance.py`, `simulation/results.py`, `analysis/sizing.py`,
  `scripts/sensitivity_energy.py`, `visualization/plots.py`, ponto de entrada,
  README e testes.
- Testes finais: 25 específicos e 26 gerais aprovados.
- Commit: `feat: validate energy balance and battery sizing`.

## Comparação executada

O “antes” é o baseline imediatamente anterior ao Item A, que continha a
inconsistência longitudinal/lateral citada na especificação.

| Indicador | Antes | Depois | Variação |
|---|---:|---:|---:|
| Tempo total (s) | 1170,17 | 1390,53 | +18,83% |
| Tempo médio por volta (s) | 53,19 | 63,21 | +18,83% |
| Energia terminal (Wh) | 4649,02 | 2642,36 | -43,16% |
| Energia interna/química estimada (Wh) | 5404,54 | 2712,30 | -49,81% |
| Potência DC máxima (kW) | 80,00 | 15,55 | -80,56% |
| SoC final (%) | 33,80 | 66,90 | +33,09 p.p. |
| Aceleração máxima (m/s²) | 11,10 | 2,22 | -80,03% |
| Desaceleração máxima (m/s²) | -16,81 | -6,82 | -59,42% em magnitude |
| Inversões médias por volta | 87,09 | 8,00 | -90,81% |

As maiores diferenças vêm da unificação de μ e da remoção do chattering. Não
houve ajuste para reproduzir energia histórica.

## Dimensionamento preliminar final

| Grandeza | Resultado |
|---|---:|
| Distância | 22,000 km |
| Energia terminal | 2642,36 Wh |
| Perdas internas | 69,94 Wh |
| Energia interna estimada | 2712,30 Wh |
| Consumo específico | 120,11 Wh/km |
| Potência DC máxima | 15,55 kW |
| Corrente DC máxima | 29,46 A |
| Energia utilizável mínima | 3254,76 Wh |
| Energia nominal mínima | 4068,45 Wh |
| Capacidade mínima a 532,8 V | 7,64 Ah |
| C-rate requerido dessa capacidade mínima | 3,86 C |

O pack 144s5p genérico atende energia, mas a aprovação elétrica permanece
pendente. O candidato 144s3p existe apenas pelo critério energético e não deve
ser tratado como configuração segura.

## Dashboard e arquivos gráficos

- `results/00_endurance_dashboard.png`;
- `results/01_speed_lap.png`;
- `results/02_dc_power_lap.png`;
- `results/03_longitudinal_forces_lap.png`;
- `results/04_voltage_current_lap.png`;
- `results/05_lap_energy_time.png`;
- `results/06_lap_soc.png`;
- `results/07_gg_diagram.png`;
- `results/08_power_speed.png`;
- diagnóstico complementar `results/09_battery_voltage_diagnostics.png`.

O mapa 2D da pista não foi criado, pois a sequência não representa geometria
fechada validada.

## Hipóteses novas ou agora explícitas

| Hipótese | Valor | Unidade | Local |
|---|---:|---|---|
| Coeficiente simplificado de aderência | 0,60 | adimensional | `TireConfig` |
| Alvo de reta | 0,99 | fração do limite | `SimulationConfig` |
| Ganho proporcional do piloto | 2,0 | adimensional | `SimulationConfig` |
| Banda de liberação do freio | 0,10 | m/s | `SimulationConfig` |
| Taxa máxima do acelerador | 3,0 | s⁻¹ | `SimulationConfig` |
| Fator de inércia das rodas | 0,80 | adimensional | `DrivetrainConfig` |

Não são parâmetros experimentais. Todos são configuráveis.

## Limitações restantes e dados necessários

- traçado ou telemetria real da pista;
- identificação e datasheet das células;
- tensões mínima e máxima;
- corrente contínua e de pico;
- curva OCV×SoC e resistência por SoC/temperatura;
- limites térmicos, envelhecimento e refrigeração;
- mapas de eficiência do motor e inversor;
- parâmetros longitudinais e laterais medidos dos pneus;
- dados reais de aceleração, frenagem, consumo e estratégia de condução;
- requisitos regulamentares aplicáveis ao acumulador.

## Integridade

- `src/` não foi alterado.
- As suítes específica e geral foram executadas após cada item.
- Um commit local foi preparado por item aprovado.
- Não houve push ou merge.
