"""Physical, numerical and end-to-end validation of Endurance_Real."""

from dataclasses import replace
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
from math import ceil

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
sys.path.insert(0, str(ROOT))

from config.parameters import (  # noqa: E402
    BatteryConfig,
    SimulationConfig,
    TireConfig,
)
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
            result.target_speed_m_s, result.throttle_command,
            result.brake_command, result.distance_to_corner_m,
            result.estimated_braking_distance_m,
        ):
            self.assertTrue(np.all(np.isfinite(values)))

    def test_soc_and_energy_are_monotonic_without_regeneration(self):
        self.assertTrue(np.all(np.diff(self.results.soc) <= 1e-12))
        self.assertTrue(np.all(
            np.diff(self.results.cumulative_energy_wh) >= -1e-12))
        braking = self.results.brake_force_n > 1e-6
        self.assertTrue(np.any(braking))
        self.assertTrue(np.all(self.results.electrical_power_w[braking] == 0.0))

    def test_lap_summary_conserves_energy_without_boundary_double_count(self):
        summaries = self.results.lap_summary()
        self.assertEqual(
            len(summaries),
            ceil(self.results.final_distance_m / self.results.lap_length_m),
        )
        self.assertAlmostEqual(
            sum(item.terminal_energy_wh for item in summaries),
            self.results.energy_wh,
            delta=self.results.energy_wh * 1e-6,
        )
        self.assertAlmostEqual(
            sum(item.distance_m for item in summaries),
            self.results.final_distance_m,
            places=8,
        )
        self.assertEqual(int(self.results.lap_index[-1]), 21)
        self.assertAlmostEqual(
            float(self.results.lap_position_m[-1]), self.results.lap_length_m)

    def test_lap_summary_handles_partial_final_lap(self):
        partial_config = replace(
            self.config, target_distance_m=2_500.0, maximum_time_s=400.0)
        partial = EnduranceSimulator(partial_config).run()
        summaries = partial.lap_summary()
        self.assertEqual(len(summaries), 3)
        self.assertAlmostEqual(summaries[-1].distance_m, 500.0, places=7)
        self.assertAlmostEqual(
            sum(item.terminal_energy_wh for item in summaries),
            partial.energy_wh,
            delta=partial.energy_wh * 1e-6,
        )

    def test_lap_and_segment_metadata_are_exported(self):
        self.assertEqual(len(self.results.lap_index), len(self.results.time_s))
        self.assertEqual(len(self.results.lap_position_m), len(self.results.time_s))
        self.assertEqual(
            len(self.results.segment_names), len(self.config.track_segments))
        self.assertEqual(
            len(self.results.segment_is_corner), len(self.config.track_segments))
        with tempfile.TemporaryDirectory() as temporary:
            path = self.results.save_npz(Path(temporary) / "results.npz")
            with np.load(path) as data:
                for key in (
                    "lap_index", "lap_position_m", "segment_boundaries_m",
                    "segment_is_corner", "segment_names", "max_dc_power_w",
                    "minimum_usable_soc",
                ):
                    self.assertIn(key, data.files)

    def test_reference_curve_speed_limits_are_respected(self):
        track = ReferenceTrack(
            self.config.track_segments,
            self.config.vehicle,
            self.config.tire,
            self.config.motor,
            self.config.drivetrain.final_drive_ratio,
        )
        local_limits = np.asarray([
            track.state_at(float(distance)).local_speed_limit_m_s
            for distance in self.results.distance_m
        ])
        maximum_excess = float(np.max(self.results.speed_m_s - local_limits))
        self.assertLess(maximum_excess, 0.02)

    def test_combined_grip_respects_normal_and_lateral_force(self):
        normal = 1000.0
        mu = self.config.tire.friction_coefficient
        no_cornering = self.simulator.vehicle.combined_grip_longitudinal_limit_n(
            mu, normal, 0.0)
        at_lateral_limit = (
            self.simulator.vehicle.combined_grip_longitudinal_limit_n(
                mu, normal, mu * normal)
        )
        self.assertAlmostEqual(no_cornering, mu * normal)
        self.assertAlmostEqual(at_lateral_limit, 0.0)

    def test_slow_corner_limit_matches_configured_mu_equation(self):
        track = self.simulator.track
        index = next(
            i for i, segment in enumerate(self.config.track_segments)
            if segment.name == "Curva lenta"
        )
        radius = self.config.track_segments[index].radius_m
        vehicle = self.config.vehicle
        mu = self.config.tire.friction_coefficient
        aero_vertical = 0.5 * vehicle.air_density_kg_m3 * (
            vehicle.lift_coefficient_front * vehicle.lift_area_front_m2
            + vehicle.lift_coefficient_rear * vehicle.lift_area_rear_m2
        )
        denominator = vehicle.mass_kg / radius - mu * aero_vertical
        expected = np.sqrt(
            mu * vehicle.mass_kg * vehicle.gravity_m_s2 / denominator)
        self.assertAlmostEqual(
            track.segment_speed_limits_m_s[index], expected, delta=1e-6)

    def test_configured_mu_affects_traction_braking_and_corner_speed(self):
        low = replace(self.config, tire=TireConfig(friction_coefficient=0.45),
                      target_distance_m=300.0, maximum_time_s=120.0)
        high = replace(self.config, tire=TireConfig(friction_coefficient=0.75),
                       target_distance_m=300.0, maximum_time_s=120.0)
        low_simulator = EnduranceSimulator(low)
        high_simulator = EnduranceSimulator(high)
        low_result = low_simulator.run()
        high_result = high_simulator.run()
        self.assertGreater(
            float(np.max(high_result.drive_force_n)),
            float(np.max(low_result.drive_force_n)),
        )
        low_brake = low_simulator.brake.apply(20.0, 0.0, 0.0)
        high_brake = high_simulator.brake.apply(20.0, 0.0, 0.0)
        self.assertGreater(
            high_brake.effective_wheel_force_n,
            low_brake.effective_wheel_force_n,
        )
        self.assertGreater(
            high_simulator.track.segment_speed_limits_m_s[1],
            low_simulator.track.segment_speed_limits_m_s[1],
        )

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

    def test_driver_state_and_throttle_rate_limit(self):
        self.assertTrue(set(self.results.controller_state).issubset({
            "ACCELERATING", "CRUISING", "BRAKING",
        }))
        rate = np.abs(np.diff(self.results.throttle_command)) / self.config.time_step_s
        self.assertLessEqual(
            float(np.max(rate)), self.config.throttle_rate_limit_per_s + 1e-10)
        self.assertTrue(np.all(self.results.throttle_command >= 0.0))
        self.assertTrue(np.all(self.results.throttle_command <= 1.0))
        self.assertTrue(np.all(self.results.brake_command >= 0.0))
        self.assertTrue(np.all(self.results.brake_command <= 1.0))

    def test_command_inversions_are_limited_per_lap(self):
        command = np.where(
            self.results.brake_command > 1e-9,
            -1,
            np.where(self.results.throttle_command > 1e-6, 1, 0),
        )
        inversions = []
        for lap in range(22):
            mask = np.minimum(
                (self.results.distance_m / self.results.lap_length_m).astype(int),
                21,
            ) == lap
            active = command[mask]
            active = active[active != 0]
            inversions.append(int(np.sum(active[1:] != active[:-1])))
        self.assertLessEqual(max(inversions), 8)

    def test_time_step_convergence(self):
        fine_config = replace(self.config, time_step_s=0.01)
        fine = EnduranceSimulator(fine_config).run()
        self.assertEqual(fine.status, "completed")
        energy_relative_difference = abs(
            fine.energy_wh - self.results.energy_wh) / fine.energy_wh
        time_relative_difference = abs(
            fine.total_time_s - self.results.total_time_s) / fine.total_time_s
        self.assertLess(energy_relative_difference, 0.01)
        self.assertLess(time_relative_difference, 0.01)

    def test_graphs_are_generated(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = generate_all_plots(self.results, Path(temporary))
            self.assertEqual(len(paths), 9)
            for path in paths:
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 1_000)

    def test_interactive_dashboard_has_eight_visible_panels(self):
        import matplotlib.pyplot as plt

        figure = create_interactive_dashboard(self.results)
        try:
            titled_axes = [axis for axis in figure.axes if axis.get_title()]
            self.assertEqual(len(titled_axes), 8)
            self.assertTrue(all(axis.get_visible() for axis in titled_axes))
            self.assertTrue(np.allclose(figure.get_size_inches(), (15.0, 11.0)))
            self.assertIn("volta de referência 2", figure._suptitle.get_text())
            self.assertEqual(len(titled_axes[0].patches), 4)
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
