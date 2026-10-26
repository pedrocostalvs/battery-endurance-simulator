# Simulador de Endurance (22 km): Xangô e-Racing

Simula a prova de Endurance de 22 km da Formula SAE Electric para avaliar se a
bateria aguenta a prova, e com que folga. A cada instante calcula velocidade,
energia gasta, SoC, tensão, corrente e temperatura das células.

> Modelo preliminar, pois o carro ainda não existe.
> Os resultados devem ser lidos como faixas e comparações entre opções de projeto.

## Como rodar

1. Instale as dependências no ambiente virtual: `numpy`, `scipy` e `matplotlib`.
2. Abra `endurance/rodar_endurance.py` no VS Code e clique em **Run Python File (▶)**.

O resumo e os gráficos ficam em `endurance/resultados/`.

## De onde vem cada parte

O simulador reaproveita o código que a equipe já tinha, por import, sem alterar
os arquivos originais:

| Código original | O que fornece |
|---|---|
| `src/Brake.py` (`BrakeSystem`) | Dados do sistema de freio |
| `src/Simulation/Simulation.py` | Aceleração do carro (motor, pneu, transmissão) |
| `src/Models` | Classes do veículo, motor, pneu e transmissão |
| `endurance/modelo_tensao.py` | Curva de tensão da bateria (Shepherd/Tremblay) |

Quando um original precisava de ajuste, foi criado um arquivo que o "embrulha"
e corrige por fora. As correções sugeridas para os originais estão registradas
à parte.

## Arquivos

**Parâmetros**
- `parametros.py`: todos os números do carro num lugar só. Cada valor é marcado
  como CONHECIDO (equipe ou datasheet) ou HIPÓTESE (provisório).

**Embrulhos dos códigos originais**
- `frenagem.py`: força de frenagem a partir da força no pedal, limitada pela
  aderência de cada eixo.
- `tracao.py`: roda a `Simulation` uma vez e gera um mapa de tração
  (aceleração máxima em cada velocidade), com controle de tração.
- `motor.py`: monta as classes do carro com os parâmetros novos e calcula a
  potência pedida à bateria pelo mapa de eficiência do Emrax 228.
- `bateria.py`: aplica os dados da célula Murata VTC6 e do pack 142s5p ao
  modelo de tensão.

**Partes novas**
- `pista.py`: pista montada a partir da telemetria de uma volta real de
  Autocross (674 m, 14 curvas).
- `dinamica.py`: forças no carro (arrasto, rolamento, downforce), limite de
  velocidade nas curvas e frenagem máxima.
- `piloto.py`: decide a cada instante se acelera, mantém, rola ou freia.
- `simulador.py`: o loop dos 22 km, que junta tudo.
- `calibracao.py`: validação contra o vídeo e escolha do ritmo de prova.
- `resultados.py`: gráficos e resumo.
- `rodar_endurance.py`: ponto de entrada.

## Como funciona

A simulação avança em passos de 0,01 s até completar os 22 km. Em cada passo:

1. **O piloto decide** o que fazer, olhando as curvas nos próximos 150 m.
2. **Calcula a força** que empurra ou segura o carro.
3. **Calcula a aceleração** (a = F/m).
4. **A bateria entrega a potência** pedida pelo motor e desconta a energia.
5. **Atualiza velocidade e posição** para o próximo passo.

### Decisão do piloto

Nesta ordem:

1. **Frear:** se a distância até a próxima curva ficou no limite do que dá para frear.
2. **Rolar:** se falta menos de 0,5 s para o ponto de frenagem. Tira o pé e
   deixa o carro perder velocidade sozinho, sem gastar bateria.
3. **Acelerar:** se está abaixo da velocidade desejada.
4. **Manter:** se já está na velocidade certa; o motor só vence o arrasto.

### Forças em cada modo

- **Sempre:** arrasto do ar e resistência ao rolamento seguram o carro.
- **Acelerar:** o empurrão vem do mapa de tração, limitado a 120 N·m.
- **Manter:** o motor iguala o arrasto; aceleração zero.
- **Rolar:** sem motor; também atuam as perdas do motor, que continua girando.
- **Frear:** soma-se a força do freio, limitada pela aderência do pneu.

A massa usada inclui as peças que giram (rotor, rodas, eixos): cerca de 272 kg
equivalentes para um carro de 240 kg.

## Resultado com o ritmo recomendado

Ritmo: teto de 120 N·m no motor e rolagem de 0,5 s antes de cada frenagem.

| Grandeza | Valor |
|---|---|
| Tempo total | 25,4 min (32 voltas) |
| Energia | 4,97 kWh (226 Wh/km) |
| SoC final | 36% |
| Corrente por célula (pico) | 28 A |
| Temperatura da célula (máx.) | 49 °C |

Pilotando no limite o tempo todo, a bateria chega ao SoC mínimo em 18,8 km.
Cerca de 60% da energia é dissipada no freio, porque o carro não tem
regeneração. Por isso rolar antes de frear é o ajuste que mais economiza.

## Principais hipóteses

- Massa de 240 kg (sem confirmação se inclui o piloto).
- Distribuição de peso 45/55 (dianteira/traseira).
- Balanço de freio de 60% na dianteira.
- Coeficiente de atrito do pneu de 1,3.
- Eficiência do inversor de 95%.
- Resistência térmica da célula de 50 K/W.
- SoC mínimo de 20%.

Todas ficam em `parametros.py` e podem ser trocadas quando houver o dado real.