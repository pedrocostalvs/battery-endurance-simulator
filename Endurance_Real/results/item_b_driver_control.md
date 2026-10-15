# Item B — estabilização do piloto virtual

## Causa do chattering

O controlador anterior alternava diretamente entre acelerador total, freio
total e um ponto de equilíbrio instantâneo. O alvo futuro deixava de ser
considerado assim que a velocidade ficava momentaneamente abaixo do limite da
curva, permitindo reaceleração antes da entrada. Além disso, o feedforward
inicial normalizava a força pelo limite trativo efetivo enquanto o laço
aplicava o acelerador como fração do torque máximo do motor.

## Correção

- Estados persistentes `ACCELERATING`, `CRUISING` e `BRAKING`.
- Segmento-alvo travado desde o início da frenagem até sua saída.
- Alvo de reta igual a 99% do limite cinemático do powertrain.
- Controle `feedforward + Kp`, com `Kp = 2,0` configurável.
- Taxa do acelerador limitada a `3,0 1/s`.
- Distância de liberação do acelerador incluída na antecipação de frenagem.
- Comando do acelerador normalizado pela força trativa máxima efetivamente
  disponível, tornando o feedforward coerente com a força aplicada.
- Depois de uma única frenagem, a velocidade de curva é mantida pelo
  feedforward resistivo; não ocorre novo ciclo aceleração→frenagem no mesmo
  evento.

Os ganhos e bandas são `ASSUMPTIONs`, pois não há calibração do piloto real.

## Históricos adicionados

- velocidade-alvo efetiva;
- acelerador;
- freio;
- estado do controlador;
- distância até a curva-alvo;
- distância estimada de frenagem.

Todos são exportados no NPZ.

## Comparação com o Item A

| Indicador | Antes | Depois | Variação |
|---|---:|---:|---:|
| Tempo total (s) | 1381,86 | 1390,53 | +0,63% |
| Tempo médio por volta (s) | 62,81 | 63,21 | +0,63% |
| Energia terminal (Wh) | 2882,62 | 2642,36 | -8,33% |
| Energia química estimada (Wh) | 2975,89 | 2712,30 | -8,86% |
| Potência DC máxima (kW) | 24,69 | 15,55 | -37,02% |
| Aceleração máxima (m/s²) | 2,22 | 2,22 | aproximadamente 0% |
| Desaceleração máxima (m/s²) | -7,05 | -6,82 | -3,3% em magnitude |
| Inversões médias por volta | 110,91 | 8,00 | -92,79% |

A redução de energia ultrapassa os 3% desejáveis porque o controlador anterior
reaplicava potência repetidamente entre eventos de frenagem. Remover esse
trabalho dissipado desnecessário reduz consumo e potência máxima sem alterar
os parâmetros físicos.

Definição de inversão: após remover amostras neutras, conta-se cada mudança
entre comando de tração (`throttle > 1e-6`) e comando de freio
(`brake_command > 1e-9`). O resultado é oito inversões por volta, coerente com
quatro eventos de curva.

## Verificação

- Excesso máximo sobre limites locais: -0,0179 m/s (nenhum excesso).
- 18/18 testes específicos aprovados.
- Distância final exata de 22 km preservada.
- Convergência entre passos de 0,02 s e 0,01 s preservada.
