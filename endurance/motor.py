"""Motor e componentes do código existente, montados com os parâmetros novos.

``criar_componentes`` instancia as classes do Marco (Motor, Vehicle,
Transmission, Tire) com os valores de ``config``, sem editar os arquivos
delas. A eficiência elétrica usa o mapa digitalizado do EMRAX 228 vezes a
eficiência do inversor.
"""
import caminhos  # noqa: F401
import parametros as config
from mapa_eficiencia_emrax228 import eficiencia_motor, perdas_vazio_w
from Models import Motor, Tire, Transmission, Vehicle


def criar_componentes():
    motor = Motor.Motor(**config.MOTOR)
    veiculo = Vehicle.Vehicle(**config.VEICULO, **config.AERO)
    transmissao = Transmission.Transmission(**config.TRANSMISSAO)
    pneu = Tire.Tire(
        pacejka_params=dict(Tire.Tire.HOOSIER_FSAE_LONG),
        tire_friction_coef=config.FATOR_MU_PACEJKA,   # fator, dá μ efetivo de 1,3 em Fz0
        Fz0=654.0,
        camber=0.0,
    )
    return {"motor": motor, "veiculo": veiculo, "transmissao": transmissao, "pneu": pneu}


def torque_maximo(motor):
    """Torque máximo do motor [N·m] com a corrente limite configurada."""
    return 1.5 * motor.p * motor.lambda_m * motor.max_current


def eficiencia_eletrica(rpm, torque):
    """Eficiência da bateria até o eixo do motor (motor × inversor), de 0 a 1."""
    return eficiencia_motor(rpm, torque) / 100.0 * config.EFICIENCIA_INVERSOR


def potencia_dc(rpm, torque):
    """Potência pedida à bateria [W] para entregar ``torque`` a ``rpm``."""
    import math
    p_mec = torque * rpm * 2 * math.pi / 60
    if p_mec <= 0.0:
        return 0.0
    return p_mec / eficiencia_eletrica(rpm, torque)


class TabelaEficiencia:
    """Perdas do motor pré-calculadas numa grade, com interpolação bilinear.

    ``eficiencia_motor`` (contornos) leva ~0,1 ms por chamada; no loop de
    22 km isso pesa. A grade guarda as PERDAS [W] e não a eficiência: com
    torque zero a eficiência vai a zero, mas as perdas valem exatamente as
    perdas em vazio, então a interpolação fica suave em cruzeiro.

        perdas = P_mec · (1/η - 1)        (P_vazio quando o torque é zero)
        P_dc   = (P_mec + perdas) / η_inversor
    """

    def __init__(self, passo_rpm=50.0, passo_torque=2.0, arquivo=None):
        import math
        from pathlib import Path
        import numpy as np
        arquivo = Path(arquivo) if arquivo else Path(__file__).resolve().parent / "resultados" / "tabela_perdas_motor.npz"
        self.rpm = np.arange(0.0, 5500.0 + passo_rpm, passo_rpm)
        self.torque = np.arange(0.0, config.TORQUE_PICO + passo_torque, passo_torque)
        self._dn = self.rpm[1] - self.rpm[0]
        self._dt = self.torque[1] - self.torque[0]
        if arquivo.exists():
            dados = np.load(arquivo)
            if dados["perdas"].shape == (len(self.rpm), len(self.torque)):
                self.perdas = dados["perdas"]
                return
        perdas = np.zeros((len(self.rpm), len(self.torque)))
        for a, n in enumerate(self.rpm):
            for b, t in enumerate(self.torque):
                p_mec = t * n * 2 * math.pi / 60
                if t == 0.0 or n == 0.0:
                    perdas[a, b] = perdas_vazio_w(n) + 3 * 0.018 * (t / 1.1) ** 2
                else:
                    perdas[a, b] = p_mec * (100.0 / eficiencia_motor(n, t) - 1.0)
        self.perdas = perdas
        arquivo.parent.mkdir(exist_ok=True)
        np.savez(arquivo, perdas=perdas)

    def perdas_motor(self, rpm, torque):
        n = min(max(rpm, 0.0), self.rpm[-1])
        t = min(max(torque, 0.0), self.torque[-1])
        i = min(int(n / self._dn), len(self.rpm) - 2)
        j = min(int(t / self._dt), len(self.torque) - 2)
        fn = (n - self.rpm[i]) / self._dn
        ft = (t - self.torque[j]) / self._dt
        p = self.perdas
        return float((1 - fn) * (1 - ft) * p[i, j] + fn * (1 - ft) * p[i + 1, j]
                     + (1 - fn) * ft * p[i, j + 1] + fn * ft * p[i + 1, j + 1])

    def motor(self, rpm, torque):
        """Eficiência do motor (0 a 1)."""
        import math
        p_mec = torque * rpm * 2 * math.pi / 60
        return p_mec / (p_mec + self.perdas_motor(rpm, torque)) if p_mec > 0 else 0.0

    def potencia_dc(self, rpm, torque):
        """Potência pedida à bateria [W] para entregar ``torque`` a ``rpm``."""
        import math
        p_mec = torque * rpm * 2 * math.pi / 60
        if p_mec <= 0.0:
            return 0.0
        return (p_mec + self.perdas_motor(rpm, torque)) / config.EFICIENCIA_INVERSOR


def torque_arrasto_vazio(rpm):
    """Torque de arrasto das perdas em vazio [N·m], presente mesmo sem acelerar."""
    import math
    w = rpm * 2 * math.pi / 60
    return perdas_vazio_w(rpm) / w if w > 1e-6 else 0.0
