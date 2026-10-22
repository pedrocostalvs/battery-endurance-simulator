"""Parâmetros do simulador de Endurance, todos num lugar só.

Os dicionários usam os mesmos nomes de chave que as classes do código
existente (``Vehicle``, ``Motor``, ``Transmission``, ``BrakeSystem``), para
poderem ser passados direto a elas.

Marcação de origem:
    CONHECIDO  valor da equipe ou de datasheet
    HIPÓTESE   valor provisório, trocar quando houver dado real
"""
import math

G = 9.81

# ---------------------------------------------------------------------------
# Veículo
# ---------------------------------------------------------------------------
FRACAO_PESO_TRASEIRA = 0.55     # HIPÓTESE: 45/55 até pesar os eixos
ENTRE_EIXOS = 1.5               # CONHECIDO [m]

VEICULO = {
    "mass": 240.0,              # CONHECIDO [kg]
    "wheel_radius": 0.26,       # CONHECIDO [m]
    "wheel_mass": 5.0,          # CONHECIDO [kg] por roda
    "drag_coeff": 0.7789,       # CONHECIDO
    "frontal_area": 0.68,       # CONHECIDO [m²]
    "rolling_resistance": 0.015,  # CONHECIDO
    "road_grade": 0.0,          # pista plana
    "L": ENTRE_EIXOS,
    "h": 0.28,                  # CONHECIDO, altura do CG [m]
    # distância do eixo DIANTEIRO ao CG [m] (no Vehicle: Fz_tras = m·g·dist_cg/L)
    "dist_cg": FRACAO_PESO_TRASEIRA * ENTRE_EIXOS,
}

AERO = {                        # mantido como está no código atual
    "has_wing": True,
    "lift_coeff_front": 1.0,
    "area_front": 0.35,
    "lift_coeff_rear": 1.0,
    "area_rear": 0.35,
}

# ---------------------------------------------------------------------------
# Pneu
# ---------------------------------------------------------------------------
MU_PNEU = 1.3                   # CONHECIDO (confirmado pela equipe)

# ---------------------------------------------------------------------------
# Transmissão
# ---------------------------------------------------------------------------
TRANSMISSAO = {
    "final_drive_ratio": 5.0,   # CONHECIDO
    "Z_pinhao": None,
    "Z_coroa": None,
    "chain_efficiency": 0.98,   # CONHECIDO
    "diff_efficiency": 0.97,    # CONHECIDO
    "axle_inertia": 0.0015,
    "diff_inertia": 0.012,
    "sprocket_inertia": 0.0002,
    "coroa_inertia": 0.0015,
    "lsd_bias_ratio": 3.0,
}

# ---------------------------------------------------------------------------
# Motor: EMRAX 228 HV (datasheet Technical Data v4.5)
# ---------------------------------------------------------------------------
POLOS_PARES = 10
FLUXO_IMA = 0.0542              # CONHECIDO [Wb]
TORQUE_PICO = 240.0             # CONHECIDO [N·m]
KT_PICO = 1.5 * POLOS_PARES * FLUXO_IMA        # [N·m/A de pico]

MOTOR = {
    "rs": 0.018,                # CONHECIDO, resistência de fase a 25 °C [ohm]
    "ld": 177e-6,               # CONHECIDO [H]
    "lq": 183e-6,               # CONHECIDO [H]
    "jm": 0.0421,               # CONHECIDO, inércia do rotor [kg·m²]
    "kf": 0.0,                  # zerado: as perdas em vazio já estão no mapa de eficiência
    "lambda_m": FLUXO_IMA,
    "p": POLOS_PARES,
    "valor_mu": 0.95,
    "speed_ref": 5500 * 2 * math.pi / 60,      # CONHECIDO, 5500 rpm [rad/s]
    "max_current": TORQUE_PICO / KT_PICO,      # amplitude de pico que dá 240 N·m [A]
}

EFICIENCIA_INVERSOR = 0.95      # HIPÓTESE
POTENCIA_MAX_DC = 80e3          # regulamento [W]
ARREFECIMENTO_MOTOR = "AC/LC"   # HIPÓTESE conservadora: 28 a 42 kW contínuos
POTENCIA_CONTINUA_MOTOR = (28e3, 42e3)

# ---------------------------------------------------------------------------
# Freio (mesmas chaves do BrakeSystem; valores do BatteryCapacity.py)
# ---------------------------------------------------------------------------
_PESO = VEICULO["mass"] * G
FREIO = {
    "RedP": 4,                  # CONHECIDO, redução do pedal
    "a": 0.8,                   # não usado pelo simulador novo
    "psi": FRACAO_PESO_TRASEIRA,
    "μl": 0.45,                 # não usado (ver propostas de alteração)
    "pi": math.pi,
    "HCG": VEICULO["h"],
    "μ": MU_PNEU,
    "FzF": _PESO * (1 - FRACAO_PESO_TRASEIRA),
    "FzR": _PESO * FRACAO_PESO_TRASEIRA,
    "Rdp": VEICULO["wheel_radius"],
    "Dcm": 0.02,                # CONHECIDO, cilindro mestre [m]
    "Dwc": 0.032,               # CONHECIDO, cilindro de roda [m]
    "Npast": 2,                 # CONHECIDO, pastilhas por disco
    "atrito_coeficiente": 0.35,  # CONHECIDO, atrito pastilha/disco
    "red": 0.075,               # CONHECIDO, raio efetivo do disco [m]
    "Mt": VEICULO["mass"],
    "m_wheel": VEICULO["wheel_mass"],
    "m_tire": 10,
    "L": ENTRE_EIXOS,
    "c_rr": VEICULO["rolling_resistance"],
}
FORCA_PEDAL_MAX = 500.0         # CONHECIDO [N]
NUMERO_DISCOS = 4               # HIPÓTESE: um por roda
BALANCO_FREIO_DIANTEIRO = 0.60  # HIPÓTESE: fração da força de frenagem na dianteira

# ---------------------------------------------------------------------------
# Bateria: 142s5p com Murata US18650VTC6
# Parâmetros ajustados às curvas de 3 A e 10 A do datasheet (ver
# claude/propostas-de-alteracao.md, item 1.4). Aplicados sobre modelo_tensao.py.
# ---------------------------------------------------------------------------
BATERIA = {
    "NS": 142,
    "NP": 5,
    "V_MIN_CEL": 2.5,
    "R_EXTRA_PACK": 0.0,        # HIPÓTESE: busbars ainda não medidos
    "E0": 3.7039,
    "K_POL": 0.04149,
    "KR": 0.0,                  # termo de polarização sobre a corrente (zerado no ajuste)
    "A_EXP": 0.4206,
    "B_EXP": 0.73,
    "Q_REF": 3.361,             # assíntota do modelo [Ah]
    "R_REF": 0.0167,
    "T_REF": 296.15,
    "BETA": 1500.0,
    "DQDT": 0.0,
    "M_CEL": 0.0466,
    "CP": 900.0,
    "R_TH": 50.0,               # HIPÓTESE: célula sozinha em ar parado (datasheet)
    "SOH_R": 1.0,
    "SOH_Q": 1.0,
}
CAPACIDADE_UTIL_CEL = 3.0       # CONHECIDO, Ah até 2,5 V a 1C (usada no SoC)
SOC_MINIMO = 0.20               # HIPÓTESE
TEMPERATURA_AMBIENTE = 298.15   # [K]
