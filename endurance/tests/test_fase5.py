"""Fase 5: validação contra o vídeo e calibração do ritmo de Endurance.

Rodar da raiz do repositório (~1 min):
    python -m unittest endurance.tests.test_fase5 -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import caminhos  # noqa: E402,F401
import parametros as config  # noqa: E402
from calibracao import (Contexto, TEMPO_VOLTA_GOPHER, contexto_cenario,  # noqa: E402
                        energia_seguindo_perfil, erro_perfil)
from piloto import RITMO_ENDURANCE, RitmoPiloto  # noqa: E402

# ritmo encontrado por calibracao.ajustar_ritmo_gopher (busca completa leva ~2 min)
RITMO_GOPHER = RitmoPiloto(fator_curva=0.95, torque_maximo=150.0, velocidade_maxima=70 / 3.6, tempo_rolagem=2.0)


class TestValidacaoVideo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = Contexto()
        cls.r = cls.ctx.rodar(RITMO_GOPHER, 3 * cls.ctx.pista.comprimento_volta)
        cls.ref = energia_seguindo_perfil(cls.ctx.din, cls.ctx.mapa, cls.ctx.tabela)

    def test_volta_e_perfil(self):
        self.assertAlmostEqual(self.r["resumo"]["tempo_volta_medio_s"], TEMPO_VOLTA_GOPHER, delta=1.5)
        self.assertLess(erro_perfil(self.r, self.ctx), 2.0)        # m/s

    def test_energia_bate_com_o_perfil_medido(self):
        """O piloto simulado gasta o mesmo que o carro seguindo a velocidade real (±15%)."""
        sim = self.r["resumo"]["consumo_wh_km"]
        self.assertAlmostEqual(sim, self.ref["consumo_wh_km"], delta=0.15 * self.ref["consumo_wh_km"])


class TestRitmoEndurance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = Contexto()
        cls.rec = cls.ctx.rodar(RitmoPiloto(**RITMO_ENDURANCE))["resumo"]

    def test_termina_com_folga(self):
        self.assertEqual(self.rec["status"], "completo")
        self.assertGreaterEqual(self.rec["soc_final"], config.SOC_MINIMO + 0.10)

    def test_ritmo_de_autocross_nao_termina(self):
        limite = self.ctx.rodar(RitmoPiloto())["resumo"]
        self.assertLess(limite["soc_final"], config.SOC_MINIMO)
        self.assertLess(limite["tempo_s"], self.rec["tempo_s"])
        self.assertLess(self.rec["tempo_s"] / limite["tempo_s"], 1.02)   # custa menos de 2% de tempo

    def test_cg_muda_pouco_e_massa_continua_viavel(self):
        base = self.rec["energia_wh"]
        for fr in (0.50, 0.60):
            r = contexto_cenario(fr).rodar(RitmoPiloto(**RITMO_ENDURANCE))["resumo"]
            self.assertAlmostEqual(r["energia_wh"], base, delta=0.05 * base)
        pesado = contexto_cenario(0.55, 310.0).rodar(RitmoPiloto(**RITMO_ENDURANCE))["resumo"]
        self.assertEqual(pesado["status"], "completo")
        self.assertGreater(pesado["soc_final"], config.SOC_MINIMO + 0.05)


if __name__ == "__main__":
    unittest.main(verbosity=2)
