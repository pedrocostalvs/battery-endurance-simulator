"""Bateria do simulador: usa o modelo de tensão do Pedro (modelo_tensao.py).

O arquivo ``modelo_tensao.py`` está sem alterações. Este módulo:

1. aplica os parâmetros da VTC6 e do pack 142s5p (``config.BATERIA``) por
   cima das constantes do modelo;
2. reaproveita as funções ``R_T`` e ``Q_T`` do modelo;
3. enquanto as propostas 1.3, 1.5 e 1.6 não forem aplicadas no original,
   faz o passo com três diferenças, todas marcadas abaixo:
     - polarização sobre a corrente com constante própria (KR);
     - SoC pela capacidade útil (3,0 Ah);
     - corte de tensão pela tensão da célula, sem a queda nos busbars.

Com KR = K_POL, sem busbars e com capacidade útil = Q_REF, o resultado é
idêntico ao ``modelo_tensao.passo`` (há um teste para isso).
"""
import math

import caminhos  # noqa: F401
import parametros as config
import modelo_tensao as mt


def aplicar_parametros(parametros=None):
    """Grava os parâmetros nas constantes do modelo_tensao."""
    parametros = dict(config.BATERIA if parametros is None else parametros)
    kr = parametros.pop("KR")
    for nome, valor in parametros.items():
        if not hasattr(mt, nome):
            raise AttributeError(f"modelo_tensao não tem a constante {nome}")
        setattr(mt, nome, valor)
    return kr


class Bateria:
    def __init__(self, soc_inicial=1.0, temperatura=config.TEMPERATURA_AMBIENTE,
                 capacidade_util=config.CAPACIDADE_UTIL_CEL, parametros=None):
        self.kr = aplicar_parametros(parametros)
        self.capacidade_util = capacidade_util
        self.it = (1.0 - soc_inicial) * capacidade_util   # Ah extraídos por célula
        self.T = temperatura
        self.energia_wh = 0.0
        self.perdas_wh = 0.0
        self.ultimo = None

    @property
    def soc(self):
        return 1.0 - self.it / self.capacidade_util

    def passo(self, potencia_pack, dt, temperatura_ambiente=config.TEMPERATURA_AMBIENTE):
        """Avança um passo pedindo ``potencia_pack`` [W] (positiva na descarga)."""
        Q = mt.Q_T(self.T)
        R = mt.R_T(self.T)
        it_c = min(self.it, 0.999 * Q)
        f = Q / (Q - it_c)

        V0 = mt.E0 - mt.K_POL * f * it_c + mt.A_EXP * math.exp(-mt.B_EXP * it_c)
        R_cel = R + self.kr * f                           # diferença 1: KR próprio
        R_eff = R_cel + mt.R_EXTRA_PACK * mt.NP / mt.NS

        P_cel = potencia_pack / (mt.NS * mt.NP)
        disc = V0 * V0 - 4.0 * R_eff * P_cel
        limitado = disc < 0.0
        if limitado:
            i = V0 / (2.0 * R_eff)
        else:
            i = (V0 - math.sqrt(disc)) / (2.0 * R_eff)
        V_terminal = V0 - R_eff * i                       # tensão vista pelo inversor
        V_celula = V0 - R_cel * i                         # diferença 3: sem busbars

        q_gerado = i * i * R_cel
        self.T += dt * (q_gerado - (self.T - temperatura_ambiente) / mt.R_TH) / (mt.M_CEL * mt.CP)
        self.it += i * dt / 3600.0

        potencia_entregue = mt.NS * V_terminal * mt.NP * i
        self.energia_wh += potencia_entregue * dt / 3600.0
        self.perdas_wh += mt.NS * mt.NP * q_gerado * dt / 3600.0

        self.ultimo = {
            "V_pack": mt.NS * V_terminal,
            "V_cel": V_celula,
            "I_pack": i * mt.NP,
            "I_cel": i,
            "C_rate": i / self.capacidade_util,
            "P_entregue": potencia_entregue,
            "SoC": self.soc,                              # diferença 2: capacidade útil
            "T": self.T,
            "limitado": limitado,
            "fim": V_celula <= mt.V_MIN_CEL or self.it >= self.capacidade_util,
        }
        return self.ultimo


def tensao_celula(it_ah, corrente, temperatura=None, kr=None):
    """Tensão da célula para uma carga extraída e corrente fixas (sem dinâmica)."""
    if kr is None:
        kr = config.BATERIA["KR"]
    T = mt.T_REF if temperatura is None else temperatura
    Q = mt.Q_T(T)
    it_c = min(it_ah, 0.999 * Q)
    f = Q / (Q - it_c)
    V0 = mt.E0 - mt.K_POL * f * it_c + mt.A_EXP * math.exp(-mt.B_EXP * it_c)
    return V0 - (mt.R_T(T) + kr * f) * corrente


aplicar_parametros()
