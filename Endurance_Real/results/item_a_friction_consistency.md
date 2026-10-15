# Item A — consistência do coeficiente de atrito

## Causa

O baseline usava `TireConfig.peak_longitudinal_mu()` na tração e frenagem,
produzindo coeficientes longitudinais próximos de 2, enquanto o limite de curva
usava `mu_lateral = 0,60`. Isso explica a combinação incoerente de velocidades
laterais moderadas com acelerações longitudinais de +11/−17 m/s².

## Correção

`TireConfig.friction_coefficient` é agora a fonte única do coeficiente
simplificado usado por:

- limite de tração do eixo motriz;
- limite agregado de frenagem;
- velocidade limite em curvas.

O valor 0,60 foi preservado e identificado como `ASSUMPTION`. Ele não é
confundido com o `lambda_mu` do modelo Pacejka original. A combinação de forças
usa um círculo de atrito simplificado:

```text
Fx,max = sqrt((mu Fz)² - Fy²)
```

As cargas normais incluem downforce. Na tração é usada a carga traseira com
transferência longitudinal; na frenagem ainda se usa o limite agregado do
veículo, uma limitação documentada do modelo.

## Resultados

| Indicador | Antes | Depois | Variação |
|---|---:|---:|---:|
| Tempo total (s) | 1170,17 | 1381,86 | +18,09% |
| Tempo médio por volta (s) | 53,19 | 62,81 | +18,09% |
| Energia terminal (Wh) | 4649,02 | 2882,62 | -37,99% |
| Energia química estimada (Wh) | 5404,54 | 2975,89 | -44,94% |
| Potência DC máxima (kW) | 80,00 | 24,69 | -69,14% |
| SoC final (%) | 33,80 | 63,67 | +29,86 p.p. |
| Aceleração máxima (m/s²) | 11,10 | 2,22 | -80,02% |
| Desaceleração máxima (m/s²) | -16,81 | -7,05 | -58,06% em magnitude |
| Inversões médias por volta | 87,09 | 110,91 | +27,35% |

Os limites das quatro curvas permaneceram em 12,2964; 14,6301; 10,3939 e
13,5073 m/s, pois já usavam 0,60. As grandes mudanças longitudinais decorrem
da remoção do coeficiente efetivo próximo de 2, não de calibração para um
resultado-alvo. O aumento de chattering é tratado no Item B.

## Verificação

- 16/16 testes de `Endurance_Real` aprovados.
- 26/26 testes gerais aprovados.
- Distância final: exatamente 22.000 m.
- A equação analítica da Curva lenta coincide com o código a `1e-6`.
- Um teste altera o μ do config e confirma efeito em tração, frenagem e curva.
