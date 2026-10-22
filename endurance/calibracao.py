"""Fase 5: validação e calibração do ritmo de Endurance.

1. Seguidor de perfil: o nosso carro percorrendo exatamente a velocidade medida
   no vídeo da Gopher, com o mesmo modelo físico do simulador (massa
   equivalente, mapa de tração como limite, tabela de perdas do Emrax). Dá a
   energia "de referência" daquele jeito de pilotar.
2. Ritmo Gopher: o simulador com o piloto ajustado para imitar a volta do vídeo
   (teto de 150 N·m, como aparece no overlay, e tempo de volta de ~53 s).
   Se o piloto estiver bem modelado, as duas energias ficam próximas.
3. Varredura de ritmos para os 22 km: tempo total x energia, e qual ritmo é o
   mais rápido que termina com o SoC acima do mínimo com folga.
4. Sensibilidade ao CG e à massa (os dois ainda são hipóteses).
"""
import contextlib
import copy
import itertools
import math

import numpy as np

import caminhos  # noqa: F401
import parametros as config
from bateria import Bateria
from dinamica import Dinamica
from frenagem import Freio
from motor import TabelaEficiencia
from pista import Pista, ler_telemetria, _suavizar
from piloto import RitmoPiloto
from simulador import SimuladorEndurance
from tracao import PASTA_RESULTADOS, MapaTracao, gerar_mapa

TEMPO_VOLTA_GOPHER = 53.0


# ---------------------------------------------------------------------------
# 1. Seguidor de perfil
# ---------------------------------------------------------------------------
def energia_seguindo_perfil(din=None, mapa=None, tabela=None, t_inicio=0.5, t_fim=53.5):
    """Energia [Wh] e consumo [Wh/km] do nosso carro na velocidade medida da Gopher."""
    din = din or Dinamica()
    mapa = mapa or MapaTracao()
    tabela = tabela or TabelaEficiencia()
    t, v = ler_telemetria()
    m = (t >= t_inicio) & (t <= t_fim)
    t, v = t[m], _suavizar(v[m])
    v = np.convolve(np.pad(v, 2, mode="edge"), np.ones(5) / 5, "valid")    # suaviza ~1 s no total
    a = np.gradient(v, t)
    energia, distancia, freio = 0.0, 0.0, 0.0
    for k in range(len(t) - 1):
        dt = t[k + 1] - t[k]
        vk, ak = v[k], min(a[k], mapa.aceleracao(v[k]))          # não acelera mais que o pneu
        f_res = din.resistencia(vk)
        forca = din.m_eq_tracao * ak + f_res
        if forca > 0.0:
            torque = din.torque_motor_de_forca_roda(forca)
            energia += tabela.potencia_dc(din.rpm_motor(vk), torque) * dt
        else:
            f_vazio = din.arrasto_motor_em_vazio(vk)
            freio += max(-din.m_eq * ak - f_res - f_vazio, 0.0) * vk * dt
        distancia += vk * dt
    return {"energia_wh": energia / 3600, "distancia_m": distancia,
            "consumo_wh_km": energia / 3600 / distancia * 1000, "energia_freio_wh": freio / 3600}


# ---------------------------------------------------------------------------
# Execução de um ritmo
# ---------------------------------------------------------------------------
class Contexto:
    """Peças reaproveitadas entre execuções (mapa, tabela, pista)."""

    def __init__(self, arquivo_mapa=None):
        self.din = Dinamica()
        self.pista = Pista(dinamica=self.din)
        self.mapa = MapaTracao(arquivo_mapa) if arquivo_mapa else MapaTracao()
        self.tabela = TabelaEficiencia()

    def rodar(self, ritmo, distancia=22_000.0, parar_no_soc_minimo=False):
        sim = SimuladorEndurance(ritmo=ritmo, distancia_total=distancia, dinamica=self.din,
                                 pista=self.pista, mapa=self.mapa, tabela=self.tabela,
                                 bateria=Bateria(), parar_no_soc_minimo=parar_no_soc_minimo)
        return sim.rodar()


def perfil_video():
    """Velocidade do vídeo por distância, já no referencial da nossa pista."""
    from pista import segmentos_do_video
    t, v = ler_telemetria()
    m = (t >= 0.5) & (t <= 53.5)
    t, v = t[m], _suavizar(v[m])
    s = np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(t))])
    _, inicio = segmentos_do_video(retornar_inicio=True)
    return s, v, inicio


def erro_perfil(r, ctx, volta=2):
    """RMS [m/s] entre a velocidade simulada (uma volta do meio) e a do vídeo, de 100 m ao fim."""
    sv, vv, inicio = perfil_video()
    L = ctx.pista.comprimento_volta
    s, v = r["distancia"], r["velocidade"]
    meio = (s >= (volta - 1) * L) & (s < volta * L)
    x = np.linspace(100.0, sv[-1] - 40.0, 300)
    simulada = np.interp((x - inicio) % L, s[meio] - (volta - 1) * L, v[meio])
    return float(np.sqrt(np.mean((simulada - np.interp(x, sv, vv)) ** 2)))


