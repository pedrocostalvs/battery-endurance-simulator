"""Fase 2: mapa de tração, conferido contra o código original e contra a Fase 1.

Rodar da raiz do repositório (leva ~40 s, roda a Simulation do Marco):
    python -m unittest endurance.tests.test_fase2 -v
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import caminhos  # noqa: E402,F401
import parametros as config  # noqa: E402
from motor import criar_componentes, eficiencia_eletrica  # noqa: E402
from tracao import (MapaTracao, SimulacaoEndurance, extrair_mapa,  # noqa: E402
                    rodar_aceleracao)


def _pico_pneu(pneu, fz):
    s = np.linspace(0.002, 0.6, 600)
    return max(pneu.Tire_forces(fz, x) for x in s)


class TestReproduzOriginal(unittest.TestCase):
    def test_75m_com_parametros_antigos(self):
        """Com os parâmetros do BatteryCapacity.py, a subclasse dá os mesmos 5,104 s e 28,92 m/s."""
        fonte = (caminhos.SRC / "BatteryCapacity.py").read_text(encoding="utf-8")
        trecho = fonte[:fonte.index("sim = Simulation(")]
        trecho = trecho.replace("from visualization.energy_plots import plot_sprint_energy", "")
        ns = {}
        exec(compile(trecho, "BatteryCapacity.py", "exec"), ns)
        sim = SimulacaoEndurance(
            motor=ns["motor"], vehicle=ns["vehicle"], transmission=ns["transmission"],
            battery=ns["battery"], tire=ns["tire"], pedal=ns["pedal"],
            tmax=60.0, dmax=75, p_max_dc=80e3)
        sim.simulate()
        self.assertAlmostEqual(sim.tempo[-1], 5.104, delta=0.002)
        self.assertAlmostEqual(sim.vehicle_velocity[-1], 28.92, delta=0.02)
        self.assertLess(sim.excesso_potencia_max, 100.0)   # < 0,13% de 80 kW


class TestMapa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapa = MapaTracao()
        cls.c = criar_componentes()

    def test_limites_do_motor(self):
        d = self.mapa.dados
        self.assertLessEqual(d["torque_motor"].max(), config.TORQUE_PICO + 0.5)
        self.assertLessEqual(d["rotacao_motor"].max(), 5500.0)
        self.assertLessEqual(d["potencia_dc"].max(), config.POTENCIA_MAX_DC * 1.001)

    def test_pneu_bate_com_fase1(self):
        """Força de tração entre 93% e 100% do pico do pneu com a carga dinâmica."""
        pneu, veic = self.c["pneu"], self.c["veiculo"]
        for v in (2, 8, 14, 20, 25):
            a = self.mapa.aceleracao(v)
            fz = veic.calculate_load_transfer(a, v)
            razao = self.mapa.forca(v) / (2 * _pico_pneu(pneu, fz))
            self.assertGreater(razao, 0.93, f"v={v}")
            self.assertLessEqual(razao, 1.0, f"v={v}")

    def test_eficiencia_da_simulation_bate_com_mapa_emrax(self):
        """A Simulation usa 0,90 fixo; nos pontos de aceleração plena o mapa dá ±3%."""
        for v in (5, 10, 15, 20, 24):
            rpm, T = self.mapa.rotacao_motor(v), self.mapa.torque_motor(v)
            self.assertAlmostEqual(eficiencia_eletrica(rpm, T), 0.90, delta=0.03)

    def test_sem_patinar(self):
        d = self.mapa.dados
        self.assertLess(d["escorregamento"][d["velocidade"] > 1.0].max(), 0.15)


class TestPartidaEmMovimento(unittest.TestCase):
    def test_partindo_de_40kmh_bate_com_mapa(self):
        mapa = MapaTracao()
        sim = rodar_aceleracao(velocidade_inicial=40 / 3.6, tmax=2.5)
        m40 = extrair_mapa(sim, t_inicial=0.5)
        for v in np.arange(16.0, m40["velocidade"].max(), 1.5):
            a40 = float(np.interp(v, m40["velocidade"], m40["aceleracao"]))
            self.assertAlmostEqual(a40, mapa.aceleracao(v), delta=0.01 * mapa.aceleracao(v))
        self.assertLess(sim.excesso_potencia_max, 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
