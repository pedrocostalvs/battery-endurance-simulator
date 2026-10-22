"""Dinâmica longitudinal comum às fases 3 e 4.

Reaproveita o ``Vehicle`` do Marco (resistências, downforce, transferência de
carga) e o freio da Fase 1.

Massa equivalente
-----------------
Na Simulation do Marco o carro e o motor são dois corpos: a equação do carro
usa só a massa m, e as partes girantes (rotor, rodas, eixos) ficam na equação
do motor, com J_eff. Por isso o mapa de tração da Fase 2 já desconta o torque
gasto para girar essas peças.

Nas fases sem tração (frenagem e rolagem) quem desacelera as partes girantes
são o freio e as resistências, então a massa vista pelo carro é

    m_eq = m + J_eff · (N / r)²

com o mesmo J_eff da Simulation. Acelerando com torque abaixo do limite do
pneu, a massa vista é m + J_eff·(N/r)²·η (o torque das partes girantes passa
pela transmissão).
"""
import math

import caminhos  # noqa: F401
import parametros as config
from frenagem import Freio
from motor import criar_componentes, torque_arrasto_vazio

G = config.G


class Dinamica:
    def __init__(self, componentes=None, freio=None):
        c = componentes or criar_componentes()
        self.veiculo = c["veiculo"]
        self.transmissao = c["transmissao"]
        self.motor = c["motor"]
        self.freio = freio or Freio()
        v, t = self.veiculo, self.transmissao
        self.m = v.mass
        self.r = v.wheel_radius
        self.N = t.final_drive_ratio
        self.eta_trans = t.efficiency
        # mesmo cálculo de J_eff da Simulation (src/Simulation/Simulation.py)
        j_all = v.calculate_reflected_inertia(t)
        j_translacao = v.mass * (self.r / self.N) ** 2
        self.j_eff = max(self.motor.jm + j_all - j_translacao, self.motor.jm)
        self.m_eq = self.m + self.j_eff * (self.N / self.r) ** 2
        # acelerando, o torque para girar J_eff passa pela transmissão (η):
        # Ft = (T - J_eff·a·N/r)·N·η/r  ->  a·(m + J_eff·(N/r)²·η) = T·N·η/r - F_res
        self.m_eq_tracao = self.m + self.j_eff * (self.N / self.r) ** 2 * self.eta_trans

    # --- cinemática do trem de força -------------------------------------
    def rpm_motor(self, velocidade):
        return velocidade / self.r * self.N * 60.0 / (2 * math.pi)

    def forca_roda_de_torque_motor(self, torque_motor):
        return torque_motor * self.N * self.eta_trans / self.r

    def torque_motor_de_forca_roda(self, forca_roda):
        return forca_roda * self.r / (self.N * self.eta_trans)

    # --- forças -------------------------------------------------------------
    def resistencia(self, velocidade):
        """Arrasto + rolamento [N] (Vehicle.calculate_resistance_forces)."""
        return self.veiculo.calculate_resistance_forces(velocidade)

    def arrasto_motor_em_vazio(self, velocidade):
        """Força na roda [N] das perdas em vazio do motor (mapa Emrax)."""
        return self.forca_roda_de_torque_motor(torque_arrasto_vazio(self.rpm_motor(velocidade)))

    def downforce(self, velocidade):
        v = self.veiculo
        if not v.has_wing:
            return 0.0, 0.0
        q = v.half_rho * velocidade ** 2
        return q * v.lift_coeff_front * v.area_front, q * v.lift_coeff_rear * v.area_rear

    def forca_lateral(self, velocidade, raio):
        return 0.0 if raio is None else self.m * velocidade ** 2 / raio

    def velocidade_limite_curva(self, raio):
        """Maior velocidade em curva de raio R: m v²/R <= μ (m g + DF(v)) [m/s]."""
        if raio is None:
            return math.inf
        v = self.veiculo
        k_df = v.half_rho * (v.lift_coeff_front * v.area_front + v.lift_coeff_rear * v.area_rear) \
            if v.has_wing else 0.0
        den = self.m / raio - config.MU_PNEU * k_df
        if den <= 0.0:
            return math.inf
        return math.sqrt(config.MU_PNEU * self.m * G / den)

    def forca_freio_maxima(self, velocidade, raio=None):
        df_d, df_t = self.downforce(velocidade)
        limite, _ = self.freio.limite_aderencia(df_d, df_t, self.forca_lateral(velocidade, raio))
        return min(limite, self.freio.forca_comandada(1.0)[1])

    def desaceleracao_maxima(self, velocidade, raio=None):
        """Desaceleração com freio no limite + resistências [m/s², positiva]."""
        f = self.forca_freio_maxima(velocidade, raio) + self.resistencia(velocidade) \
            + self.arrasto_motor_em_vazio(velocidade)
        return f / self.m_eq
