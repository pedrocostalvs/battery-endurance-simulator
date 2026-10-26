"""Fase 3: pista equivalente à volta de Autocross do vídeo da Gopher.

A pista sai da telemetria do vídeo (``dados/telemetria_autocross_gopher_2023.csv``):

1. integra a velocidade para ter a distância ao longo da volta;
2. cada mínimo local de velocidade é uma curva;
3. raio da curva pela velocidade mínima: R = v_min² / (μ g), com μ = 1,3
   (supondo aderência parecida com a do nosso carro);
4. comprimento do arco: trecho em torno do mínimo com v <= 1,08·v_min
   (mínimo de 5 m);
5. o resto vira reta; a reta de largada e a de chegada são unidas (no
   Endurance a volta é fechada) e limitadas a 77 m, como no regulamento.

Para usar outra pista basta montar uma lista de ``Segmento`` com comprimentos e
raios medidos.
"""
import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import caminhos  # noqa: F401
import parametros as config

ARQUIVO_TELEMETRIA = Path(__file__).resolve().parent / "dados" / "telemetria_autocross_gopher_2023.csv"
RETA_MAXIMA_REGULAMENTO = 77.0     # [m]
RAIO_MINIMO_REGULAMENTO = 4.5      # [m] hairpin com diâmetro externo de 9 m


@dataclass(frozen=True)
class Segmento:
    nome: str
    comprimento: float
    raio: float | None = None       # None = reta


def ler_telemetria(arquivo=ARQUIVO_TELEMETRIA):
    t, v = [], []
    with open(arquivo, encoding="utf-8") as f:
        linhas = (linha for linha in f if not linha.startswith("#"))
        for linha in csv.DictReader(linhas):
            t.append(float(linha["tempo_s"]))
            v.append(float(linha["velocidade_m_s"]))
    return np.asarray(t), np.asarray(v)


def _suavizar(v):
    mediana = np.array([np.median(v[max(0, i - 3):i + 4]) for i in range(len(v))])
    nucleo = np.ones(5) / 5
    return np.convolve(np.pad(mediana, 2, mode="edge"), nucleo, "valid")


def segmentos_do_video(t_inicio=0.5, t_fim=53.5, mu=config.MU_PNEU, proeminencia=0.6,
                       fator_arco=1.08, arco_minimo=5.0, retornar_inicio=False):
    """Segmentos da volta do vídeo. Com ``retornar_inicio``, devolve também a
    posição no vídeo [m] onde começa a Curva 1 (o início da nossa volta)."""
    from scipy.signal import find_peaks
    t, v = ler_telemetria()
    m = (t >= t_inicio) & (t <= t_fim)
    t, v = t[m], _suavizar(v[m])
    s = np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(t))])
    minimos, _ = find_peaks(-v, prominence=proeminencia, distance=6)

    curvas = []
    for i in minimos:
        vmin = v[i]
        a = i
        while a > 0 and v[a - 1] <= fator_arco * vmin:
            a -= 1
        b = i
        while b < len(v) - 1 and v[b + 1] <= fator_arco * vmin:
            b += 1
        comprimento = max(s[b] - s[a], arco_minimo)
        centro = s[i]
        curvas.append([centro - comprimento / 2, centro + comprimento / 2, vmin ** 2 / (mu * config.G), centro])

    # curvas encostadas: arcos que se sobrepõem são divididos no meio entre os ápices
    for anterior, atual in zip(curvas[:-1], curvas[1:]):
        if atual[0] < anterior[1]:
            meio = (anterior[3] + atual[3]) / 2
            anterior[1], atual[0] = min(anterior[1], meio), max(atual[0], meio)

    segmentos, fim_anterior = [], None
    for n, (ini, fim, raio, _) in enumerate(curvas, start=1):
        if fim_anterior is not None and ini - fim_anterior > 0.5:
            segmentos.append(Segmento(f"Reta {n - 1}-{n}", ini - fim_anterior))
        segmentos.append(Segmento(f"Curva {n}", fim - ini, raio))
        fim_anterior = fim
    reta_largada = curvas[0][0] + (s[-1] - fim_anterior)
    segmentos.append(Segmento("Reta de largada/chegada", min(reta_largada, RETA_MAXIMA_REGULAMENTO)))
    if retornar_inicio:
        return segmentos, float(curvas[0][0])
    return segmentos


