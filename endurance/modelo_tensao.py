import math

# =====================================================================
# MODELO DE TENSAO DA BATERIA (Shepherd/Tremblay com R(T) e Q(T))
# Procure por "# <-- TROCAR" para achar os parametros a substituir.
# =====================================================================

# ---------------------------------------------------------------------
# BLOCO 1: PACK
# ---------------------------------------------------------------------
NS = 144               # celulas em serie
NP = 5                 # celulas em paralelo
V_MIN_CEL = 2.5        # V, tensao de corte da celula                   # <-- TROCAR (ou 3.0 se o BMS cortar antes)
R_EXTRA_PACK = 0.0     # ohm, busbars + contatos + fusivel (pack todo)  # <-- TROCAR (medir ou calcular, cap. 17)

# ---------------------------------------------------------------------
# BLOCO 2: CURVA DE DESCARGA DA CELULA (datasheet). VALORES PLACEHOLDER
# ---------------------------------------------------------------------
Q_REF   = 3.0     # Ah  capacidade nominal em T_REF                      # <-- TROCAR
E_FULL  = 4.20    # V   tensao da celula cheia
E_EXP   = 4.05    # V   tensao no fim da zona exponencial                # <-- TROCAR
Q_EXP   = 0.20    # Ah  carga extraida no fim da zona exponencial        # <-- TROCAR
E_NOM   = 3.55    # V   tensao no fim da zona nominal (patamar)          # <-- TROCAR
Q_NOM   = 2.60    # Ah  carga extraida no fim da zona nominal            # <-- TROCAR
I_CURVA = 3.0     # A   corrente em que a curva do datasheet foi medida  # <-- TROCAR

# ---------------------------------------------------------------------
# BLOCO 3: TEMPERATURA (so R e Q variam com T)
# ---------------------------------------------------------------------
T_REF = 298.15    # K   temperatura em que os dados do BLOCO 2 e R_REF foram medidos
R_REF = 0.015     # ohm DCIR da celula nova em T_REF                     # <-- TROCAR
BETA  = 3000.0    # K   sensibilidade de R a T (Arrhenius)               # <-- TROCAR (ajustar com DCIR em 2 temperaturas)
DQDT  = 0.012     # Ah/K variacao da capacidade com T                    # <-- TROCAR (capacidade em 2 temperaturas)

# ---------------------------------------------------------------------
# BLOCO 4: TERMICO DA CELULA (modelo concentrado)
# ---------------------------------------------------------------------
M_CEL = 0.047     # kg  massa da celula                                  # <-- TROCAR (datasheet)
CP    = 900.0     # J/(kg K) calor especifico                            # <-- TROCAR
R_TH  = 10.0      # K/W resistencia termica celula -> ambiente           # <-- TROCAR (depende do arrefecimento)

# ---------------------------------------------------------------------
# BLOCO 5: ENVELHECIMENTO (1.0 = celula nova)
# ---------------------------------------------------------------------
SOH_R = 1.0       # multiplicador de resistencia (>1 com o uso)          # <-- TROCAR
SOH_Q = 1.0       # multiplicador de capacidade (<1 com o uso)           # <-- TROCAR

# =====================================================================
# CONSTANTES DERIVADAS (nao editar)
# =====================================================================
A_EXP = E_FULL - E_EXP
B_EXP = 3.0 / Q_EXP
_den = Q_REF * (Q_NOM + I_CURVA) / (Q_REF - Q_NOM) - I_CURVA
K_POL = (E_FULL - E_NOM + A_EXP * (math.exp(-B_EXP * Q_NOM) - 1.0)) / _den
E0 = E_FULL + (K_POL + R_REF) * I_CURVA - A_EXP


def R_T(T):
    return R_REF * SOH_R * math.exp(BETA * (1.0 / T - 1.0 / T_REF))


def Q_T(T):
    return max(0.1, (Q_REF + DQDT * (T - T_REF)) * SOH_Q)


def passo(it, T, P_pack, dt, T_amb):
    """
    it     : carga ja extraida por celula (Ah)
    T      : temperatura da celula (K)
    P_pack : potencia pedida ao pack (W), positiva na descarga
    dt     : passo (s)
    T_amb  : temperatura ambiente (K)
    """
    Q = Q_T(T)
    R = R_T(T)
    it_c = min(it, 0.999 * Q)
    f = Q / (Q - it_c)

    # V_cel = V0 - R_eff * i  (linear em i, entao a potencia constante tem solucao fechada)
    V0 = E0 - K_POL * f * it_c + A_EXP * math.exp(-B_EXP * it_c)
    R_eff = R + K_POL * f + R_EXTRA_PACK * NP / NS

    P_cel = P_pack / (NS * NP)
    disc = V0 * V0 - 4.0 * R_eff * P_cel
    limitado = disc < 0.0
    if limitado:                      # pack nao consegue entregar P_pack
        i = V0 / (2.0 * R_eff)        # corrente do ponto de potencia maxima
    else:
        i = (V0 - math.sqrt(disc)) / (2.0 * R_eff)
    V_cel = V0 - R_eff * i

    it_novo = it + i * dt / 3600.0
    q_gen = i * i * R
    T_novo = T + dt * (q_gen - (T - T_amb) / R_TH) / (M_CEL * CP)

    return {
        "V_pack": NS * V_cel,
        "V_cel": V_cel,
        "I_pack": i * NP,
        "I_cel": i,
        "C_rate": i / Q_REF,
        "P_entregue": NS * V_cel * NP * i,
        "SoC": 1.0 - it_novo / Q,
        "it": it_novo,
        "T": T_novo,
        "limitado": limitado,
        "fim": (V_cel <= V_MIN_CEL) or (it_novo >= 0.999 * Q),
    }


if __name__ == "__main__":
    for T_C, P in [(25, 80000), (5, 80000), (25, 30000)]:
        it, T, t = 0.0, T_C + 273.15, 0.0
        s = passo(it, T, P, 1.0, T_C + 273.15)
        print(f"\n--- T0={T_C} C, P={P/1000:.0f} kW  | inicio: Vpack={s['V_pack']:.0f} V, "
              f"I={s['I_pack']:.0f} A, {s['C_rate']:.1f}C")
        while True:
            s = passo(it, T, P, 1.0, T_C + 273.15)
            it, T, t = s["it"], s["T"], t + 1.0
            if s["fim"] or t > 3600:
                break
        print(f"fim em t={t:.0f} s | Vpack={s['V_pack']:.0f} V, I={s['I_pack']:.0f} A, "
              f"SoC={s['SoC']*100:.0f}%, T={s['T']-273.15:.0f} C, limitado={s['limitado']}")