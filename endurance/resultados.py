"""Fase 6: gráficos e resumo do Endurance.

Gera PNGs em ``resultados/graficos`` e um resumo em texto. Cada gráfico tem
um único eixo (sem eixo duplo): grandezas de escalas diferentes ficam em
painéis separados.
"""
from pathlib import Path

import matplotlib
import numpy as np

import caminhos  # noqa: F401
import parametros as config

PASTA_GRAFICOS = Path(__file__).resolve().parent / "resultados" / "graficos"

# Paleta de referência (tema claro): superfície, textos, grade e séries
SUPERFICIE = "#fcfcfb"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRADE = "#e4e3df"
NEUTRO = "#8f8e88"
SERIE_1 = "#2a78d6"   # azul
SERIE_2 = "#eb6834"   # laranja
SERIE_3 = "#1baf7a"   # verde-água


def _estilo(plt):
    plt.rcParams.update({
        "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
        "axes.edgecolor": GRADE, "axes.labelcolor": TEXTO_2, "axes.titlecolor": TEXTO,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.labelsize": 9,
        "xtick.color": TEXTO_2, "ytick.color": TEXTO_2, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "axes.grid": True, "grid.color": GRADE, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "legend.fontsize": 8, "legend.labelcolor": TEXTO_2,
        "lines.linewidth": 1.6, "font.size": 9,
    })


