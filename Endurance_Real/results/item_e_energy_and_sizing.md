# Item E — validação energética e dimensionamento preliminar

## Auditoria da cadeia de potência

O modelo usa a seguinte sequência sem dupla contagem identificada:

```text
P_roda = F_tração v
F_tração = (T_motor - kf ω) N η_corrente η_diferencial / r
P_motor = T_motor ω
P_DC = P_motor / (η_motor η_inversor)
P_terminal = V_terminal I
V_terminal = OCV_modelada - R_eq I
```

A transmissão e o atrito viscoso estão na conversão torque→força. As
eficiências do motor e inversor são aplicadas uma única vez entre `P_motor` e
`P_DC`. A integração executada resultou em:

- energia DC nos terminais: 2642,361542 Wh;
- energia mecânica no eixo do motor: 2259,219119 Wh;
- trabalho trativo positivo nas rodas: 1990,694581 Wh.

O motor e inversor usam eficiências constantes, e não mapas medidos.

## Bateria e conservação

Foram adicionados históricos de OCV modelada, tensão terminal, queda `I·R`,
perda instantânea, perda acumulada e energia interna estimada acumulada.

```text
E_interna,estimada = E_terminal + ∫I²R_eq dt = ∫OCV_modelada I dt
```

| Parcela | Resultado |
|---|---:|
| Energia terminal | 2642,361542 Wh |
| Perda resistiva interna | 69,937100 Wh |
| Energia interna estimada | 2712,298642 Wh |
| Tensão terminal simulada | 527,959187–547,200000 V |
| OCV mínima modelada | 544,919826 V |
| Queda resistiva máxima | 16,967644 V |
| Corrente média temporal | 12,856011 A |
| Corrente máxima | 29,457715 A |
| SoC final | 66,895067% |

Não há elementos RC no modelo, portanto não existe energia armazenada em uma
rede dinâmica de polarização a contabilizar. A “OCV modelada” contém os termos
de polarização da formulação Modified Shepherd existente; sem curva OCV×SoC e
dados da célula, `∫OCV I dt` é uma **estimativa interna**, não uma medição exata
de energia química. A possível redundância entre carga acumulada e carga usada
nos termos de polarização permanece pendente de fundamentação por datasheet;
a equação não foi alterada arbitrariamente.

## Dimensionamento preliminar

| Grandeza | Valor | Natureza |
|---|---:|---|
| Distância total | 22,000 km | calculada |
| Tempo total | 1390,53 s | calculado |
| Energia nos terminais | 2642,36 Wh | calculada |
| Energia química/interna estimada | 2712,30 Wh | estimada pelo modelo resistivo |
| Perdas internas | 69,94 Wh | calculadas (`I²R`) |
| Consumo específico terminal | 120,11 Wh/km | calculado |
| Potência DC máxima | 15,55 kW | calculada |
| Corrente DC máxima | 29,46 A | calculada |
| SoC final | 66,90% | carga integrada |
| Energia utilizável mínima | 3254,76 Wh | estimada, margem de 20% |
| Energia nominal mínima | 4068,45 Wh | estimada, janela de 80% |
| Capacidade mínima | 7,64 Ah | estimada a 532,8 V nominal |
| C-rate máximo da capacidade mínima | 3,86 C | demanda calculada |

O pack genérico atual é 144s5p, 532,8 V nominais, 15 Ah e 7992 Wh. Ele atende
ao critério energético e a potência simulada permanece abaixo do limite de
projeto de 80 kW. Sua demanda máxima é 1,96 C no pack e 5,89 A por célula.

Pelo critério **somente energético**, `ceil(7,64/3,0) = 3` células em paralelo.
Assim, 144s3p é um candidato matemático energético, não uma configuração
aprovada. Faltam corrente contínua/pico, tensões mínima/máxima, curva OCV,
temperatura, envelhecimento, isolamento, proteções e requisitos regulamentares.
O estado elétrico geral permanece `PENDING`.

## Sensibilidade

Foram executados 15 cenários de 22 km, alterando uma variável por vez. Maiores
impactos sobre a energia interna estimada:

| Variação | Efeito |
|---|---:|
| μ −10% | −7,27% |
| Massa −10% | −6,80% |
| Massa +10% | +6,76% |
| μ +10% | +6,30% |
| Eficiência do motor −5% | +5,42% |
| Eficiência do motor +5% | −4,89% |
| Arrasto −20% | −4,63% |
| Arrasto +20% | +4,34% |
| Rolamento ±20% | −1,83% / +1,68% |
| Resistência interna ±20% | −0,54% / +0,55% |
| Capacidade nominal ±20% | menos de 0,001% |

A capacidade quase não altera a demanda mecânica/terminal deste cenário; ela
altera principalmente SoC e reserva. Os arquivos `energy_sensitivity.csv` e
`energy_sensitivity.md` contêm todos os resultados. Variações são cenários
hipotéticos, não intervalos de incerteza medidos.

## Verificações implementadas

- `V_terminal I = P_DC`;
- `OCV I = P_DC + I²R`;
- energia interna igual a terminal mais perda integrada;
- carga integrada igual à variação de SoC;
- monotonicidade das energias sem regeneração;
- cadeia DC→motor→roda;
- ausência de NaN/infinito;
- limites incompletos permanecem explicitamente pendentes;
- gráfico complementar `09_battery_voltage_diagnostics.png`.
