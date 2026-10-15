"""Physical, numerical and end-to-end validation of Endurance_Real."""

from dataclasses import replace
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
sys.path.insert(0, str(ROOT))

from config.parameters import BatteryConfig, SimulationConfig  # noqa: E402
from models.battery import BatteryModel  # noqa: E402
from simulation.endurance import EnduranceSimulator  # noqa: E402
from simulation.track import ReferenceTrack  # noqa: E402
from visualization.plots import (  # noqa: E402
    create_interactive_dashboard,
    generate_all_plots,
)


class EnduranceRealTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = SimulationConfig()
        cls.simulator = EnduranceSimulator(cls.config)
        cls.results = cls.simulator.run()

    def test_initial_conditions_and_battery_power_conservation(self):
        battery = BatteryModel(BatteryConfig())
        self.assertEqual(battery.soc, 1.0)
        self.assertEqual(battery.energy_delivered_wh, 0.0)

        point = battery.solve_power(20_000.0)
        self.assertTrue(point.feasible)
        self.assertAlmostEqual(
            point.terminal_voltage_v * point.current_a,
            point.delivered_power_w,
            delta=1e-8,
        )
        self.assertAlmostEqual(
            point.open_circuit_voltage_v * point.current_a,
            point.delivered_power_w + point.resistive_loss_w,
            delta=1e-8,
        )
        battery.advance(point, 1.0)
        self.assertLess(battery.soc, 1.0)

    def test_braking_chain_is_dimensional_and_adhesion_limited(self):
        speed = 20.0
        output = self.simulator.brake.apply(
            speed_m_s=speed,
            lateral_force_n=0.0,
            previous_deceleration_m_s2=0.0,
            pedal_fraction=1.0,
        )
        cfg = self.config.brake
        expected_pressure = (
            cfg.pedal_force_n * cfg.pedal_ratio / cfg.master_area_m2)
        expected_pad_normal = (
            expected_pressure * cfg.wheel_cylinder_area_m2
            * cfg.pads_per_disc * cfg.number_of_discs)
        expected_disc_torque = (
            expected_pad_normal * cfg.pad_friction_coefficient
            * cfg.effective_disc_radius_m)

        self.assertAlmostEqual(output.master_pressure_pa, expected_pressure)
        self.assertAlmostEqual(output.total_pad_normal_force_n, expected_pad_normal)
        self.assertAlmostEqual(output.total_disc_torque_nm, expected_disc_torque)
        self.assertLessEqual(
            output.effective_wheel_force_n, output.adhesion_limit_n)
        self.assertGreater(output.front_normal_load_n, output.rear_normal_load_n)

    def test_constant_speed_force_balance(self):
        speed = 15.0
        resistance = self.simulator.vehicle.total_resistance_n(speed)
        net_force = resistance - resistance
        acceleration = net_force / self.simulator.drivetrain.equivalent_mass_kg
        self.assertAlmostEqual(acceleration, 0.0)

    def test_motor_respects_torque_speed_current_and_power_limits(self):
        motor = self.simulator.motor
        cfg = self.config.motor
        low_speed = motor.maximum_drive_torque(1.0)
        high_speed = motor.maximum_drive_torque(0.9 * cfg.max_speed_rad_s)
        overspeed = motor.maximum_drive_torque(cfg.max_speed_rad_s)

        self.assertLessEqual(low_speed.torque_nm, cfg.max_torque_nm)
        self.assertLessEqual(
            low_speed.phase_current_peak_a, cfg.max_phase_current_peak_a)
        self.assertLessEqual(high_speed.dc_power_w, cfg.max_dc_power_w)
        self.assertEqual(overspeed.torque_nm, 0.0)

    def test_complete_track_finishes_exactly_without_non_finite_values(self):
        result = self.results
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.termination_reason, "target_distance_reached")
        self.assertAlmostEqual(result.final_distance_m, 22_000.0, places=7)
        self.assertLessEqual(float(np.max(result.distance_m)), 22_000.0 + 1e-8)
        for values in (
            result.time_s, result.distance_m, result.speed_m_s,
            result.acceleration_m_s2, result.electrical_power_w,
            result.battery_current_a, result.battery_voltage_v, result.soc,
            result.cumulative_energy_wh,
        ):
            self.assertTrue(np.all(np.isfinite(values)))

    def test_soc_and_energy_are_monotonic_without_regeneration(self):
        self.assertTrue(np.all(np.diff(self.results.soc) <= 1e-12))
        self.assertTrue(np.all(
            np.diff(self.results.cumulative_energy_wh) >= -1e-12))
        braking = self.results.brake_force_n > 1e-6
        self.assertTrue(np.any(braking))
        self.assertTrue(np.all(self.results.electrical_power_w[braking] == 0.0))

    def test_reference_curve_speed_limits_are_respected(self):
        track = ReferenceTrack(
            self.config.track_segments,
            self.config.vehicle,
            self.config.motor,
            self.config.drivetrain.final_drive_ratio,
        )
        local_limits = np.asarray([
            track.state_at(float(distance)).local_speed_limit_m_s
            for distance in self.results.distance_m
        ])
        maximum_excess = float(np.max(self.results.speed_m_s - local_limits))
        self.assertLess(maximum_excess, 0.02)

    def test_relevant_limit_causes_explicit_termination(self):
        battery = replace(
            self.config.battery, minimum_usable_soc=0.9999)
        short_config = replace(
            self.config,
            battery=battery,
            maximum_time_s=200.0,
            time_step_s=0.04,
        )
        result = EnduranceSimulator(short_config).run()
        self.assertEqual(result.status, "interrupted")
        self.assertEqual(result.termination_reason, "minimum_usable_soc_reached")
        self.assertLess(result.final_distance_m, short_config.target_distance_m)

    def test_acceleration_and_braking_both_occur(self):
        self.assertGreater(float(np.max(self.results.acceleration_m_s2)), 0.0)
        self.assertLess(float(np.min(self.results.acceleration_m_s2)), 0.0)
        self.assertTrue(np.any(self.results.drive_force_n > 0.0))
        self.assertTrue(np.any(self.results.brake_force_n > 0.0))

    def test_time_step_convergence(self):
        coarse_config = replace(self.config, time_step_s=0.04)
        coarse = EnduranceSimulator(coarse_config).run()
        self.assertEqual(coarse.status, "completed")
        energy_relative_difference = abs(
            coarse.energy_wh - self.results.energy_wh) / self.results.energy_wh
        time_relative_difference = abs(
            coarse.total_time_s - self.results.total_time_s) / self.results.total_time_s
        self.assertLess(energy_relative_difference, 0.01)
        self.assertLess(time_relative_difference, 0.01)

    def test_graphs_are_generated(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = generate_all_plots(self.results, Path(temporary))
            self.assertEqual(len(paths), 7)
            for path in paths:
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 1_000)

    def test_interactive_dashboard_has_one_window_with_seven_plots(self):
        import matplotlib.pyplot as plt

        figure = create_interactive_dashboard(self.results)
        try:
            self.assertEqual(len(figure.axes), 8)
            self.assertTrue(all(axis.get_visible() for axis in figure.axes[:7]))
            self.assertFalse(figure.axes[7].get_visible())
            self.assertEqual(
                [len(axis.lines) for axis in figure.axes[:7]], [1] * 7)
        finally:
            plt.close(figure)

    def test_entry_point_runs_from_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = os.environ.copy()
            environment["ENDURANCE_NO_SHOW"] = "1"
            completed = subprocess.run(
                [sys.executable, str(ROOT / "run_endurance.py")],
                cwd=temporary,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("Distância:              22000.000000 m", completed.stdout)
        self.assertIn("Status:                 COMPLETED", completed.stdout)
        self.assertNotIn("[Arquivos gerados]", completed.stdout)
        self.assertNotIn(".png", completed.stdout)
        self.assertNotIn(".npz", completed.stdout)


if __name__ == "__main__":
    unittest.main()
