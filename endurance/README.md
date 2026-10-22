# Simulador de Endurance (22 km) — Xangô e-Racing

Simula o Endurance de 22 km da Formula SAE Electric para avaliar a bateria:
energia, SoC, tensão, corrente e temperatura das células, com um piloto que
olha as curvas à frente e uma pista baseada em telemetria real.

Reaproveita o código existente por import, sem alterá-lo:

| Parte | De onde vem |
|---|---|
| Aceleração | `Simulation` do Marco (`src/Simulation`), rodada uma vez para gerar o mapa de tração |
| Freio | dados do `BrakeSystem` (`src/Brake.py`) |
| Veículo, motor, pneu, transmissão | classes de `src/Models` |
| Bateria | modelo de tensão do Pedro (`modelo_tensao.py`, sem alterações) |

> Modelo preliminar, **não validado experimentalmente**. A pista é equivalente
> a uma volta de Autocross real, mas não é uma pista oficial de Endurance.

## Como rodar

No VS Code: abra `endurance/rodar_endurance.py` e clique em **Run Python File (▶)**.

Pelo terminal, da raiz do repositório:

```powershell
.\.venv\Scripts\python.exe endurance\rodar_endurance.py
```

Saída em `endurance/resultados/`: `resumo_endurance.txt`, `endurance_resultado.npz`
e os gráficos em `graficos/`.

Testes (41, cerca de 1 min):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s endurance\tests -v
```

Dependências: `numpy`, `scipy` e `matplotlib`.

## Resultado com o ritmo recomendado

| Grandeza | Valor |
|---|---|
| Tempo total | 25,4 min (32 voltas de 46,6 s) |
| Velocidade média / máxima | 52,0 / 93,4 km/h |
| Energia | 4,97 kWh (226 Wh/km) |
| SoC final | 36,2% |
| Tensão do pack | 471 a 585 V |
| Corrente por célula (pico) | 28,4 A |
| Temperatura da célula (máx.) | 48,6 °C |
| Maior média de potência em 60 s | 13,2 kW |

Ritmo recomendado (`piloto.RITMO_ENDURANCE`): teto de 120 N·m no motor e
tirar o pé 0,5 s antes de cada frenagem. Em ritmo de Autocross (piloto sempre
no limite) a bateria chega ao SoC mínimo em 18,8 km.

61% da energia vai para o freio, porque não há regeneração. Por isso rolar
antes de frear é o ajuste que mais economiza: 1 s de rolagem custa 2,8% de
tempo e corta 40% da energia.

## Organização

| Arquivo | Fase | Função |
|---|---|---|
| `parametros.py` | 1 | Todos os parâmetros, marcados como CONHECIDO ou HIPÓTESE |
| `bateria.py` | 1 | Aplica os parâmetros da VTC6 ao modelo de tensão do Pedro |
| `frenagem.py` | 1 | Força pelo pedal e limite de aderência por eixo |
| `motor.py` | 1 | Componentes do código existente, mapa de eficiência do Emrax 228, tabela de perdas |
| `mapa_eficiencia_emrax228.py` | 1 | Contornos do mapa de eficiência digitalizados do manual |
| `tracao.py` | 2 | Mapa de tração gerado pela `Simulation`, com controle de tração |
| `dinamica.py` | 3 | Massa equivalente, resistências, downforce, limites de curva e frenagem |
| `pista.py` | 3 | Pista a partir da telemetria do vídeo |
| `piloto.py` | 4 | Modos acelerar, manter, rolar e frear; parâmetros de ritmo |
| `simulador.py` | 4 | Loop dos 22 km |
| `calibracao.py` | 5 | Validação contra o vídeo, varredura de ritmos, sensibilidade |
| `resultados.py` | 6 | Gráficos e resumo |
| `rodar_endurance.py` | 6 | Ponto de entrada |
| `dados/telemetria_autocross_gopher_2023.csv` | 3 | Velocidade lida do vídeo da Gopher (FSAE Michigan 2023) |

## Equações principais

Dinâmica longitudinal, com massa equivalente das partes girantes
(J_eff igual ao da `Simulation`):

```text
acelerando no limite do pneu:  a = mapa de tração (Simulation)
acelerando com teto de torque: a = (T·N·η/r - F_res) / (m + J_eff·(N/r)²·η)
rolando:                        a = -(F_res + F_vazio) / (m + J_eff·(N/r)²)
freando:                        a = -(F_freio + F_res + F_vazio) / (m + J_eff·(N/r)²)
F_res   = ½ρ·Cd·A·v² + Crr(v)·m·g
F_vazio = perdas em vazio do motor / velocidade (o rotor continua girando)
```

Freio: `p = F_pedal·RedP/A_mestre`, `T_disco = 2·μ_pastilha·p·A_roda·r_disco`,
limitado pela aderência de cada eixo com transferência de carga e balanço de 60%.

Curvas: `m·v²/R <= μ·(m·g + downforce)`. Raio de cada curva da pista:
`R = v_min²/(μ·g)`, com a velocidade mínima do vídeo.

Potência DC: `P = (T·ω + perdas_motor(rpm, T)) / η_inversor`, com as perdas do
mapa do Emrax 228 (perdas em vazio quando o torque é baixo).

## Hipóteses (trocar em `parametros.py` quando houver dado real)

- Distribuição de peso 45/55 (sensibilidade de 50/50 a 40/60: energia muda menos de 3%).
- Massa de 240 kg; se não incluir o piloto, com 310 kg a energia sobe 9% e o SoC final fica em 30%.
- Balanço de freio de 60% na dianteira.
- Arrefecimento do motor a ar ou líquido (28 a 42 kW contínuos).
- Eficiência do inversor de 95%.
- Resistência térmica da célula de 50 K/W (célula sozinha em ar parado).
- SoC mínimo de 20%.

## Pendências

As correções encontradas nos arquivos originais estão registradas no projeto
(`propostas-de-alteracao.md`) para serem aplicadas no final. O simulador
contorna todas elas por conta própria.
