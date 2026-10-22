"""Fase 4: loop do Endurance com piloto, mapa de tração, freio e bateria.

A cada passo dt:
    1. o piloto decide o modo (acelerar, manter, rolar, frear);
    2. calcula torque do motor, força de frenagem e aceleração do carro;
    3. potência DC pelo torque e rotação (tabela de perdas do Emrax ÷ inversor);
    4. a bateria (modelo de tensão do Pedro) avança com essa potência;
    5. integra velocidade e distância.

Modos:
    ACELERAR  menor entre o mapa de tração (limite do pneu, Fase 2), reduzido em
              curva pelo círculo de atrito, e o teto de torque do ritmo:
                  a = (T·N·η/r - F_res) / m_eq_tracao
              potência DC limitada a 80 kW
    MANTER    torque só para vencer as resistências: T = F_res·r/(N·η)
    ROLAR     torque zero e sem potência; desacelera por resistências e pelas
              perdas em vazio do motor (o rotor continua girando)
    FREAR     força de frenagem para a desaceleração pedida pelo piloto,
              limitada pela aderência (Fase 1); sem regeneração
"""
import math
import time

import numpy as np

import caminhos  # noqa: F401
import parametros as config
from bateria import Bateria
from dinamica import Dinamica
from motor import TabelaEficiencia
from pista import Pista
from piloto import ACELERAR, FREAR, MANTER, ROLAR, Piloto, RitmoPiloto
from tracao import MapaTracao

CAMPOS = ("tempo", "distancia", "velocidade", "aceleracao", "modo", "torque_motor", "rpm_motor",
          "potencia_dc", "forca_freio", "tensao_pack", "corrente_pack", "corrente_celula", "soc",
          "temperatura_celula", "energia_wh")
CODIGO_MODO = {ACELERAR: 0, MANTER: 1, ROLAR: 2, FREAR: 3}


