# Battery Endurance Simulator

Simulador computacional desenvolvido em Python para análise do consumo energético de um veículo Formula SAE Electric, com foco no dimensionamento e na avaliação do sistema de baterias.

## Objetivo

Estimar a energia elétrica consumida ao longo de uma prova de Endurance de 22 km, considerando os modelos de aceleração, frenagem e os parâmetros do conjunto motopropulsor.

## Funcionalidades

- Simulação de aceleração em um percurso de 75 metros.
- Modelagem da frenagem do veículo.
- Estimativa do consumo de energia elétrica.
- Acompanhamento do estado de carga (SoC) da bateria.
- Estimativa de desempenho energético para 22 km.

## Estrutura do projeto

- `src/BatteryCapacity.py`: rotina principal de análise energética.
- `src/Brake.py`: modelo de frenagem.
- `src/Models/`: modelos dos componentes do veículo.
- `src/Simulation/`: rotinas de simulação.
- `src/Constants/`: constantes utilizadas pelos modelos.
- `requirements.txt`: dependências externas do projeto.

## Como executar

Requisitos: Python e dependências listadas em `requirements.txt`.

No terminal PowerShell, a partir da pasta principal do repositório:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/BatteryCapacity.py
```

## Resultados preliminares

Para a configuração atual, o simulador apresentou:

| Parâmetro | Resultado |
|---|---|
| Distância simulada | 22 km |
| Energia consumida | 6.970,29 Wh |
| Tempo estimado | 1.508,87 s |
| Ciclos executados | 153 |

Os resultados são preliminares e dependem das hipóteses e parâmetros dos modelos computacionais. Não constituem validação experimental.

## Créditos

Projeto relacionado às atividades de desenvolvimento do sistema Powertrain da equipe Xangô e-Racing.

Os modelos e módulos utilizados devem manter o reconhecimento de seus respectivos autores e as condições de utilização autorizadas pela equipe.