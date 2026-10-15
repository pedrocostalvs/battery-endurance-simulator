from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BatteryPowerSolution:
    """Operating point that closes the battery-side DC power balance."""

    requested_power: float
    delivered_power: float
    current: float
    voltage: float
    max_available_power: float
    power_limited: bool
    residual: float


class BatteryPack:
    """A Battery Pack object based on a simplified Modified Shepherd model.

    This class represents a battery pack composed of cells arranged in series 
    and parallel. It models the terminal voltage, state-of-charge (SOC) dynamics, 
    accumulated current, and provides physical properties such as total mass 
    and volume.

    Parameters
    ----------
    tipo_celula : str
        Type of electrochemical cell. Implemented options:
        - 'Li-ion'
        - 'LiFePO4'
    n_serie : int
        Number of cells in series.
    n_paralelo : int
        Number of cells in parallel.
    soc_inicial : float, optional
        Initial state of charge of the pack (0.0–1.0). Default is 1.0.

    Attributes
    ----------
    E0 : float
        Nominal open-circuit voltage of a single cell [V].
    K : float
        Polarization constant [V].
    Q : float
        Capacity of a single cell [Ah].
    A : float
        Exponential voltage coefficient [V].
    B : float
        Exponential capacity coefficient [Ah^-1].
    R : float
        Internal resistance [Ω].
    peso : float
        Mass of a single cell [kg].
    volume : float
        Volume of a single cell [L].
    n_serie : int
        Number of series-connected cells.
    n_paralelo : int
        Number of parallel-connected cells.
    soc : float
        Current state of charge (SOC).
    carga_total : float
        Total pack capacity [Ah].
    inv_carga_total : float
        Precomputed inverse of capacity in [1/Coulombs].
    Iast : float
        Accumulated current [Coulombs].
    tempo_acumulado : float
        Elapsed time [s].
    tensao_hist : list
        History of terminal voltage values.
    corrente_hist : list
        History of current values.
    soc_hist : list
        History of SOC values.
    tempo : list
        History of time values.

    Methods
    -------
    definir_celula(tipo):
        Returns electrochemical parameters for a given cell type.
    calcular_derivadas(corrente):
        Computes time derivatives of SOC, accumulated current, and time.
    calcular_tensao(corrente, soc, Iast, tempo_acumulado):
        Computes pack terminal voltage given state and load current.
    calcular_peso_total():
        Returns total pack mass [kg].
    calcular_volume_total():
        Returns total pack volume [L].
    calcular_tensao_nominal():
        Returns nominal pack voltage [V].
    """

    def __init__(self, tipo_celula, n_serie, n_paralelo, soc_inicial=1.0):
        self.parametros = self.definir_celula(tipo_celula)
        if self.parametros is None:
            raise ValueError(f"Unknown cell type: {tipo_celula}")

        # Extract parameters
        params = self.parametros
        self.E0 = params['E0']
        self.K = params['K']
        self.Q = params['Q']
        self.A = params['A']
        self.B = params['B']
        self.R = params['R']
        self.peso = params['peso']
        self.volume = params['volume']

        self.n_serie = n_serie
        self.n_paralelo = n_paralelo

        self.soc = soc_inicial
        self.carga_total = self.Q * n_paralelo  # Ah
        self.inv_carga_total = 1.0 / (self.carga_total * 3600.0)

        # Integration states
        self.Iast = 0.0  # Accumulated current [Coulombs]
        self.tempo_acumulado = 0.0  # Time [s]

        # History
        self.tensao_hist = []
        self.corrente_hist = []
        self.soc_hist = []
        self.tempo = []

    def definir_celula(self, tipo):
        """Return parameters of a predefined electrochemical cell.

        Parameters
        ----------
        tipo : str
            Cell type identifier.

        Returns
        -------
        dict or None
            Dictionary with cell parameters if type exists, otherwise None.
        """
        catalogo = {
            'Li-ion': {
                'E0': 3.7,
                'K': 0.005,
                'Q': 3.0,
                'A': 0.1,
                'B': 0.01,
                'R': 0.02,
                'peso': 0.045,
                'volume': 0.025
            },
            'LiFePO4': {
                'E0': 3.2,
                'K': 0.003,
                'Q': 2.8,
                'A': 0.05,
                'B': 0.015,
                'R': 0.008,
                'peso': 0.07,
                'volume': 0.03
            }
        }
        return catalogo.get(tipo)

    def calcular_derivadas(self, corrente):
        """Compute state derivatives for numerical integration.

        Parameters
        ----------
        corrente : float
            Applied current [A] (positive for discharge, negative for charge).

        Returns
        -------
        tuple
            dsoc_dt : float
                Derivative of state of charge.
            dIast_dt : float
                Derivative of accumulated current.
            dtime_dt : float
                Derivative of elapsed time (constant = 1.0).
        """
        dsoc_dt = -corrente * self.inv_carga_total
        dIast_dt = corrente
        dtime_dt = 1.0
        return dsoc_dt, dIast_dt, dtime_dt

    def calcular_tensao(self, corrente, soc, Iast, tempo_acumulado):
        """Compute the terminal voltage of the battery pack.

        Parameters
        ----------
        corrente : float
            Applied current [A] (positive for discharge, negative for charge).
        soc : float
            Current state of charge (0.0–1.0).
        Iast : float
            Accumulated current [Coulombs].
        tempo_acumulado : float
            Elapsed time [s].

        Returns
        -------
        float
            Terminal voltage of the pack [V].

        Notes
        -----
        O modelo de Shepherd é avaliado POR CÉLULA e o resultado escalado
        por n_serie.  Os estados chegam em nível de PACK (corrente total,
        Iast total, capacidade total), então são convertidos para célula:
            i_cell    = corrente / n_paralelo
            q_cell    = (1 − soc) · Q          [Ah por célula]
            Iast_cell = Iast / n_paralelo
        Sem essa divisão, a corrente do pack inteiro era aplicada à
        resistência de UMA célula — com n_paralelo > 1 o sag de tensão
        ficava n_paralelo× superestimado e o barramento colapsava ao piso.
        """
        i_cell = corrente / self.n_paralelo
        q_cell = (1 - soc) * self.Q                # carga usada por célula [Ah]
        Iast_cell = Iast / self.n_paralelo

        denom1 = max(self.Q - q_cell, 1e-6)
        term_exp = self.A * np.exp(-self.B * q_cell)
        term_K = self.K * self.Q / denom1
        term_carga = term_K * q_cell
        term_Iast = term_K * (Iast_cell / 3600)

        if corrente >= 0:  # Discharge
            Vt = self.E0 - self.R * i_cell - term_Iast - term_carga + term_exp
        else:  # Charge
            i_cell_abs = abs(i_cell)
            denom2 = max(i_cell_abs * tempo_acumulado - 0.1 * self.Q, 1e-6)
            term_K_charge = self.K * self.Q / denom2 * (Iast_cell / 3600)
            Vt = self.E0 - self.R * i_cell_abs - term_K_charge - term_carga + term_exp

        return Vt * self.n_serie

    def calcular_resistencia_equivalente(self):        
        return self.n_serie * self.R / self.n_paralelo

    def resolver_potencia_descarga(self, potencia, soc, Iast, tempo_acumulado):

        values = {
            'potencia': potencia,
            'soc': soc,
            'Iast': Iast,
            'tempo_acumulado': tempo_acumulado,
        }
        for name, value in values.items():
            if not np.isfinite(value):
                raise ValueError(f"{name} must be finite.")

        potencia = float(potencia)
        soc = float(soc)
        Iast = float(Iast)
        tempo_acumulado = float(tempo_acumulado)

        if potencia < 0.0:
            raise ValueError("potencia must be non-negative for discharge.")
        if not 0.0 < soc <= 1.0:
            raise ValueError("soc must be in the interval (0, 1].")

        voltage_open = float(
            self.calcular_tensao(0.0, soc, Iast, tempo_acumulado)
        )
        if not np.isfinite(voltage_open) or voltage_open <= 0.0:
            raise ValueError("Open-circuit voltage must be finite and positive.")

        resistance = float(self.calcular_resistencia_equivalente())
        if not np.isfinite(resistance) or resistance < 0.0:
            raise ValueError("Equivalent resistance must be finite and non-negative.")

        if potencia == 0.0:
            return BatteryPowerSolution(
                requested_power=0.0,
                delivered_power=0.0,
                current=0.0,
                voltage=voltage_open,
                max_available_power=(
                    np.inf if resistance == 0.0
                    else voltage_open**2 / (4.0 * resistance)
                ),
                power_limited=False,
                residual=0.0,
            )

        if resistance == 0.0:
            current = potencia / voltage_open
            return BatteryPowerSolution(
                requested_power=potencia,
                delivered_power=potencia,
                current=current,
                voltage=voltage_open,
                max_available_power=np.inf,
                power_limited=False,
                residual=voltage_open * current - potencia,
            )

        max_available_power = voltage_open**2 / (4.0 * resistance)
        power_limited = potencia > max_available_power
        delivered_power = min(potencia, max_available_power)
        discriminant = max(
            voltage_open**2 - 4.0 * resistance * delivered_power,
            0.0,
        )

        # Stable form of the high-voltage quadratic root.  It avoids the
        # cancellation in (V0 - sqrt(discriminant)) / (2*R) for small powers.
        current = (
            2.0 * delivered_power
            / (voltage_open + np.sqrt(discriminant))
        )
        voltage = voltage_open - resistance * current
        residual = voltage * current - delivered_power

        if not np.all(np.isfinite((current, voltage, residual))):
            raise FloatingPointError("Battery power solution is not finite.")

        return BatteryPowerSolution(
            requested_power=potencia,
            delivered_power=delivered_power,
            current=current,
            voltage=voltage,
            max_available_power=max_available_power,
            power_limited=power_limited,
            residual=residual,
        )

    def calcular_peso_total(self):
        """Return the total pack mass.

        Returns
        -------
        float
            Total mass [kg].
        """
        return self.n_serie * self.n_paralelo * self.peso

    def calcular_volume_total(self):
        """Return the total pack volume.

        Returns
        -------
        float
            Total volume [L].
        """
        return self.n_serie * self.n_paralelo * self.volume

    def calcular_tensao_nominal(self):
        """Return the nominal pack voltage.

        Returns
        -------
        float
            Nominal voltage [V].
        """
        return self.E0 * self.n_serie
