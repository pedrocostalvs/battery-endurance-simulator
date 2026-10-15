# Baseline antes das correções físicas

Registro criado em 2026-10-15 antes das fases de revisão física do
`Endurance_Real`. Este arquivo não deve ser substituído pelas execuções
posteriores.

## Estado do repositório

- Branch: `main`.
- Commit de partida: `716fe96` (`endurance com graficos`).
- Árvore de trabalho antes do registro: limpa.
- O diretório `src/` foi consultado apenas para comparação.

## Execução de referência

- Interpretador: `.venv/Scripts/python.exe`.
- Cenário: configuração padrão, percurso hipotético repetido até 22 km.
- Passo de tempo: 0,02 s.
- Status: `completed`.
- Motivo: `target_distance_reached`.

| Grandeza | Valor em precisão completa |
|---|---:|
| Distância final | 22000,000000000000 m |
| Tempo total | 1380,7676252109238 s |
| Energia nos terminais | 2961,885849564084 Wh |
| Perda resistiva interna | 95,87458504136438 Wh |
| Estimativa de energia interna | 3057,7604346054484 Wh |
| Consumo específico terminal | 134,63117498018562 Wh/km |
| Potência DC máxima | 24730,747729251692 W |
| Corrente máxima | 47,838738514920195 A |
| Tensão mínima | 516,9567987692831 V |
| SoC final | 0,6266688980161529 |
| Velocidade média | 15,933166159395803 m/s |
| Velocidade máxima | 26,897633735241037 m/s |
| Aceleração máxima | 2,218489610662723 m/s² |
| Desaceleração máxima | -7,0588092335213855 m/s² |

A estimativa interna acima é somente a soma
`energia_terminal + perda_resistiva` do modelo elétrico existente. Ela não
é uma medição da energia química da célula.

## Testes antes das correções

Comando:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s .\Endurance_Real\tests -v
```

Resultado: 13 testes executados e 13 aprovados.

## Limitações deste baseline

- O percurso é hipotético e não representa uma pista real validada.
- O valor `0,6` ainda é interpretado como coeficiente de aderência absoluto,
  embora seja `lambda_mu` no modelo Pacejka longitudinal de origem.
- A perda resistiva é acumulada pelo objeto da bateria, mas não faz parte do
  NPZ nem do resumo terminal deste baseline.
- A frenagem usa um limite agregado de aderência, sem limitar os eixos
  dianteiro e traseiro separadamente.
