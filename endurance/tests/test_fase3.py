"""Fase 3: pista, conferida contra o vídeo, o regulamento e as fases 1 e 2.

Rodar da raiz do repositório:
    python -m unittest endurance.tests.test_fase3 -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import caminhos  # noqa: E402,F401
from pista import (Pista, Segmento, ler_telemetria, segmentos_do_video,  # noqa: E402
                   volta_quase_estatica, _suavizar)
from tracao import MapaTracao  # noqa: E402

TEMPO_VOLTA_VIDEO = 53.0       # s
DISTANCIA_VIDEO = 680.6        # m


class TestPista(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pista = Pista()
        cls.mapa = MapaTracao()
        cls.volta = volta_quase_estatica(cls.pista, cls.mapa)

    def test_tamanho_e_curvas(self):
        self.assertAlmostEqual(self.pista.comprimento_volta, DISTANCIA_VIDEO, delta=0.02 * DISTANCIA_VIDEO)
        curvas = [sg for sg in self.pista.segmentos if sg.raio is not None]
        self.assertEqual(len(curvas), 14)

    def test_regulamento(self):
        self.assertEqual(self.pista.verificar_regulamento(), [])

    def test_limite_das_curvas_perto_do_minimo_do_video(self):
        """Com downforce o nosso limite fica um pouco acima do mínimo do vídeo (até 5%)."""
        for sg, lim in zip(self.pista.segmentos, self.pista.limites):
            if sg.raio is None:
                continue
            v_video = math.sqrt(sg.raio * 1.3 * 9.81)
            self.assertGreaterEqual(lim, v_video)
            self.assertLess(lim, 1.05 * v_video)

    def test_restricoes_a_frente(self):
        r = self.pista.restricoes_a_frente(0.0, 100.0)
        self.assertTrue(r)
        self.assertTrue(all(0.0 <= d <= 100.0 for d, _, _ in r))

    def test_segmentos_manuais(self):
        p = Pista([Segmento("reta", 50.0), Segmento("curva", 20.0, 10.0)], dinamica=self.pista.dinamica)
        self.assertEqual(p.comprimento_volta, 70.0)
        self.assertEqual(p.segmento(55.0).nome, "curva")
        self.assertEqual(p.segmento(75.0).nome, "reta")      # volta fechada

    # --- compatibilidade com as fases 1 e 2 ----------------------------------
    def test_volta_respeita_mapa_e_curvas(self):
        v, s = self.volta["velocidade"], self.volta["distancia"]
        self.assertLessEqual(self.volta["v_max"], self.mapa.v_max + 1e-6)
        for vi, si in zip(v[::20], s[::20]):
            self.assertLessEqual(vi, self.pista.limite(si) + 1e-6)

    def test_tempo_de_volta_plausivel(self):
        """Mais rápida que a Gopher (piloto ideal), mas na mesma ordem; média na faixa do regulamento."""
        t = self.volta["tempo_volta"]
        self.assertLess(t, TEMPO_VOLTA_VIDEO)
        self.assertGreater(t, 0.75 * TEMPO_VOLTA_VIDEO)
        self.assertTrue(48.0 <= self.volta["v_media"] * 3.6 <= 57.0)

    def test_perfil_parecido_com_o_video(self):
        tv, vv = ler_telemetria()
        m = (tv >= 0.5) & (tv <= 53.5)
        tv, vv = tv[m], _suavizar(vv[m])
        sv = np.concatenate([[0.0], np.cumsum((vv[1:] + vv[:-1]) / 2 * np.diff(tv))])
        s, v = self.volta["distancia"], self.volta["velocidade"]
        _, inicio = segmentos_do_video(retornar_inicio=True)   # Curva 1 no vídeo
        # compara de 100 m até perto do fim (o vídeo começa parado; a nossa volta, em movimento)
        x = np.linspace(100.0, sv[-1] - 40.0, 400)
        a = np.interp(x, sv, vv)
        b = np.interp((x - inicio) % self.pista.comprimento_volta, s, v)
        self.assertGreater(np.corrcoef(a, b)[0, 1], 0.7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
