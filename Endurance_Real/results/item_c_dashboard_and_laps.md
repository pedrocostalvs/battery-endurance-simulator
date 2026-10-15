# Item C — dashboard e resultados por volta

## Resultados estruturados

`EnduranceResults` passou a registrar índice e posição da volta, metadados dos
segmentos, limite DC configurado, SoC mínimo utilizável e todos os históricos
do piloto. A distância final de 22.000 m pertence à volta 22 com posição local
de 1.000 m, evitando a criação espúria de uma volta 23.

`lap_summary()` divide a prova nas fronteiras de distância e interpola tempo e
energia acumulada nessas fronteiras. Assim, intervalos que atravessam uma linha
de volta são repartidos sem omissão ou dupla contagem. Uma simulação de 2,5 km
foi usada para validar a última volta parcial de 500 m.

## Dashboard

O dashboard 15×11 usa uma grade 4×2 e a volta 2 como referência:

1. velocidade e limite local por posição;
2. potência DC por posição;
3. forças de tração e frenagem;
4. tensão e corrente;
5. energia e tempo por volta;
6. SoC final por volta;
7. diagrama g-g simplificado;
8. potência DC por velocidade.

As regiões de curva aparecem em laranja nos gráficos posicionais. O diagrama
g-g usa a aceleração centrípeta implícita `Fy/m`, mas não é validação de uma
dinâmica lateral completa: a pista é uma sequência longitudinal de segmentos e
o pneu combinado é apenas um círculo de atrito simplificado.

## Exportações

- `00_endurance_dashboard.png`;
- oito painéis individuais numerados de `01` a `08`;
- cópia real do dashboard em `docs/img/endurance_dashboard.png`;
- `endurance_results.npz` com os metadados e históricos novos.

Os sete PNGs antigos foram substituídos pelas novas exportações. Nenhuma janela
individual é aberta; somente o dashboard interativo permanece visível na
execução normal.

## Resultados físicos

O Item C não altera equações, parâmetros ou controle. Os resultados permanecem
iguais aos do Item B: 1.390,53 s, 2.642,36 Wh nos terminais, potência máxima de
15,55 kW e SoC final de 66,90%.

## Verificação

- 21/21 testes específicos aprovados antes da documentação final do item.
- Soma da energia por volta igual à energia total dentro de `1e-6` relativo.
- 22 resumos para 22 km e três resumos para o caso parcial de 2,5 km.
- Nove PNGs gerados e não vazios.
- O dashboard contém oito eixos principais titulados; eixos secundários e barra
  de cores são adicionais.
