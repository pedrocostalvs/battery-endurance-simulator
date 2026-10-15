"""Tests for the battery-side DC power balance."""

from pathlib import Path
import sys
import unittest

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from Models.BatteryPack import BatteryPack  # noqa: E402
from Models.Motor import Motor  # noqa: E402
from Simulation.Simulation import Simulation  # noqa: E402


class BatteryPowerBalanceTests(unittest.TestCase):
    def setUp(self):
        self.battery = BatteryPack(
            tipo_celula="Li-ion",
            n_serie=144,
            n_paralelo=5,
            soc_inicial=1.0,
        )

    def _assert_conserved(self, solution):
        self.assertTrue(np.isfinite(solution.current))
        self.assertTrue(np.isfinite(solution.voltage))
        self.assertTrue(np.isfinite(solution.residual))
        tolerance = 1e-9 * max(1.0, solution.delivered_power)
        self.assertLessEqual(abs(solution.residual), tolerance)
        self.assertAlmostEqual(
            solution.voltage * solution.current,
            solution.delivered_power,
            delta=tolerance,
        )

    def test_zero_power_returns_open_circuit_point(self):
        solution = self.battery.resolver_potencia_descarga(0.0, 1.0, 0.0, 0.0)

        self.assertEqual(solution.current, 0.0)
        self.assertEqual(solution.delivered_power, 0.0)
        self.assertFalse(solution.power_limited)
        self.assertAlmostEqual(solution.voltage, 547.2)
        self._assert_conserved(solution)

    def test_regular_power_uses_high_voltage_root(self):
        solution = self.battery.resolver_potencia_descarga(
            80_000.0, 1.0, 0.0, 0.0)

        resistance = self.battery.calcular_resistencia_equivalente()
        open_voltage = self.battery.calcular_tensao(0.0, 1.0, 0.0, 0.0)
        self.assertLess(solution.current, open_voltage / (2.0 * resistance))
        self.assertGreater(solution.voltage, open_voltage / 2.0)
        self.assertFalse(solution.power_limited)
        self._assert_conserved(solution)

    def test_small_powers_are_numerically_stable(self):
        previous_current = -1.0
        for power in (1e-12, 1e-9, 1e-6, 1e-3, 1.0):
            with self.subTest(power=power):
                solution = self.battery.resolver_potencia_descarga(
                    power, 1.0, 0.0, 0.0)
                self.assertGreater(solution.current, previous_current)
                self._assert_conserved(solution)
                previous_current = solution.current

    def test_power_near_mathematical_limit_is_stable(self):
        open_voltage = self.battery.calcular_tensao(0.0, 1.0, 0.0, 0.0)
        resistance = self.battery.calcular_resistencia_equivalente()
        max_power = open_voltage**2 / (4.0 * resistance)
        solution = self.battery.resolver_potencia_descarga(
            np.nextafter(max_power, 0.0), 1.0, 0.0, 0.0)

        self.assertFalse(solution.power_limited)
        self._assert_conserved(solution)

    def test_infeasible_power_returns_explicit_limited_solution(self):
        solution = self.battery.resolver_potencia_descarga(
            1_000_000.0, 1.0, 0.0, 0.0)

        self.assertTrue(solution.power_limited)
        self.assertAlmostEqual(
            solution.delivered_power, solution.max_available_power)
        self._assert_conserved(solution)

    def test_solution_is_continuous_for_valid_states(self):
        delta_soc = 1e-6
        for soc in (0.2, 0.5, 0.8, 1.0 - delta_soc):
            solutions = []
            for local_soc in (soc, soc + delta_soc):
                iast = (
                    (1.0 - local_soc)
                    * self.battery.Q
                    * self.battery.n_paralelo
                    * 3600.0
                )
                solution = self.battery.resolver_potencia_descarga(
                    10_000.0, local_soc, iast, 100.0)
                self.assertFalse(solution.power_limited)
                self._assert_conserved(solution)
                solutions.append(solution)

            self.assertLess(
                abs(solutions[1].current - solutions[0].current), 1e-3)
            self.assertLess(
                abs(solutions[1].voltage - solutions[0].voltage), 1e-3)

    def test_invalid_inputs_are_rejected(self):
        invalid_cases = (
            (-1.0, 1.0, 0.0, 0.0),
            (np.nan, 1.0, 0.0, 0.0),
            (np.inf, 1.0, 0.0, 0.0),
            (1.0, 0.0, 0.0, 0.0),
            (1.0, 1.1, 0.0, 0.0),
            (1.0, 1.0, np.nan, 0.0),
        )
        for args in invalid_cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.battery.resolver_potencia_descarga(*args)

    def test_simulation_stops_before_integrating_infeasible_power(self):
        motor = Motor(
            rs=0.00706,
            ld=0.0000965,
            lq=0.0000965,
            jm=0.02521,
            kf=0.005,
            lambda_m=0.04748,
            p=10,
            valor_mu=0.95,
            speed_ref=575.96,
            max_current=323.0,
        )
        simulation = Simulation(
            motor=motor,
            battery=self.battery,
            p_max_dc=None,
            tmax=0.001,
            dmax=None,
        )
        simulation.isq0 = 500.0
        simulation.wm0 = 1000.0

        result = simulation.simulate(tf=0.001)

        self.assertEqual(result["termination_reason"], "battery_power_limit")
        self.assertIsNotNone(result["battery_power_limit_event"])
        self.assertEqual(len(result["t"]), 0)
        event = result["battery_power_limit_event"]
        self.assertGreater(
            event["requested_power"], event["max_available_power"])
        self.assertTrue(np.isfinite(event["current"]))
        self.assertTrue(np.isfinite(event["voltage"]))


if __name__ == "__main__":
    unittest.main()