class SimuladorEndurance:
    def __init__(self, ritmo=None, distancia_total=22_000.0, dt=0.01,
                 dinamica=None, pista=None, mapa=None, tabela=None, bateria=None,
                 parar_no_soc_minimo=True):
        self.din = dinamica or Dinamica()
        self.pista = pista or Pista(dinamica=self.din)
        self.mapa = mapa or MapaTracao()
        self.tabela = tabela or TabelaEficiencia()
        self.bateria = bateria or Bateria()
        self.ritmo = ritmo or RitmoPiloto()
        self.piloto = Piloto(self.pista, self.din, self.ritmo, v_max_trem=self.mapa.v_max)
        self.distancia_total = distancia_total
        self.dt = dt
        self.parar_no_soc_minimo = parar_no_soc_minimo

    # ------------------------------------------------------------------
    def _acelerar(self, v, raio):
        din, mapa = self.din, self.mapa
        f_res = din.resistencia(v)
        # círculo de atrito em curva: reduz o que sobra para tracionar
        fator = 1.0
        if raio is not None:
            df_d, df_t = din.downforce(v)
            fz = din.m * config.G + df_d + df_t
            fator = math.sqrt(max(1.0 - (din.forca_lateral(v, raio) / (config.MU_PNEU * fz)) ** 2, 0.0))
        a = mapa.aceleracao(v) * fator
        torque = mapa.torque_motor(v) * fator
        rpm = mapa.rotacao_motor(v)                         # inclui o escorregamento do mapa
        teto = self.ritmo.torque_maximo
        if teto is not None and teto < torque:
            a_teto = (din.forca_roda_de_torque_motor(teto) - f_res) / din.m_eq_tracao
            if a_teto < a:
                torque, a, rpm = teto, a_teto, din.rpm_motor(v)
        potencia = self.tabela.potencia_dc(rpm, torque)
        if potencia > config.POTENCIA_MAX_DC:
            torque *= config.POTENCIA_MAX_DC / potencia
            rpm = din.rpm_motor(v)
            a = min(a, (din.forca_roda_de_torque_motor(torque) - f_res) / din.m_eq_tracao)
            potencia = self.tabela.potencia_dc(rpm, torque)
        return a, torque, rpm, potencia

    def rodar(self, mostrar_progresso=False):
        inicio = time.time()
        din, bat, dt = self.din, self.bateria, self.dt
        t = s = v = 0.0
        hist = {k: [] for k in CAMPOS}
        status, motivo = "completo", "distancia_atingida"
        energia_freio = energia_resist = energia_vazio = 0.0
        proximo_aviso = 1000.0

        while s < self.distancia_total - 1e-9:
            decisao = self.piloto.decidir(s, v)
            raio = self.pista.segmento(s).raio
            f_res = din.resistencia(v)
            f_vazio = din.arrasto_motor_em_vazio(v) if v > 0.1 else 0.0
            torque = rpm = potencia = forca_freio = 0.0

            if decisao.modo == ACELERAR:
                a, torque, rpm, potencia = self._acelerar(v, raio)
                if v + a * dt > decisao.velocidade_alvo:          # não passar do alvo
                    a = max((decisao.velocidade_alvo - v) / dt, 0.0)
            elif decisao.modo == MANTER:
                torque = din.torque_motor_de_forca_roda(f_res)
                rpm = din.rpm_motor(v)
                potencia = self.tabela.potencia_dc(rpm, torque)
                a = 0.0
            elif decisao.modo == ROLAR:
                a = -(f_res + f_vazio) / din.m_eq
            else:  # FREAR
                maxima = din.forca_freio_maxima(v, raio)
                forca_freio = min(max(decisao.desaceleracao_pedida * din.m_eq - f_res - f_vazio, 0.0), maxima)
                a = -(forca_freio + f_res + f_vazio) / din.m_eq

            ponto = bat.passo(potencia, dt)
            if ponto["limitado"]:
                status, motivo = "interrompido", "bateria_nao_entrega_potencia"
                break

            v_novo = max(v + a * dt, 0.0)
            ds = 0.5 * (v + v_novo) * dt
            if s + ds > self.distancia_total:                    # último passo exato
                ds = self.distancia_total - s
            energia_freio += forca_freio * ds
            energia_resist += f_res * ds
            if decisao.modo in (ROLAR, FREAR):
                energia_vazio += f_vazio * ds
            t += dt
            s += ds
            v = v_novo

            for k, val in (("tempo", t), ("distancia", s), ("velocidade", v), ("aceleracao", a),
                           ("modo", CODIGO_MODO[decisao.modo]), ("torque_motor", torque),
                           ("rpm_motor", rpm), ("potencia_dc", potencia), ("forca_freio", forca_freio),
                           ("tensao_pack", ponto["V_pack"]), ("corrente_pack", ponto["I_pack"]),
                           ("corrente_celula", ponto["I_cel"]), ("soc", ponto["SoC"]),
                           ("temperatura_celula", ponto["T"] - 273.15), ("energia_wh", bat.energia_wh)):
                hist[k].append(val)

            if ponto["fim"]:
                status, motivo = "interrompido", "tensao_minima_da_celula"
                break
            if self.parar_no_soc_minimo and ponto["SoC"] <= config.SOC_MINIMO:
                status, motivo = "interrompido", "soc_minimo"
                break
            if t > 7200:
                status, motivo = "interrompido", "tempo_maximo"
                break
            if mostrar_progresso and s >= proximo_aviso:
                print(f"  {s / 1000:5.1f} km  t={t:6.0f} s  SoC={ponto['SoC'] * 100:5.1f}%")
                proximo_aviso += 1000.0

        r = {k: np.asarray(val) for k, val in hist.items()}
        r.update(status=status, motivo=motivo, tempo_execucao=time.time() - inicio,
                 energia_freio_wh=energia_freio / 3600, energia_resistencias_wh=energia_resist / 3600,
                 energia_vazio_motor_wh=energia_vazio / 3600, perdas_bateria_wh=bat.perdas_wh,
                 comprimento_volta=self.pista.comprimento_volta)
        r["resumo"] = resumir(r)
        return r


def media_movel(x, t, janela):
    if len(x) == 0:
        return np.array([])
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0
    n = max(int(round(janela / dt)), 1)
    return np.convolve(x, np.ones(n) / n, mode="valid")


