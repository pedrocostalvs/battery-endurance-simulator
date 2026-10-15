# Simulador físico de Endurance — Xangô e-Racing

Implementação independente para estudar o comportamento longitudinal e elétrico
do veículo ao longo de 22 km. O código original do repositório permanece intacto.

Este modelo é preliminar e **não foi validado experimentalmente**. O percurso é
hipotético e não representa uma pista oficial.

## Execução pelo VS Code

1. Abra `Endurance_Real/run_endurance.py`.
2. Selecione o interpretador `.venv/Scripts/python.exe` no VS Code.
3. Clique em **Run Python File (▶)**.

O arquivo resolve seus próprios imports a partir da localização física, portanto
não exige alteração de `PYTHONPATH` nem mudança do diretório do terminal.

Pelo PowerShell, a execução equivalente é:

```powershell
.\.venv\Scripts\python.exe Endurance_Real\run_endurance.py
```

## Organização

- `config/parameters.py`: dados conhecidos e hipóteses configuráveis.
- `models/`: bateria, motor, transmissão, veículo e frenagem adaptados.
- `simulation/track.py`: pista de referência e limites de velocidade em curva.
- `simulation/endurance.py`: estratégia de condução e integração acoplada.
- `simulation/results.py`: resultados e exportação numérica.
- `visualization/plots.py`: sete gráficos Matplotlib não bloqueantes.
- `tests/`: testes físicos, numéricos e de execução.
- `results/`: gráficos e dados gerados.

## Equações principais

Dinâmica longitudinal com massa equivalente:

```text
m_eq dv/dt = F_tração - F_freio - F_aero - F_rolamento - F_inclinação
F_aero = 0,5 ρ Cd A v²
F_rolamento = Crr(v) m g cos(θ)
F_inclinação = m g sin(θ)
```

A massa equivalente soma a massa translacional e as inércias rotacionais
convertidas por equivalência de energia cinética. Nenhuma inércia é contada em
um segundo corpo dinâmico.

O limite longitudinal disponível usa círculo de atrito:

```text
F_long,max = sqrt[(μ Fz)² - F_lateral²]
F_lateral = m v²/R
```

O limite de curva é obtido de `m v²/R <= μ(mg + F_downforce)`. A estratégia de
condução olha à frente e inicia a frenagem quando a distância até uma curva é
menor que a distância cinemática necessária. A velocidade não é prescrita.

Motor e transmissão:

```text
T_max = 1,5 p λm iq,max
P_mec,max = P_DC,max η_motor η_inversor
F_roda = (T_motor - kf ωmotor) N ηtrans / rroda
```

Bateria, na raiz estável de alta tensão:

```text
Vterminal = Vaberto(SoC, carga acumulada) - Req I
PDC = Vterminal I
I = 2PDC / [Vaberto + sqrt(Vaberto² - 4 Req PDC)]
dSoC/dt = -I / (Qpack 3600)
Pperda = I² Req
```

Não há regeneração. Durante frenagem, a potência elétrica de tração é zero.

## Origem dos dados

Vieram da configuração existente: massa 240 kg, raio 0,26 m, Cd 0,7789, área
frontal 0,68 m², Crr 0,015, transmissão 5:1 com eficiências 0,98 e 0,97,
parâmetros do PMSM, limite configurado de 323 A de fase, referência de rotação
575,96 rad/s, pack genérico 144s5p e parâmetros hidráulicos de `Brake.py`.

Os modelos adaptados preservam a origem conceitual dos módulos existentes. A
frenagem nova separa força no pedal, pressão, força normal das pastilhas, torque
nos discos, força nas rodas e aderência. A resistência ao rolamento é aplicada
somente pela dinâmica do veículo, evitando dupla contagem.

## Hipóteses configuráveis

- pista plana de referência com oito segmentos e uma volta de 1 km;
- raios das curvas do cenário de referência;
- eficiência constante do motor de 90% e inversor de 95%;
- SoC mínimo utilizável de 20%;
- margem energética de 20%;
- passo de integração de 0,02 s;
- estratégia simples de aceleração/manutenção/frenagem;
- balanço hidráulico dianteiro de 60%.

## Limitações

- Não há telemetria ou geometria de pista real.
- Não há datasheet identificando a célula genérica.
- Tensões mínima/máxima e correntes contínua/de pico permanecem pendentes.
- Não há mapas de eficiência, dinâmica térmica ou degradação do pack.
- O pneu é representado pelo coeficiente de atrito e círculo de atrito, não pela
  Magic Formula completa combinada longitudinal/lateral.
- O motor é quase-estático; não há PI de corrente nem chaveamento do inversor.
- O limite de 80 kW é um parâmetro existente do projeto, não uma afirmação de
  conformidade regulamentar.

## Substituição por pista real

Edite `reference_track_segments()` em `config/parameters.py` ou construa uma
tupla de `TrackSegmentConfig` com comprimentos e raios medidos. Uma evolução
futura pode implementar outro provedor com a mesma interface de `ReferenceTrack`
para ler curvatura em função da distância.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s Endurance_Real\tests -v
```

Os testes verificam unidades e condições iniciais, potência DC, monotonicidade
de SoC e energia, frenagem limitada por aderência, velocidade constante,
aceleração/frenagem, término exato, convergência de passo e geração de gráficos.

## Créditos

Projeto relacionado ao Powertrain da equipe Xangô e-Racing. Os parâmetros e as
equações adaptadas têm como base os modelos existentes no repositório; a autoria
e os créditos desses modelos são preservados.
