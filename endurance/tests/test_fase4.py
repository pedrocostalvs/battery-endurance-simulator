"""Fase 4: piloto e loop, conferidos contra as fases 1, 2 e 3.

Rodar da raiz do repositório:
    python -m unittest endurance.tests.test_fase4 -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import caminhos  # noqa: E402,F401
import parametros as config  # noqa: E402
from bateria import Bateria  # noqa: E402
from dinamica import Dinamica  # noqa: E402
from motor import TabelaEficiencia  # noqa: E402
from pista import Pista, volta_quase_estatica  # noqa: E402
from piloto import RitmoPiloto  # noqa: E402
from simulador import CODIGO_MODO, SimuladorEndurance  # noqa: E402
from tracao import MapaTracao  # noqa: E402


class TestLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.din = Dinamica()
        cls.pista = Pista(dinamica=cls.din)
        cls.mapa = MapaTracao()
        cls.tabela = TabelaEficiencia()
        cls.voltas = 4
        cls.r = cls._rodar(RitmoPiloto())

    @classmethod
    def _rodar(cls, ritmo, voltas=None):
        sim = SimuladorEndurance(ritmo=ritmo, distancia_total=(voltas or cls.voltas) * cls.pista.comprimento_volta,
                                 dinamica=cls.din, pista=cls.pista, mapa=cls.mapa, tabela=cls.tabela,
                                 bateria=Bateria())
        return sim.rodar()

    def test_completa_a_distancia(self):
        self.assertEqual(self.r["status"], "completo")
        self.assertAlmostEqual(self.r["distancia"][-1], self.voltas * self.pista.comprimento_volta, places=6)

    def test_volta_bate_com_volta_ideal_da_fase3(self):
        ideal = volta_quase_estatica(self.pista, self.mapa)["tempo_volta"]
        self.assertAlmostEqual(self.r["resumo"]["tempo_volta_medio_s"], ideal, delta=0.03 * ideal)

    def test_respeita_curvas_e_mapa(self):
        s, v = self.r["distancia"], self.r["velocidade"]
        limites = np.array([self.pista.limite(x) for x in s])
        self.assertLessEqual(float(np.max(v - limites)), RitmoPiloto().faixa_velocidade + 0.05)
        self.assertLessEqual(v.max(), self.mapa.v_max + 1e-6)

    def test_aceleracao_e_frenagem_dentro_dos_limites(self):
        a = self.r["aceleracao"]
        v = self.r["velocidade"] - a * 0.01            # velocidade no início do passo
        acelerando = self.r["modo"] == CODIGO_MODO["acelerar"]
        a_mapa = np.array([self.mapa.aceleracao(x) for x in v[acelerando]])
        self.assertTrue(np.all(a[acelerando] <= a_mapa + 1e-6))
        freando = self.r["modo"] == CODIGO_MODO["frear"]
        d_max = np.array([self.din.desaceleracao_maxima(x) for x in v[freando]])
        self.assertTrue(np.all(-a[freando] <= d_max + 1e-6))

    def test_potencia_e_energia(self):
        r = self.r
        self.assertLessEqual(r["potencia_dc"].max(), config.POTENCIA_MAX_DC + 1.0)
        integral = float(np.sum(r["potencia_dc"]) * 0.01 / 3600)
        self.assertAlmostEqual(r["energia_wh"][-1], integral, delta=0.005 * integral)
        self.assertTrue(np.all(np.diff(r["soc"]) <= 1e-12))

    def test_balanco_de_energia(self):
        """Energia nas rodas (freio + resistências + perdas em vazio + energia cinética final)
        entre 75% e 95% da energia tirada da bateria: o resto são perdas no motor,
        inversor, transmissão e escorregamento."""
        r, din = self.r, self.din
        cinetica_final = 0.5 * din.m_eq * r["velocidade"][-1] ** 2 / 3600
        rodas = r["energia_freio_wh"] + r["energia_resistencias_wh"] + r["energia_vazio_motor_wh"] + cinetica_final
        razao = rodas / r["energia_wh"][-1]
        self.assertGreater(razao, 0.75)
        self.assertLess(razao, 0.95)

    def test_rolagem_economiza_energia(self):
        com = self._rodar(RitmoPiloto(tempo_rolagem=1.0))["resumo"]
        sem = self.r["resumo"]
        self.assertLess(com["consumo_wh_km"], sem["consumo_wh_km"])
        self.assertGreater(com["tempo_volta_medio_s"], sem["tempo_volta_medio_s"])
        self.assertGreater(com["fracao_tempo"]["rolar"], 0.0)

    def test_teto_de_torque(self):
        r = self._rodar(RitmoPiloto(torque_maximo=80.0), voltas=2)
        self.assertLessEqual(r["torque_motor"].max(), 80.0 + 1e-6)
        self.assertLess(r["resumo"]["consumo_wh_km"], self.r["resumo"]["consumo_wh_km"])

    def test_para_no_soc_minimo(self):
        b = Bateria(soc_inicial=config.SOC_MINIMO + 0.01)
        sim = SimuladorEndurance(distancia_total=22_000, dinamica=self.din, pista=self.pista, mapa=self.mapa,
                                 tabela=self.tabela, bateria=b)
        r = sim.rodar()
        self.assertEqual(r["motivo"], "soc_minimo")
        self.assertLess(r["distancia"][-1], 22_000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
