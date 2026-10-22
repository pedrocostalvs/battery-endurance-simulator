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


def torque_arrasto_vazio(rpm):
    """Torque de arrasto das perdas em vazio [N·m], presente mesmo sem acelerar."""
    import math
    w = rpm * 2 * math.pi / 60
    return perdas_vazio_w(rpm) / w if w > 1e-6 else 0.0
