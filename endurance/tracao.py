"""Fase 2: mapa de tração gerado pela Simulation do Marco.

A ``Simulation`` (src/Simulation/Simulation.py) é rodada uma vez, com
acelerador cheio, do carro parado até a velocidade máxima. Do resultado sai,
para cada velocidade:

    - força de tração no chão [N]
    - aceleração [m/s²]
    - torque e rotação do motor
    - potência DC pedida (com a eficiência fixa de 0,90 da Simulation)

O loop do Endurance consulta esse mapa em vez de rodar a Simulation a cada
aceleração (que levaria horas com passo de 0,1 ms).

``SimulacaoEndurance`` é uma subclasse que não altera o arquivo original e faz
só duas coisas (propostas 3.4, 3.5 e 3.7):
  1. a barreira de 80 kW registra o excesso em vez de encerrar a simulação;
  2. aceita velocidade inicial, com o filtro de rotação começando nela.

``PedalControleTracao`` faz o papel de controle de tração pela entrada de
pedal da Simulation (proposta 3.8), para a roda não patinar.
"""
import time
from pathlib import Path

import numpy as np

import caminhos  # noqa: F401
import parametros as config
from motor import criar_componentes
from Models.BatteryPack import BatteryPack
from Models.Pedal import Pedal
from Simulation.Simulation import Simulation

PASTA_RESULTADOS = Path(__file__).resolve().parent / "resultados"
ARQUIVO_MAPA = PASTA_RESULTADOS / "mapa_tracao.npz"


class SimulacaoEndurance(Simulation):
    def __init__(self, *args, velocidade_inicial=0.0, **kwargs):
        self.velocidade_inicial = float(velocidade_inicial)
        self.excesso_potencia_max = 0.0
        super().__init__(*args, **kwargs)

    def _dc_power_limit_exceeded(self, requested_power):
        if self.p_max_dc is not None:
            self.excesso_potencia_max = max(self.excesso_potencia_max,
                                            requested_power - self.p_max_dc)
        return False

    def _reset_ic(self):
        super()._reset_ic()
        v0 = getattr(self, "velocidade_inicial", 0.0)
        if v0 > 0.0 and self.vehicle is not None and self.transmission is not None:
            self.vv0 = v0
            self.wm0 = self.transmission.wheel_to_motor_speed(v0 / self.vehicle.wheel_radius)

    def _build_x0(self):
        x = super()._build_x0()
        self.wm_filt = self.wm0          # filtro de rotação começa na rotação real
        return x


class PedalControleTracao(Pedal):
    """Acelerador com controle de tração, usando a entrada de pedal da Simulation.

    A cada passo:
      1. calcula a força máxima que os pneus traseiros aguentam com a carga do
         último passo (pico do próprio Pacejka) vezes ``fracao_pico``;
      2. converte em torque no motor, somando o torque para acelerar as partes
         girantes (J_eff), e limita o pedal a esse torque;
      3. se o escorregamento passar do alvo, reduz um pouco mais (proporcional).

    Sem isso a roda patina até a rotação máxima, porque a Simulation não tem
    controle de tração. Um controle só por realimentação do escorregamento não
    funciona aqui: no modelo do Marco a força do pneu é limitada pelo torque do
    motor, então com torque zero a roda não é freada de volta e o escorregamento
    não cai.
    """

    def __init__(self, pneu, pedal_max=1.0, fracao_pico=1.0, kp=3.0):
        super().__init__(ganho=1.0)
        self.sim = None
        self.pedal_max = pedal_max
        self.kp = kp
        cargas = np.linspace(100.0, 2500.0, 49)
        s = np.linspace(0.002, 0.6, 600)
        picos, alvos = [], []
        for fz in cargas:
            f = np.array([pneu.Tire_forces(fz, x) for x in s])
            k = int(np.argmax(f))
            picos.append(f[k])
            # escorregamento onde a força atinge fracao_pico do pico (lado estável)
            alvos.append(s[int(np.argmax(f >= fracao_pico * f[k]))])
        self._fz = cargas
        self._f_pico = fracao_pico * np.array(picos)
        self._s_alvo = np.array(alvos)

    def forca_maxima_roda(self, fz_roda):
        return float(np.interp(fz_roda, self._fz, self._f_pico))

    def escorregamento_alvo(self, fz_roda):
        return float(np.interp(fz_roda, self._fz, self._s_alvo))

    def update(self, t):
        sim = self.sim
        veic, trans = sim.vehicle, sim.transmission
        k = sim.k_log - 1
        if k >= 0:
            fz = float(sim.fz_hist[k])
            a = float(sim.vehicle_acceleration[k])
            slip = float(sim.slip_ratio_hist[k])
        else:
            fz = veic.calculate_load_transfer(0.0, sim.vv0)
            a, slip = 0.0, 0.0
        n_rodas = getattr(veic, "n_driven_wheels", 2)
        N, eta, r = trans.final_drive_ratio, trans.efficiency, veic.wheel_radius
        forca = n_rodas * self.forca_maxima_roda(fz)
        torque = forca * r / (N * eta) + sim.j_eff * max(a, 0.0) * N / r
        pedal = torque / (sim.Kt * sim.max_current)
        excesso = slip - self.escorregamento_alvo(fz)
        if excesso > 0.0:
            pedal -= self.kp * excesso
        self.posicao = float(np.clip(pedal, 0.0, self.pedal_max))
        return self.posicao


