"""Freio do simulador, usando os dados do ``BrakeSystem`` (src/Brake.py).

O ``apply_brake`` original ainda não responde à força no pedal (proposta 2.1),
então este módulo pega do ``BrakeSystem`` apenas os dados físicos do sistema
(redução do pedal, cilindros, pastilhas, disco, raio do pneu) e faz a conta:

    pressão      p      = F_pedal · RedP / A_mestre
    aperto       F_ap   = p · A_roda                     (por disco)
    torque       T_disco = 2 · μ_pastilha · F_ap · r_disco   (duas faces)
    força roda   F_cmd  = n_discos · T_disco / r_pneu

Limite por aderência, eixo a eixo, com balanço b (fração na dianteira):

    dianteira: b·F     <= μ (Fz_d + F·h/L + DF_d)  ->  F <= μ(Fz_d + DF_d) / (b - μh/L)
    traseira:  (1-b)·F <= μ (Fz_t - F·h/L + DF_t)  ->  F <= μ(Fz_t + DF_t) / (1 - b + μh/L)

A transferência de carga usa a própria força de frenagem (F·h/L), então o
limite sai direto, sem iterar. O eixo que trava primeiro define o máximo.
Em curva, o μ disponível para frear cai pelo círculo de atrito.

Quando o ``apply_brake`` for corrigido, ``forca_comandada`` pode chamar ele.
"""
import math
from dataclasses import dataclass

import caminhos  # noqa: F401
import parametros as config
from Brake import BrakeSystem


@dataclass(frozen=True)
class SaidaFreio:
    pressao_pa: float
    forca_comandada_n: float
    limite_aderencia_n: float
    forca_n: float
    eixo_limitante: str


class Freio:
    def __init__(self, parametros=None, mu_pneu=config.MU_PNEU,
                 balanco_dianteiro=config.BALANCO_FREIO_DIANTEIRO,
                 numero_discos=config.NUMERO_DISCOS,
                 forca_pedal_max=config.FORCA_PEDAL_MAX):
        self.sistema = BrakeSystem(dict(config.FREIO if parametros is None else parametros))
        self.mu = mu_pneu
        self.balanco = balanco_dianteiro
        self.discos = numero_discos
        self.forca_pedal_max = forca_pedal_max
        s = self.sistema
        self.area_mestre = s.pi * s.Dcm ** 2 / 4.0
        self.area_roda = s.pi * s.Dwc ** 2 / 4.0

    def forca_comandada(self, fracao_pedal):
        """Força total nas rodas pedida pelo pedal [N], sem limite de aderência."""
        s = self.sistema
        fracao = min(max(float(fracao_pedal), 0.0), 1.0)
        pressao = fracao * self.forca_pedal_max * s.RedP / self.area_mestre
        aperto = pressao * self.area_roda
        torque_disco = 2.0 * s.atrito_coeficiente * aperto * s.red
        return pressao, self.discos * torque_disco / s.Rdp

    def limite_aderencia(self, downforce_dianteira=0.0, downforce_traseira=0.0,
                         forca_lateral=0.0):
        """Maior força de frenagem sem travar nenhum eixo [N] e o eixo limitante."""
        s = self.sistema
        peso = s.Mt * 9.81
        fz_d = s.FzF + downforce_dianteira
        fz_t = s.FzR + downforce_traseira
        mu = self.mu
        if forca_lateral > 0.0:
            fracao_lateral = forca_lateral / (mu * (peso + downforce_dianteira + downforce_traseira))
            mu = mu * math.sqrt(max(1.0 - fracao_lateral ** 2, 0.0))
        chi = mu * s.HCG / s.L
        b = self.balanco
        lim_d = mu * fz_d / (b - chi) if b > chi else math.inf
        lim_t = mu * fz_t / (1.0 - b + chi)
        return (lim_d, "dianteira") if lim_d <= lim_t else (lim_t, "traseira")

    def aplicar(self, fracao_pedal, downforce_dianteira=0.0, downforce_traseira=0.0,
                forca_lateral=0.0):
        pressao, comandada = self.forca_comandada(fracao_pedal)
        limite, eixo = self.limite_aderencia(downforce_dianteira, downforce_traseira, forca_lateral)
        return SaidaFreio(pressao, comandada, limite, min(comandada, limite), eixo)
