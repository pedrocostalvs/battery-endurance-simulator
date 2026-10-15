# Item D — documentação técnica

O README foi reestruturado para distinguir dados do projeto, hipóteses e
limitações; documentar dinâmica, pneus, piloto, bateria, pista, dashboard e
execução multiplataforma; e delimitar o uso para dimensionamento preliminar.

Também foi movido o fator empírico de inércia das rodas `0,80` para
`DrivetrainConfig.wheel_inertia_shape_factor`, mantendo exatamente o valor e o
resultado numérico anterior.

Pontos explicitamente registrados:

- o piloto freia antes da curva e não faz *trail braking*;
- o diagrama g-g não valida uma dinâmica lateral completa;
- a sequência de pista não fecha geometricamente;
- a primeira volta contém o transiente de largada;
- as demais voltas são quase periódicas, com evolução elétrica pelo SoC;
- potência, energia terminal e estimativa interna são grandezas distintas;
- parâmetros sem medição são `ASSUMPTIONs` configuráveis;
- o resultado serve para estudos preliminares, não para aprovação do pack;
- créditos foram preservados e nenhuma licença foi criada.

O Item D não altera física nem resultados da simulação.