def _volta_do_meio(r):
    L = r["comprimento_volta"]
    n = int(r["distancia"][-1] // L)
    k = max(n // 2, 1)
    m = (r["distancia"] >= (k - 1) * L) & (r["distancia"] < k * L)
    return m, (k - 1) * L, k


def graficos(r, pista=None, pasta=PASTA_GRAFICOS, mostrar=False):
    if not mostrar:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _estilo(plt)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    km = r["distancia"] / 1000
    t_min = r["tempo"] / 60
    arquivos = []

    def salvar(fig, nome):
        fig.tight_layout()
        caminho = pasta / nome
        fig.savefig(caminho, dpi=150)
        arquivos.append(caminho)
        if not mostrar:
            plt.close(fig)

    # 1. Velocidade numa volta, com o limite das curvas
    m, inicio, k = _volta_do_meio(r)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    s_volta = r["distancia"][m] - inicio
    if pista is not None:
        lim = np.array([pista.limite(x) for x in s_volta]) * 3.6
        lim = np.where(np.isfinite(lim), lim, np.nan)
        ax.plot(s_volta, lim, color=GRADE, lw=5, solid_capstyle="butt", label="Limite da curva", zorder=1)
    ax.plot(s_volta, r["velocidade"][m] * 3.6, color=SERIE_1, label="Velocidade", zorder=2)
    ax.set(title=f"Velocidade ao longo da volta {k}", xlabel="Distância na volta [m]", ylabel="km/h")
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", ncols=2)
    salvar(fig, "01_velocidade_volta.png")

    # 2. SoC
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.axhline(config.SOC_MINIMO * 100, color=NEUTRO, lw=1.0, ls="--")
    ax.text(km[-1], config.SOC_MINIMO * 100 + 1.5, "SoC mínimo", color=TEXTO_2, ha="right", fontsize=8)
    ax.plot(km, r["soc"] * 100, color=SERIE_1)
    ax.set(title="Estado de carga da bateria", xlabel="Distância [km]", ylabel="SoC [%]", ylim=(0, 102))
    salvar(fig, "02_soc.png")

    # 3. Painel elétrico: tensão, corrente por célula, temperatura da célula
    fig, eixos = plt.subplots(3, 1, figsize=(9, 7.2), sharex=True)
    eixos[0].plot(t_min, r["tensao_pack"], color=SERIE_1)
    eixos[0].axhline(config.BATERIA["NS"] * config.BATERIA["V_MIN_CEL"], color=NEUTRO, lw=1.0, ls="--")
    eixos[0].set(title="Tensão do pack", ylabel="V")
    eixos[1].plot(t_min, r["corrente_celula"], color=SERIE_1, lw=0.8)
    eixos[1].set(title="Corrente por célula", ylabel="A")
    eixos[2].plot(t_min, r["temperatura_celula"], color=SERIE_1)
    eixos[2].set(title="Temperatura da célula (modelo concentrado)", ylabel="°C", xlabel="Tempo [min]")
    salvar(fig, "03_eletrico.png")

    # 4. Potência DC e torque numa volta (painéis separados)
    t_volta = r["tempo"][m] - r["tempo"][m][0]
    fig, eixos = plt.subplots(2, 1, figsize=(9, 5.2), sharex=True)
    eixos[0].plot(t_volta, r["potencia_dc"][m] / 1000, color=SERIE_1)
    eixos[0].axhline(config.POTENCIA_MAX_DC / 1000, color=NEUTRO, lw=1.0, ls="--")
    eixos[0].set(title=f"Potência pedida à bateria na volta {k}", ylabel="kW")
    eixos[1].plot(t_volta, r["torque_motor"][m], color=SERIE_1)
    eixos[1].set(title="Torque do motor", ylabel="N·m", xlabel="Tempo na volta [s]")
    salvar(fig, "04_potencia_torque_volta.png")

    # 5. Energia acumulada
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(km, r["energia_wh"] / 1000, color=SERIE_1)
    ax.set(title="Energia tirada da bateria", xlabel="Distância [km]", ylabel="kWh")
    ax.annotate(f"{r['energia_wh'][-1] / 1000:.2f} kWh", (km[-1], r["energia_wh"][-1] / 1000),
                xytext=(-8, 6), textcoords="offset points", ha="right", va="bottom", color=TEXTO, fontsize=9)
    salvar(fig, "05_energia.png")

    # 6. Para onde vai a energia
    res = r["resumo"]
    din_m_eq = r.get("massa_equivalente", config.VEICULO["mass"])
    cinetica = 0.5 * din_m_eq * r["velocidade"][-1] ** 2 / 3600
    rodas = res["energia_freio_wh"] + res["energia_resistencias_wh"] + res["energia_vazio_motor_wh"] + cinetica
    itens = [
        ("Freio (sem regeneração)", res["energia_freio_wh"]),
        ("Arrasto e rolamento", res["energia_resistencias_wh"]),
        ("Motor, inversor, transmissão\ne escorregamento", res["energia_wh"] - rodas),
        ("Perdas internas da bateria", res["perdas_bateria_wh"]),
        ("Motor girando sem torque", res["energia_vazio_motor_wh"]),
    ]
    itens.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(9, 3.4))
    nomes, valores = zip(*itens)
    barras = ax.barh(nomes, [v / 1000 for v in valores], color=SERIE_1, height=0.6)
    total = res["energia_wh"] + res["perdas_bateria_wh"]
    for b, v in zip(barras, valores):
        ax.text(b.get_width() + total / 1000 * 0.01, b.get_y() + b.get_height() / 2,
                f"{v / 1000:.2f} kWh ({v / total * 100:.0f}%)", va="center", color=TEXTO, fontsize=8)
    ax.set(title="Para onde vai a energia da bateria", xlabel="kWh")
    ax.grid(visible=False)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(valores) / 1000 * 1.35)
    salvar(fig, "06_destino_energia.png")

    if mostrar:
        plt.show(block=False)
    return arquivos


