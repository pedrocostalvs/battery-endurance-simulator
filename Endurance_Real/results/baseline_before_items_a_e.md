# Baseline antes dos itens A–E

Estado medido em 2026-10-15 antes do Item A da revisão de consistência,
controle, dashboard e dimensionamento. A árvore continha a revisão longitudinal
de pneus ainda sem commit; por isso este baseline corresponde ao comportamento
de aproximadamente +11/−17 m/s² citado na especificação.

| Indicador | Baseline |
|---|---:|
| Distância | 22000,000000 m |
| Tempo total | 1170,172584 s |
| Tempo médio por volta | 53,189663 s |
| Energia nos terminais | 4649,017828 Wh |
| Perdas internas | 755,527154 Wh |
| Energia química estimada | 5404,544982 Wh |
| Potência DC máxima | 80,000000 kW |
| Corrente DC média | 30,547153 A |
| Corrente DC máxima | 185,293262 A |
| SoC final | 33,804360 % |
| Aceleração máxima | 11,104104 m/s² |
| Desaceleração máxima | -16,813771 m/s² |
| Velocidade média | 18,800646 m/s |
| Velocidade máxima | 29,836058 m/s |
| Inversões tração↔freio médias por volta | 87,090909 |

Definição de inversão neste baseline: mudança direta entre amostras com força
de tração maior que `1e-6 N` e força de frenagem maior que `1e-6 N`, ou vice-
versa. Amostras neutras não contam como inversão.

## Limites de velocidade dos segmentos de curva

| Segmento | Raio (m) | Limite (m/s) |
|---|---:|---:|
| Curva A | 25 | 12,296411 |
| Curva B | 35 | 14,630100 |
| Curva lenta | 18 | 10,393861 |
| Curva de retorno | 30 | 13,507287 |

## Verificação inicial

- Testes específicos: 16 executados, 16 aprovados.
- Branch: `main`.
- Nenhum arquivo de `src/` foi alterado pela revisão.
- Os resultados são de percurso hipotético e não têm validação experimental.