def bateria_para_simulation():
    """BatteryPack do Marco, só para a Simulation ter tensão de barramento."""
    return BatteryPack("Li-ion", config.BATERIA["NS"], config.BATERIA["NP"])


def rodar_aceleracao(velocidade_inicial=0.0, tmax=14.0, dmax=None, controle_tracao=True):
    c = criar_componentes()
    pedal = PedalControleTracao(c["pneu"]) if controle_tracao else None
    sim = SimulacaoEndurance(
        motor=c["motor"], vehicle=c["veiculo"], transmission=c["transmissao"],
        battery=bateria_para_simulation(), tire=c["pneu"], pedal=pedal,
        tmax=tmax, dmax=dmax, p_max_dc=config.POTENCIA_MAX_DC,
        velocidade_inicial=velocidade_inicial,
    )
    if pedal is not None:
        pedal.sim = sim
    sim.simulate()
    return sim


def extrair_mapa(sim, passo_velocidade=0.25, t_inicial=0.05):
    t = np.asarray(sim.tempo)
    v = np.asarray(sim.vehicle_velocity)
    ok = t >= t_inicial
    campos = {
        "forca": np.asarray(sim.tractive_force_hist),
        "aceleracao": np.asarray(sim.vehicle_acceleration),
        "torque_motor": np.asarray(sim.conjugado),
        "rotacao_motor": np.asarray(sim.velocidade),      # já em rpm no log
        "potencia_dc": np.asarray(sim.battery_power_requested_hist),
        "escorregamento": np.asarray(sim.slip_ratio_hist),
        "resistencia": np.asarray(sim.resistive_force_hist),
        "pedal": np.asarray(sim.pedal_position_hist),
    }
    bordas = np.arange(0.0, v[ok].max() + passo_velocidade, passo_velocidade)
    centros, saida = [], {k: [] for k in campos}
    for a, b in zip(bordas[:-1], bordas[1:]):
        m = ok & (v >= a) & (v < b)
        if m.sum() < 5:
            continue
        centros.append(v[m].mean())
        for k, arr in campos.items():
            saida[k].append(arr[m].mean())
    mapa = {k: np.asarray(val) for k, val in saida.items()}
    mapa["velocidade"] = np.asarray(centros)
    return mapa


def gerar_mapa(salvar=True, arquivo=ARQUIVO_MAPA):
    inicio = time.time()
    sim = rodar_aceleracao()
    mapa = extrair_mapa(sim)
    mapa["excesso_potencia_max"] = np.array(sim.excesso_potencia_max)
    mapa["tempo_execucao"] = np.array(time.time() - inicio)
    if salvar:
        PASTA_RESULTADOS.mkdir(exist_ok=True)
        np.savez(arquivo, **mapa)
    return mapa, sim


class MapaTracao:
    """Consulta do mapa por interpolação linear na velocidade."""

    def __init__(self, arquivo=ARQUIVO_MAPA):
        if not Path(arquivo).exists():
            gerar_mapa(arquivo=arquivo)
        dados = np.load(arquivo)
        self.v = dados["velocidade"]
        self.dados = {k: dados[k] for k in dados.files}
        self.v_max = float(self.v.max())

    def _interp(self, campo, velocidade):
        return float(np.interp(velocidade, self.v, self.dados[campo]))

    def forca(self, velocidade):
        return self._interp("forca", velocidade)

    def aceleracao(self, velocidade):
        return self._interp("aceleracao", velocidade)

    def torque_motor(self, velocidade):
        return self._interp("torque_motor", velocidade)

    def rotacao_motor(self, velocidade):
        """Rotação do motor [rpm]."""
        return self._interp("rotacao_motor", velocidade)


if __name__ == "__main__":
    mapa, sim = gerar_mapa()
    print(f"\nMapa salvo em {ARQUIVO_MAPA} ({mapa['tempo_execucao']:.0f} s)")
    print(f"Excesso máximo de potência sobre 80 kW: {float(mapa['excesso_potencia_max']):.1f} W")
    print(f"{'v [m/s]':>8} {'F [N]':>8} {'a [m/s²]':>9} {'T [N·m]':>8} {'rpm':>6} {'P_dc [kW]':>9} {'slip':>6} {'pedal':>6}")
    for vv in np.arange(0, mapa["velocidade"].max(), 2.0):
        i = int(np.argmin(abs(mapa["velocidade"] - vv)))
        print(f"{mapa['velocidade'][i]:8.2f} {mapa['forca'][i]:8.0f} {mapa['aceleracao'][i]:9.2f} "
              f"{mapa['torque_motor'][i]:8.1f} {mapa['rotacao_motor'][i]:6.0f} "
              f"{mapa['potencia_dc'][i] / 1000:9.1f} {mapa['escorregamento'][i]:6.3f} {mapa['pedal'][i]:6.2f}")
