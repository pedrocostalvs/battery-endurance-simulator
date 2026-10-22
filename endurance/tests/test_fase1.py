"""Fase 1: confere os componentes antes de montar o simulador.

Rodar da raiz do repositório:
    python -m unittest discover -s endurance/tests -v
"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import caminhos  # noqa: E402,F401
import parametros as config  # noqa: E402
import modelo_tensao as mt  # noqa: E402
from bateria import Bateria, tensao_celula, aplicar_parametros  # noqa: E402
from frenagem import Freio  # noqa: E402
from mapa_eficiencia_emrax228 import CONTORNOS, eficiencia_motor  # noqa: E402
from motor import criar_componentes, torque_maximo, potencia_dc  # noqa: E402

# Curvas digitalizadas do datasheet Murata VTC6, 23 °C (mAh, V)
CURVA_3A = [(0, 4.08), (300, 3.97), (600, 3.91), (900, 3.84), (1200, 3.76), (1500, 3.68),
            (1800, 3.60), (2100, 3.52), (2400, 3.41), (2550, 3.30), (2700, 3.12),
            (2850, 2.88), (2950, 2.68), (3010, 2.52)]
CURVA_10A = [(0, 3.95), (300, 3.86), (600, 3.79), (900, 3.71), (1200, 3.62), (1500, 3.54),
             (1800, 3.47), (2100, 3.38), (2400, 3.27), (2600, 3.15), (2800, 2.92), (2950, 2.60)]


class TestFreio(unittest.TestCase):
    def setUp(self):
        self.freio = Freio()

    def test_pressao_e_forca_comandada_a_mao(self):
        # 500 N × 4 / (π·0,02²/4) = 6,366 MPa
        pressao, forca = self.freio.forca_comandada(1.0)
        self.assertAlmostEqual(pressao / 1e6, 6.366, places=2)
        # aperto = p·π·0,032²/4 = 5120 N; torque/disco = 2·0,35·5120·0,075 = 268,8 N·m
        # força = 4·268,8/0,26 = 4135 N
        self.assertAlmostEqual(forca, 4135, delta=2)

    def test_forca_proporcional_ao_pedal(self):
        _, cheia = self.freio.forca_comandada(1.0)
        _, metade = self.freio.forca_comandada(0.5)
        self.assertAlmostEqual(metade, cheia / 2, places=6)

    def test_limite_aderencia_a_mao(self):
        # sem downforce: traseira = 1,3·1294,9/(1 - 0,6 + 1,3·0,28/1,5) = 2619 N
        limite, eixo = self.freio.limite_aderencia()
        self.assertEqual(eixo, "traseira")
        self.assertAlmostEqual(limite, 2619, delta=3)

    def test_distancia_80_kmh_a_mao(self):
        # sem aero e sem rolamento: d = v²/(2a), a = 2619/240 = 10,91 m/s² -> 22,6 m
        v = 80 / 3.6
        a = self.freio.aplicar(1.0).forca_n / config.VEICULO["mass"]
        analitica = v * v / (2 * a)
        d, dt = 0.0, 1e-4
        while v > 0:
            d += v * dt
            v -= a * dt
        self.assertAlmostEqual(analitica, 22.6, delta=0.1)
        self.assertAlmostEqual(d, analitica, delta=0.01)

    def test_curva_reduz_frenagem(self):
        reta, _ = self.freio.limite_aderencia()
        curva, _ = self.freio.limite_aderencia(forca_lateral=1500)
        self.assertLess(curva, reta)


class TestBateria(unittest.TestCase):
    def test_reproduz_datasheet(self):
        for curva, corrente in ((CURVA_3A, 3.0), (CURVA_10A, 10.0)):
            erros = [abs(tensao_celula(q / 1000, corrente) - v) for q, v in curva]
            self.assertLess(max(erros), 0.06, f"{corrente} A: erro máx {max(erros):.3f} V")

    def test_identico_ao_original_quando_equivalente(self):
        # Com KR = K_POL, sem busbars e capacidade útil = Q, tensão, corrente e carga
        # devem sair iguais ao modelo do Pedro. A temperatura difere só pelo calor da
        # polarização (KR·f·i²), que o adaptador inclui (proposta 1.8).
        p = dict(config.BATERIA, KR=config.BATERIA["K_POL"], R_EXTRA_PACK=0.0)
        b = Bateria(capacidade_util=p["Q_REF"], parametros=p)
        it, T = 0.0, config.TEMPERATURA_AMBIENTE
        mcp = p["M_CEL"] * p["CP"]
        for _ in range(600):
            b.it, b.T = it, T
            orig = mt.passo(it, T, 20000.0, 1.0, config.TEMPERATURA_AMBIENTE)
            novo = b.passo(20000.0, 1.0)
            self.assertAlmostEqual(novo["V_pack"], orig["V_pack"], places=9)
            self.assertAlmostEqual(novo["I_pack"], orig["I_pack"], places=9)
            self.assertAlmostEqual(b.it, orig["it"], places=12)
            Q = p["Q_REF"]
            f = Q / (Q - min(it, 0.999 * Q))
            calor_extra = p["KR"] * f * orig["I_cel"] ** 2
            self.assertAlmostEqual(novo["T"] - orig["T"], calor_extra / mcp, places=9)
            it, T = orig["it"], orig["T"]
        aplicar_parametros()

    def test_pack_142s5p(self):
        b = Bateria()
        s = b.passo(0.0, 1.0)
        self.assertEqual(mt.NS, 142)
        self.assertLess(s["V_pack"], 600.0)
        self.assertGreater(s["V_pack"], 142 * 3.9)

    def test_soc_cai_e_energia_8kw(self):
        b = Bateria()
        soc_anterior = b.soc
        while True:
            s = b.passo(8000.0, 1.0)
            self.assertLessEqual(s["SoC"], soc_anterior)
            soc_anterior = s["SoC"]
            if s["fim"]:
                break
        self.assertAlmostEqual(b.energia_wh / 1000, 7.7, delta=0.15)


class TestMotor(unittest.TestCase):
    def test_componentes_do_codigo_existente(self):
        c = criar_componentes()
        self.assertAlmostEqual(torque_maximo(c["motor"]), 240.0, places=6)
        self.assertEqual(c["motor"].kf, 0.0)
        # Kt por Arms deve bater com o datasheet (1,1 N·m/Arms)
        kt_rms = 1.5 * c["motor"].p * c["motor"].lambda_m * math.sqrt(2)
        self.assertAlmostEqual(kt_rms, 1.1, delta=0.06)

    def test_mapa_reproduz_contornos(self):
        for nivel, pontos in CONTORNOS.items():
            for rpm, torque in pontos:
                if rpm >= 5000 or nivel == 86:
                    continue
                self.assertAlmostEqual(eficiencia_motor(rpm, torque), nivel, delta=1.0)

    def test_cruzeiro_ineficiente_e_aceleracao_eficiente(self):
        self.assertLess(eficiencia_motor(2550, 5.5), 70.0)
        self.assertGreater(eficiencia_motor(2500, 100), 96.0)

    def test_potencia_dc_maior_que_mecanica(self):
        p_mec = 100 * 2500 * 2 * math.pi / 60
        self.assertGreater(potencia_dc(2500, 100), p_mec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