def resumir(r):
    t, s, v = r["tempo"], r["distancia"], r["velocidade"]
    if len(t) == 0:
        return {}
    dist = float(s[-1])
    energia = float(r["energia_wh"][-1])
    volta = r["comprimento_volta"]
    n_voltas = int(dist // volta)
    tempos_voltas = []
    for k in range(1, n_voltas + 1):
        tempos_voltas.append(float(np.interp(k * volta, s, t)))
    tempos_voltas = np.diff([0.0] + tempos_voltas)
    pot_60s = media_movel(r["potencia_dc"], t, 60.0)
    # rotação sem enfraquecimento de campo: ~8 rpm por volt sob carga (datasheet HV)
    acima_base = r["rpm_motor"] > 8.0 * r["tensao_pack"]
    modos = r["modo"]
    return {
        "status": r["status"], "motivo": r["motivo"],
        "distancia_m": dist, "tempo_s": float(t[-1]),
        "velocidade_media_kmh": dist / float(t[-1]) * 3.6, "velocidade_max_kmh": float(v.max()) * 3.6,
        "voltas_completas": n_voltas,
        "tempo_volta_medio_s": float(np.mean(tempos_voltas[1:])) if n_voltas > 1 else float("nan"),
        "primeira_volta_s": float(tempos_voltas[0]) if n_voltas else float("nan"),
        "energia_wh": energia, "consumo_wh_km": energia / dist * 1000,
        "soc_final": float(r["soc"][-1]),
        "potencia_media_kw": energia * 3.6 / float(t[-1]),
        "potencia_max_kw": float(r["potencia_dc"].max()) / 1000,
        "potencia_media_60s_max_kw": float(pot_60s.max()) / 1000 if len(pot_60s) else float("nan"),
        "tensao_min_v": float(r["tensao_pack"].min()), "tensao_max_v": float(r["tensao_pack"].max()),
        "corrente_celula_max_a": float(r["corrente_celula"].max()),
        "temperatura_celula_max_c": float(r["temperatura_celula"].max()),
        "fracao_tempo": {nome: float(np.mean(modos == cod)) for nome, cod in CODIGO_MODO.items()},
        "fracao_tempo_acima_rotacao_base": float(np.mean(acima_base)),
        "energia_freio_wh": r["energia_freio_wh"], "energia_resistencias_wh": r["energia_resistencias_wh"],
        "energia_vazio_motor_wh": r["energia_vazio_motor_wh"], "perdas_bateria_wh": r["perdas_bateria_wh"],
        "tempo_execucao_s": r["tempo_execucao"],
    }


def imprimir_resumo(res):
    f = res["fracao_tempo"]
    print(f"\nStatus: {res['status']} ({res['motivo']})")
    print(f"Distância {res['distancia_m'] / 1000:.2f} km em {res['tempo_s']:.0f} s "
          f"({res['voltas_completas']} voltas, média {res['velocidade_media_kmh']:.1f} km/h, "
          f"máx {res['velocidade_max_kmh']:.1f} km/h)")
    print(f"Volta média {res['tempo_volta_medio_s']:.1f} s (primeira {res['primeira_volta_s']:.1f} s)")
    print(f"Energia {res['energia_wh']:.0f} Wh ({res['consumo_wh_km']:.1f} Wh/km), SoC final {res['soc_final'] * 100:.1f}%")
    print(f"Potência média {res['potencia_media_kw']:.1f} kW, máx {res['potencia_max_kw']:.1f} kW, "
          f"máx média de 60 s {res['potencia_media_60s_max_kw']:.1f} kW")
    print(f"Pack {res['tensao_min_v']:.0f} a {res['tensao_max_v']:.0f} V, célula até {res['corrente_celula_max_a']:.1f} A "
          f"e {res['temperatura_celula_max_c']:.1f} °C")
    print(f"Tempo: acelerando {f['acelerar'] * 100:.0f}%, mantendo {f['manter'] * 100:.0f}%, "
          f"rolando {f['rolar'] * 100:.0f}%, freando {f['frear'] * 100:.0f}%")
    print(f"Energia dissipada: freio {res['energia_freio_wh']:.0f} Wh, resistências {res['energia_resistencias_wh']:.0f} Wh, "
          f"perdas em vazio rolando/freando {res['energia_vazio_motor_wh']:.0f} Wh, bateria {res['perdas_bateria_wh']:.0f} Wh")
    print(f"Acima da rotação base (precisa enfraquecer campo): {res['fracao_tempo_acima_rotacao_base'] * 100:.1f}% do tempo")
    print(f"(executado em {res['tempo_execucao_s']:.0f} s)")


if __name__ == "__main__":
    sim = SimuladorEndurance()
    r = sim.rodar(mostrar_progresso=True)
    imprimir_resumo(r["resumo"])