def ajustar_ritmo_gopher(ctx, voltas=3, torque=150.0):
    """Ritmo que mais se aproxima do perfil de velocidade do vídeo, com volta de 53 ± 1,5 s."""
    melhor = None
    for fator, vmax, rolagem in itertools.product((1.0, 0.95, 0.9, 0.85),
                                                  (None, 85 / 3.6, 80 / 3.6, 75 / 3.6, 70 / 3.6),
                                                  (0.0, 0.5, 1.0, 1.5, 2.0)):
        ritmo = RitmoPiloto(fator_curva=fator, torque_maximo=torque, velocidade_maxima=vmax,
                            tempo_rolagem=rolagem)
        r = ctx.rodar(ritmo, voltas * ctx.pista.comprimento_volta)
        res = r["resumo"]
        if abs(res["tempo_volta_medio_s"] - TEMPO_VOLTA_GOPHER) > 1.5:
            continue
        erro = erro_perfil(r, ctx)
        if melhor is None or erro < melhor[0]:
            melhor = (erro, ritmo, res)
    return melhor[1], melhor[2], melhor[0]


# ---------------------------------------------------------------------------
# 3. Varredura de ritmos
# ---------------------------------------------------------------------------
GRADE_PADRAO = {
    "fator_curva": (1.0, 0.9),
    "torque_maximo": (None, 150.0, 100.0),
    "velocidade_maxima": (None, 80 / 3.6, 70 / 3.6),
    "tempo_rolagem": (0.0, 1.0, 2.0),
}


def varrer_ritmos(ctx, grade=None, distancia=22_000.0):
    grade = grade or GRADE_PADRAO
    nomes = list(grade)
    linhas = []
    for valores in itertools.product(*(grade[n] for n in nomes)):
        ritmo = RitmoPiloto(**dict(zip(nomes, valores)))
        res = ctx.rodar(ritmo, distancia)["resumo"]
        linhas.append((ritmo, res))
    return linhas


def melhor_ritmo(linhas, soc_minimo=config.SOC_MINIMO, folga=0.05):
    """O mais rápido que termina os 22 km com SoC >= mínimo + folga."""
    viaveis = [(r, res) for r, res in linhas
               if res["status"] == "completo" and res["soc_final"] >= soc_minimo + folga]
    return min(viaveis, key=lambda x: x[1]["tempo_s"]) if viaveis else None


def fronteira(linhas):
    """Ritmos que nenhum outro bate ao mesmo tempo em tempo e energia."""
    pontos = sorted(linhas, key=lambda x: x[1]["tempo_s"])
    saida, melhor_energia = [], math.inf
    for r, res in pontos:
        if res["energia_wh"] < melhor_energia:
            saida.append((r, res))
            melhor_energia = res["energia_wh"]
    return saida


def descrever(ritmo):
    tq = f"{ritmo.torque_maximo:.0f} N·m" if ritmo.torque_maximo else "livre"
    vm = f"{ritmo.velocidade_maxima * 3.6:.0f} km/h" if ritmo.velocidade_maxima else "livre"
    return f"curva {ritmo.fator_curva:.2f} | torque {tq} | vel. máx {vm} | rolagem {ritmo.tempo_rolagem:.1f} s"


# ---------------------------------------------------------------------------
# 4. Sensibilidade (CG e massa)
# ---------------------------------------------------------------------------
@contextlib.contextmanager
def parametros_temporarios(fracao_traseira=None, massa=None):
    """Troca CG e/ou massa em ``parametros`` só dentro do bloco."""
    backup = (copy.deepcopy(config.VEICULO), copy.deepcopy(config.FREIO))
    try:
        if massa is not None:
            config.VEICULO["mass"] = massa
            config.FREIO["Mt"] = massa
        fr = fracao_traseira if fracao_traseira is not None else config.VEICULO["dist_cg"] / config.VEICULO["L"]
        config.VEICULO["dist_cg"] = fr * config.VEICULO["L"]
        peso = config.VEICULO["mass"] * config.G
        config.FREIO.update(psi=fr, FzF=peso * (1 - fr), FzR=peso * fr)
        yield
    finally:
        config.VEICULO.clear(); config.VEICULO.update(backup[0])
        config.FREIO.clear(); config.FREIO.update(backup[1])


def contexto_cenario(fracao_traseira=None, massa=None):
    """Gera (ou reaproveita) o mapa de tração do cenário e monta o contexto."""
    nome = f"mapa_tracao_cg{(fracao_traseira or 0.55) * 100:.0f}_m{massa or config.VEICULO['mass']:.0f}.npz"
    arquivo = PASTA_RESULTADOS / nome
    with parametros_temporarios(fracao_traseira, massa):
        if not arquivo.exists():
            gerar_mapa(arquivo=arquivo)
        ctx = Contexto.__new__(Contexto)
        ctx.din = Dinamica(freio=Freio())
        ctx.pista = Pista(segmentos=Pista(dinamica=ctx.din).segmentos, dinamica=ctx.din)
        ctx.mapa = MapaTracao(arquivo)
        ctx.tabela = TabelaEficiencia()
    return ctx


if __name__ == "__main__":
    ctx = Contexto()

    print("=== 1. Nosso carro seguindo a velocidade da Gopher ===")
    ref = energia_seguindo_perfil(ctx.din, ctx.mapa, ctx.tabela)
    print(f"{ref['distancia_m']:.0f} m, {ref['energia_wh']:.1f} Wh, {ref['consumo_wh_km']:.0f} Wh/km")

    print("\n=== 2. Simulador com ritmo parecido com o da Gopher ===")
    ritmo_g, res_g, erro_g = ajustar_ritmo_gopher(ctx)
    print(descrever(ritmo_g), f"| erro de perfil {erro_g:.2f} m/s")
    print(f"volta {res_g['tempo_volta_medio_s']:.1f} s, {res_g['consumo_wh_km']:.0f} Wh/km, "
          f"tempo: " + ", ".join(f"{k} {v * 100:.0f}%" for k, v in res_g["fracao_tempo"].items()))