class Pista:
    def __init__(self, segmentos=None, dinamica=None):
        self.segmentos = list(segmentos) if segmentos is not None else segmentos_do_video()
        if not self.segmentos or any(sg.comprimento <= 0 for sg in self.segmentos):
            raise ValueError("todos os segmentos precisam ter comprimento positivo")
        if dinamica is None:
            from dinamica import Dinamica
            dinamica = Dinamica()
        self.dinamica = dinamica
        self.limites = [dinamica.velocidade_limite_curva(sg.raio) for sg in self.segmentos]
        self.bordas = np.concatenate([[0.0], np.cumsum([sg.comprimento for sg in self.segmentos])])
        self.comprimento_volta = float(self.bordas[-1])

    def indice(self, distancia):
        pos = distancia % self.comprimento_volta
        return min(int(np.searchsorted(self.bordas, pos, side="right")) - 1, len(self.segmentos) - 1)

    def segmento(self, distancia):
        return self.segmentos[self.indice(distancia)]

    def limite(self, distancia):
        return self.limites[self.indice(distancia)]

    def restricoes_a_frente(self, distancia, horizonte):
        """Lista de (distância até a entrada, velocidade limite, nome) das curvas à frente."""
        pos = distancia % self.comprimento_volta
        i = self.indice(distancia)
        falta = self.bordas[i + 1] - pos
        saida, j = [], (i + 1) % len(self.segmentos)
        while falta <= horizonte:
            if self.segmentos[j].raio is not None:
                saida.append((falta, self.limites[j], self.segmentos[j].nome))
            falta += self.segmentos[j].comprimento
            j = (j + 1) % len(self.segmentos)
        return saida

    def verificar_regulamento(self):
        problemas = []
        for sg in self.segmentos:
            if sg.raio is None and sg.comprimento > RETA_MAXIMA_REGULAMENTO + 1e-6:
                problemas.append(f"{sg.nome}: reta de {sg.comprimento:.1f} m (máx. 77 m)")
            if sg.raio is not None and sg.raio < RAIO_MINIMO_REGULAMENTO - 0.05:
                problemas.append(f"{sg.nome}: raio de {sg.raio:.1f} m (mín. 4,5 m)")
        return problemas

    def tabela(self):
        linhas = [f"{'Segmento':<26}{'Compr. [m]':>11}{'Raio [m]':>10}{'v lim [km/h]':>14}"]
        for sg, lim in zip(self.segmentos, self.limites):
            raio = f"{sg.raio:.1f}" if sg.raio is not None else "-"
            vl = f"{lim * 3.6:.1f}" if math.isfinite(lim) else "-"
            linhas.append(f"{sg.nome:<26}{sg.comprimento:>11.1f}{raio:>10}{vl:>14}")
        linhas.append(f"{'Total':<26}{self.comprimento_volta:>11.1f}")
        return "\n".join(linhas)


def volta_quase_estatica(pista, mapa, passo=0.25, voltas=3):
    """Volta ideal (piloto sempre no limite), só para conferir a compatibilidade.

    Passo de ida: acelera pelo mapa de tração. Passo de volta: freia no limite.
    Em cada ponto fica a menor das velocidades (limite da curva, ida e volta).
    Roda algumas voltas seguidas para a volta do meio já começar em movimento.
    """
    din = pista.dinamica
    n = int(round(pista.comprimento_volta * voltas / passo))
    s = np.arange(n) * passo
    vlim = np.array([min(pista.limite(x), mapa.v_max) for x in s])
    ida = vlim.copy()
    ida[0] = 0.0
    for k in range(1, n):
        a = mapa.aceleracao(ida[k - 1])
        ida[k] = min(vlim[k], math.sqrt(max(ida[k - 1] ** 2 + 2 * a * passo, 0.0)))
    volta = ida.copy()
    for k in range(n - 2, -1, -1):
        raio = pista.segmento(s[k]).raio
        d = din.desaceleracao_maxima(volta[k + 1], raio)
        volta[k] = min(volta[k], math.sqrt(volta[k + 1] ** 2 + 2 * d * passo))
    v = volta
    meio = (s >= pista.comprimento_volta) & (s < 2 * pista.comprimento_volta)
    vm = np.maximum(v[meio], 0.1)
    tempo = float(np.sum(passo / vm))
    return {"distancia": s[meio] - pista.comprimento_volta, "velocidade": v[meio], "tempo_volta": tempo,
            "v_media": pista.comprimento_volta / tempo, "v_max": float(v[meio].max())}


if __name__ == "__main__":
    from tracao import MapaTracao
    pista = Pista()
    print(pista.tabela())
    print("\nRegulamento:", pista.verificar_regulamento() or "ok")
    r = volta_quase_estatica(pista, MapaTracao())
    print(f"\nVolta ideal do nosso carro: {r['tempo_volta']:.1f} s, média {r['v_media'] * 3.6:.1f} km/h, "
          f"máx {r['v_max'] * 3.6:.1f} km/h")
