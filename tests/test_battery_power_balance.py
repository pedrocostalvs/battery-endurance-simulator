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

    @staticmethod
    def _make_motor():
        return Motor(
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
        simulation = Simulation(
            motor=self._make_motor(),
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

    def test_hard_iq_limit_is_continuous_at_constant_torque_transition(self):
        simulation = Simulation(motor=self._make_motor(), p_max_dc=80_000.0)
        transition_speed = (
            simulation.p_max_dc * simulation.eta_drive
            / (simulation.Kt * simulation.max_current)
        )
        epsilon = 1e-7 * transition_speed

        below = simulation._hard_iq_power_limit(transition_speed - epsilon)
        at_transition = simulation._hard_iq_power_limit(transition_speed)
        above = simulation._hard_iq_power_limit(transition_speed + epsilon)

        self.assertAlmostEqual(below, simulation.max_current)
        self.assertAlmostEqual(at_transition, simulation.max_current)
        self.assertLess(above, simulation.max_current)
        self.assertLess(below - above, 1e-3)

    def test_hard_iq_limit_handles_zero_negative_and_extreme_speed(self):
        simulation = Simulation(motor=self._make_motor(), p_max_dc=80_000.0)

        self.assertEqual(
            simulation._hard_iq_power_limit(0.0), simulation.max_current)
        self.assertEqual(
            simulation._hard_iq_power_limit(1e-12), simulation.max_current)
        self.assertAlmostEqual(
            simulation._hard_iq_power_limit(-1_000.0),
            simulation._hard_iq_power_limit(1_000.0),
        )
        extreme = simulation._hard_iq_power_limit(1e12)
        self.assertTrue(np.isfinite(extreme))
        self.assertGreater(extreme, 0.0)

    def test_hard_iq_limit_conserves_requested_power(self):
        simulation = Simulation(motor=self._make_motor(), p_max_dc=80_000.0)
        for speed in (400.0, 575.96, 1_000.0, 10_000.0):
            with self.subTest(speed=speed):
                iq_limit = simulation._hard_iq_power_limit(speed)
                requested = simulation._requested_dc_power(iq_limit, speed)
                self.assertAlmostEqual(
                    requested,
                    simulation.p_max_dc,
                    delta=simulation._dc_power_limit_tolerance(),
                )

    def test_actual_current_power_violation_stops_before_rk4(self):
        simulation = Simulation(
            motor=self._make_motor(),
            battery=self.battery,
            p_max_dc=80_000.0,
            tmax=0.001,
            dmax=None,
        )
        simulation.wm0 = 500.0
        iq_at_limit = simulation._hard_iq_power_limit(simulation.wm0)
        simulation.isq0 = iq_at_limit * (1.0 + 1e-5)

        result = simulation.simulate(tf=0.001)

        self.assertEqual(result["termination_reason"], "dc_power_limit")
        self.assertEqual(len(result["t"]), 0)
        self.assertIsNone(result["battery_power_limit_event"])
        event = result["dc_power_limit_event"]
        self.assertIsNotNone(event)
        self.assertGreater(
            event["requested_power"],
            event["power_limit"] + event["tolerance"],
        )
        self.assertAlmostEqual(event["current_q"], simulation.isq0)
        self.assertAlmostEqual(event["omega_m"], simulation.wm0)

    def test_dc_power_tolerance_only_covers_floating_point_noise(self):
        simulation = Simulation(motor=self._make_motor(), p_max_dc=80_000.0)
        tolerance = simulation._dc_power_limit_tolerance()

        self.assertAlmostEqual(tolerance, 0.000081)
        self.assertFalse(simulation._dc_power_limit_exceeded(80_000.0))
        self.assertFalse(
            simulation._dc_power_limit_exceeded(80_000.0 + tolerance))
        self.assertTrue(
            simulation._dc_power_limit_exceeded(
                np.nextafter(80_000.0 + tolerance, np.inf)))

    def test_invalid_dc_power_limits_are_rejected(self):
        for invalid_limit in (0.0, -1.0, np.nan, np.inf):
            with self.subTest(limit=invalid_limit), self.assertRaises(ValueError):
                Simulation(
                    motor=self._make_motor(), p_max_dc=invalid_limit)

    def test_rk4_converges_near_dc_power_limit(self):
        simulation = Simulation(motor=self._make_motor(), p_max_dc=80_000.0)
        speed = 500.0
        iq = 0.95 * simulation._hard_iq_power_limit(speed)
        x0 = np.array([0.0, iq, 0.0, speed, 0.0, 25.0])
        dt = 1e-4

        def integrate(substeps):
            x = x0.copy()
            local_dt = dt / substeps
            for step in range(substeps):
                x = simulation._rk4(
                    step * local_dt, x, 0.0, 0.0, 0.0, local_dt)
            return x

        coarse = integrate(1)
        medium = integrate(2)
        fine = integrate(4)
        coarse_delta = np.linalg.norm(coarse - medium)
        fine_delta = np.linalg.norm(medium - fine)

        self.assertTrue(np.all(np.isfinite(fine)))
        self.assertGreater(coarse_delta, 0.0)
        self.assertLess(fine_delta, coarse_delta)


if __name__ == "__main__":
    unittest.main()
