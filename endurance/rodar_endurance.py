"""Roda o Endurance de 22 km com o ritmo recomendado e salva gráficos e resumo.

No VS Code: abra este arquivo e clique em Run Python File (▶).
Pelo terminal, da raiz do repositório:
    python endurance/rodar_endurance.py
"""
import sys

import numpy as np

import caminhos  # noqa: F401
from calibracao import descrever
from piloto import RITMO_ENDURANCE, RitmoPiloto
from resultados import PASTA_GRAFICOS, graficos, texto_resumo
from simulador import CAMPOS, SimuladorEndurance


def main(mostrar=False):
    ritmo = RitmoPiloto(**RITMO_ENDURANCE)
    sim = SimuladorEndurance(ritmo=ritmo)
    print(f"Simulando 22 km com ritmo: {descrever(ritmo)}")
    r = sim.rodar(mostrar_progresso=True)
    r["massa_equivalente"] = sim.din.m_eq

    resumo = texto_resumo(r["resumo"], descrever(ritmo))
    print("\n" + resumo)

    PASTA_GRAFICOS.mkdir(parents=True, exist_ok=True)
    (PASTA_GRAFICOS.parent / "resumo_endurance.txt").write_text(resumo + "\n", encoding="utf-8")
    np.savez_compressed(PASTA_GRAFICOS.parent / "endurance_resultado.npz", **{k: r[k] for k in CAMPOS})
    arquivos = graficos(r, sim.pista, mostrar=mostrar)
    print(f"\n{len(arquivos)} gráficos em {PASTA_GRAFICOS}")
    return r


if __name__ == "__main__":
    main(mostrar="--mostrar" in sys.argv)
