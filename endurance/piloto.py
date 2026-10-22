"""Fase 4: piloto do Endurance.

A cada passo o piloto escolhe um de quatro modos:

    FREAR     a velocidade passou do envelope de frenagem de alguma curva à frente
    ROLAR     faltam menos de ``tempo_rolagem`` segundos para o ponto de frenagem:
              tira o pé e deixa o carro desacelerar sozinho (arrasto, rolamento e
              perdas em vazio do motor), sem gastar bateria
    ACELERAR  está abaixo da velocidade alvo do trecho
    MANTER    está na velocidade alvo: torque só para vencer as resistências

Envelope de frenagem de uma curva a distância d, com velocidade alvo v_c:

    v_permitida = sqrt(v_c² + 2 · a_plan · (d - folga))

com a_plan = ``fator_seguranca_freio`` × desaceleração máxima (Fase 1) na
velocidade v_c. A desaceleração disponível cai junto com a velocidade (menos
downforce e arrasto), então a da entrada da curva é a menor do trecho.

Parâmetros de ritmo (calibrados na Fase 5):
    fator_curva            fração da velocidade limite das curvas (1 = no limite)
    torque_maximo          teto de torque do motor [N·m] (None = sem teto)
    velocidade_maxima      teto de velocidade nas retas [m/s] (None = sem teto)
    tempo_rolagem          antecedência da tirada de pé [s] (0 = sem rolagem)
"""
from dataclasses import dataclass

ACELERAR, MANTER, ROLAR, FREAR = "acelerar", "manter", "rolar", "frear"


@dataclass
class RitmoPiloto:
    fator_curva: float = 1.0
    torque_maximo: float | None = None
    velocidade_maxima: float | None = None
    tempo_rolagem: float = 0.0
    fator_seguranca_freio: float = 0.95
    folga_frenagem: float = 1.0          # [m]
    faixa_velocidade: float = 0.3        # [m/s] histerese entre ACELERAR e MANTER
    horizonte: float = 150.0             # [m] quanto o piloto olha à frente


@dataclass
class Decisao:
    modo: str
    velocidade_alvo: float
    desaceleracao_pedida: float = 0.0    # [m/s²] no modo FREAR


class Piloto:
    def __init__(self, pista, dinamica, ritmo=None, v_max_trem=None):
        self.pista = pista
        self.din = dinamica
        self.ritmo = ritmo or RitmoPiloto()
        self.v_max_trem = v_max_trem
        self.modo_anterior = ACELERAR

    def alvo_local(self, distancia):
        r = self.ritmo
        lim = self.pista.limite(distancia)
        alvo = lim * r.fator_curva if self.pista.segmento(distancia).raio is not None else lim
        tetos = [x for x in (r.velocidade_maxima, self.v_max_trem) if x is not None]
        return min([alvo] + tetos)

    def decidir(self, distancia, velocidade):
        r = self.ritmo
        alvo = self.alvo_local(distancia)
        raio = self.pista.segmento(distancia).raio
        a_plan = r.fator_seguranca_freio * self.din.desaceleracao_maxima(velocidade, raio)

        frear, distancia_ponto_frenagem, decel_pedida, alvo_frente = False, float("inf"), 0.0, alvo
        for d, lim, _nome in self.pista.restricoes_a_frente(distancia, r.horizonte):
            v_c = lim * r.fator_curva
            if velocidade <= v_c:
                continue
            # a desaceleração disponível cai junto com a velocidade (menos downforce e
            # arrasto); planeja com a da velocidade de entrada, a menor do trecho
            a_plan = r.fator_seguranca_freio * self.din.desaceleracao_maxima(v_c)
            util = max(d - r.folga_frenagem, 1e-3)
            precisa = (velocidade ** 2 - v_c ** 2) / (2.0 * util)       # desaceleração para chegar em v_c
            ponto = d - r.folga_frenagem - (velocidade ** 2 - v_c ** 2) / (2.0 * a_plan)
            if precisa >= a_plan:
                frear = True
                if precisa > decel_pedida:
                    decel_pedida, alvo_frente = precisa, v_c
            distancia_ponto_frenagem = min(distancia_ponto_frenagem, ponto)

        if velocidade > alvo + r.faixa_velocidade:                  # entrou rápido demais num trecho
            frear = True
            decel_pedida = max(decel_pedida, a_plan)
        if frear:
            modo = FREAR
            return self._fim(Decisao(modo, min(alvo, alvo_frente), decel_pedida))

        if r.tempo_rolagem > 0.0 and distancia_ponto_frenagem <= velocidade * r.tempo_rolagem:
            return self._fim(Decisao(ROLAR, alvo))

        if velocidade < alvo - r.faixa_velocidade or (self.modo_anterior == ACELERAR and velocidade < alvo):
            return self._fim(Decisao(ACELERAR, alvo))
        return self._fim(Decisao(MANTER, alvo))

    def _fim(self, decisao):
        self.modo_anterior = decisao.modo
        return decisao
