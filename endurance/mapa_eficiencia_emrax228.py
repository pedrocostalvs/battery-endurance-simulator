"""Mapa de eficiência do motor EMRAX 228 (HV, arrefecimento combinado).

Contornos digitalizados à mão do gráfico "Efficiency map" do manual da EMRAX.
Segundo o manual, as versões MV e LV têm os mesmos gráficos (só mudam tensão e
corrente), então o mapa vale para elas também.

Como funciona:
- Dentro do mapa: acha entre quais contornos o ponto está e interpola pela
  distância até cada um (86, 90, 94, 95 e 96%).
- Abaixo do contorno de 86% (torque baixo): o mapa não informa nada. Usa um
  modelo de perdas = perdas em vazio (curva "free run losses" do manual)
  + perdas no cobre 3·R·(T/Kt)², limitado a 86%.

Atenção: as perdas em vazio já estão dentro desta eficiência. Não somar de
novo o atrito viscoso (kf) do motor quando usar este mapa.
"""
import numpy as np
from matplotlib.path import Path

R_FASE = 0.018      # ohm, resistência de fase a 25 °C (HV)
KT = 1.1            # N.m/Arms (HV)
RPM_MAX = 5000.0
TORQUE_MAX = 250.0

# Contornos (rpm, N.m), em sentido horário
CONTORNOS = {
    86: [(300, 40), (260, 60), (260, 110), (300, 150), (400, 180), (600, 215), (800, 235),
         (1050, 243), (3000, 243), (5000, 243), (5000, 107), (4500, 62), (4000, 42),
         (3640, 24), (3000, 18), (2000, 18), (1000, 21), (500, 30)],
    90: [(750, 60), (640, 80), (620, 100), (650, 130), (800, 175), (1000, 215), (1200, 230),
         (1500, 232), (3000, 232), (5000, 231), (5000, 124), (4500, 71), (4000, 50),
         (3500, 45), (3000, 42), (2000, 42), (1500, 43), (1000, 50)],
    94: [(970, 75), (950, 90), (960, 130), (1050, 160), (1300, 180), (1700, 195), (2000, 201),
         (3000, 201), (4000, 200), (5000, 199), (5000, 150), (4500, 93), (4000, 70),
         (3500, 61), (3000, 58), (2000, 57), (1500, 58), (1100, 64)],
    95: [(1200, 125), (1150, 145), (1300, 158), (1600, 166), (2000, 170), (2500, 170),
         (3000, 168), (3500, 163), (4000, 152), (4300, 130), (4150, 112), (3800, 95),
         (3400, 83), (3000, 75), (2500, 67), (2050, 64), (1700, 75), (1400, 95)],
    96: [(1500, 108), (1450, 118), (1600, 126), (2000, 129), (2500, 128), (3000, 125),
         (3400, 120), (3560, 108), (3450, 98), (3000, 88), (2500, 80), (2200, 76),
         (1900, 79), (1650, 92)],
}
NIVEIS = [86, 90, 94, 95, 96]

# Perdas em vazio lidas do manual (rpm, W)
_RPM_VAZIO = np.array([0, 1000, 2000, 3000, 4000, 5000])
_P_VAZIO = np.array([0, 200, 520, 950, 1700, 2800])

_ESCALA = np.array([RPM_MAX, TORQUE_MAX])
_POL = {n: np.array(CONTORNOS[n], float) / _ESCALA for n in NIVEIS}
_PATH = {n: Path(np.vstack([_POL[n], _POL[n][:1]])) for n in NIVEIS}
_w = lambda rpm: np.asarray(rpm, float) * 2 * np.pi / 60
_K_VAZIO = np.linalg.lstsq(np.c_[_w(_RPM_VAZIO), _w(_RPM_VAZIO) ** 2], _P_VAZIO, rcond=None)[0]


def perdas_vazio_w(rpm):
    """Perdas mecânicas e no ferro com o motor girando sem torque [W]."""
    w = _w(rpm)
    return _K_VAZIO[0] * w + _K_VAZIO[1] * w ** 2


def _distancia(p, nivel):
    v = np.vstack([_POL[nivel], _POL[nivel][:1]])
    d = np.inf
    for a, b in zip(v[:-1], v[1:]):
        if a[0] >= 0.999 and b[0] >= 0.999:   # borda do gráfico, não é contorno
            continue
        ab = b - a
        t = np.clip(np.dot(p - a, ab) / np.dot(ab, ab), 0.0, 1.0)
        d = min(d, np.linalg.norm(p - (a + t * ab)))
    return d


def _eficiencia_fisica(rpm, torque):
    p_mec = torque * _w(rpm)
    if p_mec <= 0.0:
        return 0.0
    perdas = perdas_vazio_w(rpm) + 3 * R_FASE * (torque / KT) ** 2
    return 100.0 * p_mec / (p_mec + perdas)


def eficiencia_motor(rpm, torque):
    """Eficiência do motor [%] para rotação [rpm] e torque [N.m] (tração)."""
    rpm = min(max(float(rpm), 0.0), RPM_MAX - 10.0)
    torque = min(max(float(torque), 0.0), TORQUE_MAX)
    if rpm <= 0.0 or torque <= 0.0:
        return 0.0
    p = np.array([rpm, torque]) / _ESCALA
    dentro = [n for n in NIVEIS if _PATH[n].contains_point(p)]
    if not dentro:
        return min(_eficiencia_fisica(rpm, torque), 86.0)
    nivel = max(dentro)
    if nivel == 96:
        return min(96.0 + 0.5 * _distancia(p, 96) / 0.04, 96.5)
    proximo = NIVEIS[NIVEIS.index(nivel) + 1]
    d_fora, d_dentro = _distancia(p, nivel), _distancia(p, proximo)
    return nivel + (proximo - nivel) * d_fora / (d_fora + d_dentro)


if __name__ == "__main__":
    torques = [5, 10, 20, 40, 60, 80, 100, 125, 150, 200, 240]
    rotacoes = [500, 1000, 2000, 2500, 3000, 4000, 5000]
    print("N.m\\rpm " + "".join(f"{n:>7}" for n in rotacoes))
    for t in torques:
        print(f"{t:>7} " + "".join(f"{eficiencia_motor(n, t):7.1f}" for n in rotacoes))