def grafico_varredura(linhas, recomendado=None, pasta=PASTA_GRAFICOS):
    """Tempo total x energia de cada ritmo testado na calibração."""
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _estilo(plt)
    from calibracao import fronteira
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    xs = [res["tempo_s"] / 60 for _, res in linhas]
    ys = [res["energia_wh"] / 1000 for _, res in linhas]
    ax.scatter(xs, ys, s=22, color=NEUTRO, alpha=0.6, label="Ritmos testados", zorder=2)
    f = fronteira(linhas)
    ax.plot([res["tempo_s"] / 60 for _, res in f], [res["energia_wh"] / 1000 for _, res in f],
            color=SERIE_1, marker="o", ms=4, label="Melhores combinações", zorder=3)
    utilizavel = config.BATERIA["NS"] * config.BATERIA["NP"] * 3.6 * config.CAPACIDADE_UTIL_CEL / 1000 \
        * (1 - config.SOC_MINIMO)
    ax.axhline(utilizavel, color=NEUTRO, lw=1.0, ls="--")
    ax.text(max(xs), utilizavel + 0.08, "Energia até o SoC mínimo", color=TEXTO_2, ha="right", fontsize=8)
    if recomendado is not None:
        res = recomendado[1]
        ax.scatter([res["tempo_s"] / 60], [res["energia_wh"] / 1000], s=70, color=SERIE_2,
                   edgecolor=SUPERFICIE, linewidth=2, zorder=4, label="Recomendado")
    ax.set(title="Ritmos nos 22 km: tempo x energia", xlabel="Tempo total [min]", ylabel="Energia [kWh]")
    ax.legend(loc="upper right")
    caminho = pasta / "07_ritmos_tempo_energia.png"
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    return caminho


def texto_resumo(res, ritmo_descricao=""):
    f = res["fracao_tempo"]
    linhas = [
        "RESUMO DO ENDURANCE (simulação, não validada experimentalmente)",
        f"Ritmo: {ritmo_descricao}" if ritmo_descricao else "",
        f"Status: {res['status']} ({res['motivo']})",
        f"Distância: {res['distancia_m'] / 1000:.2f} km em {res['tempo_s'] / 60:.1f} min ({res['voltas_completas']} voltas)",
        f"Volta média: {res['tempo_volta_medio_s']:.1f} s | velocidade média {res['velocidade_media_kmh']:.1f} km/h, "
        f"máxima {res['velocidade_max_kmh']:.1f} km/h",
        f"Energia: {res['energia_wh'] / 1000:.2f} kWh ({res['consumo_wh_km']:.0f} Wh/km) | SoC final {res['soc_final'] * 100:.1f}%",
        f"Potência: média {res['potencia_media_kw']:.1f} kW, máxima {res['potencia_max_kw']:.1f} kW, "
        f"maior média de 60 s {res['potencia_media_60s_max_kw']:.1f} kW",
        f"Pack: {res['tensao_min_v']:.0f} a {res['tensao_max_v']:.0f} V | célula até {res['corrente_celula_max_a']:.1f} A "
        f"e {res['temperatura_celula_max_c']:.1f} °C",
        f"Tempo em cada modo: acelerando {f['acelerar'] * 100:.0f}%, mantendo {f['manter'] * 100:.0f}%, "
        f"rolando {f['rolar'] * 100:.0f}%, freando {f['frear'] * 100:.0f}%",
        f"Acima da rotação base do motor: {res['fracao_tempo_acima_rotacao_base'] * 100:.1f}% do tempo",
        "",
        "Verificações:",
        f"  Potência contínua do motor (hipótese AC/LC, 28 kW): maior média de 60 s = "
        f"{res['potencia_media_60s_max_kw']:.1f} kW -> {'ok' if res['potencia_media_60s_max_kw'] < 28 else 'ACIMA'}",
        f"  Corrente da célula (30 A com corte térmico): {res['corrente_celula_max_a']:.1f} A -> "
        f"{'ok' if res['corrente_celula_max_a'] <= 30 else 'pico acima de 30 A'}",
        f"  Temperatura da célula (corte em 80 °C no datasheet): {res['temperatura_celula_max_c']:.1f} °C -> "
        f"{'ok' if res['temperatura_celula_max_c'] < 60 else 'atenção'}",
        f"  SoC final acima de {config.SOC_MINIMO * 100:.0f}%: {'ok' if res['soc_final'] > config.SOC_MINIMO else 'NÃO'}",
    ]
    return "\n".join(x for x in linhas if x is not None)
