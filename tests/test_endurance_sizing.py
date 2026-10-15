"""Tests for the independent preliminary endurance sizing module."""

from dataclasses import replace
from pathlib import Path
import sys
import unittest

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

from endurance_sizing.energy import calculate_energy_demand  # noqa: E402
from endurance_sizing.pack_sizing import (  # noqa: E402
    CheckStatus,
    assess_pack,
    enumerate_energy_candidates,
)
from endurance_sizing.parameters import (  # noqa: E402
    CellSpecifications,
    DrivetrainEfficiencies,
    PackConfiguration,
    SizingParameters,
    VehicleParameters,
)
from endurance_sizing.profiles import (  # noqa: E402
    VelocityProfile,
    build_hypothetical_endurance_cycle,
    repeat_to_exact_distance,
)
from endurance_sizing.scenario import (  # noqa: E402
    run_initial_hypothetical_scenario,
)
from endurance_sizing.sensitivity import run_sensitivity  # noqa: E402


class EnduranceSizingTests(unittest.TestCase):
    def setUp(self):
        self.unit_efficiency = DrivetrainEfficiencies(1.0, 1.0, 1.0)
        self.base_sizing = SizingParameters(
            target_distance_m=100.0,
            sizing_margin_fraction=0.0,
            usable_battery_fraction=1.0,
        )

    def test_constant_speed_matches_analytical_energy(self):
        vehicle = VehicleParameters(
            mass_kg=200.0,
            drag_coefficient=0.5,
            frontal_area_m2=1.0,
            rolling_resistance_coefficient=0.01,
            air_density_kg_m3=1.2,
        )
        profile = VelocityProfile(
            np.array([0.0, 10.0]), np.array([10.0, 10.0]),
            "constant", "unit test")
        result = calculate_energy_demand(
            profile, vehicle, self.unit_efficiency, self.base_sizing)

        force = 0.01 * 200.0 * 9.81 + 0.5 * 1.2 * 0.5 * 1.0 * 10.0**2
        expected_wh = force * 100.0 / 3600.0
        self.assertAlmostEqual(result.distance_m, 100.0)
        self.assertAlmostEqual(result.energy_wh, expected_wh)

    def test_linear_acceleration_matches_kinetic_energy(self):
        vehicle = VehicleParameters(100.0, 0.0, 1.0, 0.0)
        profile = VelocityProfile(
            np.array([0.0, 10.0]), np.array([0.0, 10.0]),
            "acceleration", "unit test")
        result = calculate_energy_demand(
            profile, vehicle, self.unit_efficiency, self.base_sizing)

        expected_wh = 0.5 * 100.0 * 10.0**2 / 3600.0
        self.assertAlmostEqual(result.energy_wh, expected_wh)

    def test_braking_has_no_regenerative_credit(self):
        vehicle = VehicleParameters(100.0, 0.0, 1.0, 0.0)
        profile = VelocityProfile(
            np.array([0.0, 10.0]), np.array([10.0, 0.0]),
            "braking", "unit test")
        result = calculate_energy_demand(
            profile, vehicle, self.unit_efficiency, self.base_sizing)

        self.assertEqual(result.energy_wh, 0.0)
        self.assertTrue(np.all(result.electrical_power_w == 0.0))

    def test_profile_repetition_stops_exactly_at_target_distance(self):
        cycle = build_hypothetical_endurance_cycle(sample_dt_s=0.2)
        profile = repeat_to_exact_distance(cycle, 22_000.0)

        self.assertAlmostEqual(profile.distance_m, 22_000.0, places=6)
        self.assertIn("não deriva do Sprint", profile.source)
        self.assertLessEqual(profile.distance_m, 22_000.0 + 1e-7)

    def test_margin_and_usable_fraction_are_kept_distinct(self):
        vehicle = VehicleParameters(100.0, 0.0, 1.0, 0.01)
        profile = VelocityProfile(
            np.array([0.0, 10.0]), np.array([10.0, 10.0]),
            "constant", "unit test")
        sizing = replace(
            self.base_sizing,
            sizing_margin_fraction=0.20,
            usable_battery_fraction=0.80,
        )
        result = calculate_energy_demand(
            profile, vehicle, self.unit_efficiency, sizing)

        self.assertAlmostEqual(
            result.required_usable_energy_wh, result.energy_wh * 1.20)
        self.assertAlmostEqual(
            result.minimum_nominal_energy_wh,
            result.required_usable_energy_wh / 0.80,
        )

    def test_generic_pack_is_not_approved_when_limits_are_missing(self):
        scenario = run_initial_hypothetical_scenario()
        assessment = scenario.pack_assessment

        self.assertAlmostEqual(assessment.nominal_voltage_v, 532.8)
        self.assertAlmostEqual(assessment.nominal_capacity_ah, 15.0)
        self.assertAlmostEqual(assessment.nominal_energy_wh, 7_992.0)
        self.assertEqual(assessment.overall_status, CheckStatus.PENDING)
        self.assertTrue(any(
            check.status == CheckStatus.PENDING for check in assessment.checks))

    def test_pack_limits_can_produce_explicit_pass(self):
        vehicle = VehicleParameters(100.0, 0.0, 1.0, 0.001)
        profile = VelocityProfile(
            np.array([0.0, 10.0]), np.array([1.0, 1.0]),
            "low power", "unit test")
        energy = calculate_energy_demand(
            profile, vehicle, self.unit_efficiency, self.base_sizing)
        cell = CellSpecifications(
            name="test cell",
            nominal_voltage_v=3.7,
            capacity_ah=3.0,
            min_voltage_v=3.0,
            max_voltage_v=4.2,
            max_continuous_current_a=10.0,
            max_continuous_c_rate=4.0,
        )
        pack = PackConfiguration(
            series=10,
            parallel=2,
            max_pack_power_w=10_000.0,
            allowed_min_voltage_v=25.0,
            allowed_max_voltage_v=45.0,
        )
        assessment = assess_pack(cell, pack, energy, self.base_sizing)

        self.assertEqual(assessment.overall_status, CheckStatus.PASS)

    def test_energy_candidate_enumeration_meets_nominal_requirement(self):
        cell = CellSpecifications("generic", 3.7, 3.0)
        candidates = enumerate_energy_candidates(
            cell, 8_500.0, series_options=(144,), extra_parallel_options=2)

        self.assertEqual([item.parallel for item in candidates], [6, 7, 8])
        for candidate in candidates:
            nominal_wh = (
                candidate.series * candidate.parallel
                * cell.nominal_voltage_v * cell.capacity_ah)
            self.assertGreaterEqual(nominal_wh, 8_500.0)

    def test_sensitivity_has_expected_monotonic_trends(self):
        vehicle = VehicleParameters(200.0, 0.6, 0.8, 0.02)
        efficiencies = DrivetrainEfficiencies(0.95, 0.90, 0.95)
        profile = VelocityProfile(
            np.array([0.0, 5.0, 15.0]), np.array([0.0, 15.0, 15.0]),
            "mixed", "unit test")
        points = run_sensitivity(
            profile,
            vehicle,
            efficiencies,
            self.base_sizing,
            {
                "mass": (0.9, 1.0, 1.1),
                "motor_efficiency": (0.9, 1.0, 1.1),
            },
        )
        mass_energy = [p.energy_wh for p in points if p.parameter == "mass"]
        efficiency_energy = [
            p.energy_wh for p in points if p.parameter == "motor_efficiency"]

        self.assertLess(mass_energy[0], mass_energy[1])
        self.assertLess(mass_energy[1], mass_energy[2])
        self.assertGreater(efficiency_energy[0], efficiency_energy[1])
        self.assertGreater(efficiency_energy[1], efficiency_energy[2])

    def test_initial_scenario_is_finite_and_exactly_22_km(self):
        scenario = run_initial_hypothetical_scenario()

        self.assertAlmostEqual(scenario.energy.distance_m, 22_000.0, places=6)
        self.assertTrue(np.isfinite(scenario.energy.energy_wh))
        self.assertGreater(scenario.energy.energy_wh, 0.0)
        self.assertFalse(scenario.sizing.regenerative_braking)

    def test_invalid_profiles_and_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            VelocityProfile(
                np.array([0.0, 0.0]), np.array([0.0, 1.0]),
                "invalid", "unit test")
        with self.assertRaises(ValueError):
            SizingParameters(usable_battery_fraction=0.0)
        with self.assertRaises(ValueError):
            DrivetrainEfficiencies(0.95, 1.01, 0.95)


if __name__ == "__main__":
    unittest.main()
