"""Conservation, fuel-floor event, and an analytic integration benchmark."""

import math
import unittest
from dataclasses import replace

from b777.atmosphere import KNOT, G, atmosphere
from b777.model import FlightCondition, ModelSettings, PerformanceModel
from b777.simulation import CruiseRequest, simulate_cruise


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = PerformanceModel()

    def test_mass_conservation_and_distance(self):
        result = simulate_cruise(self.model, CruiseRequest(distance_nmi=500))
        self.assertTrue(result.completed)
        self.assertAlmostEqual(result.points[-1].distance_nmi, 500, places=8)
        for a, b in zip(result.points, result.points[1:], strict=False):
            self.assertLess(b.mass_kg, a.mass_kg)
            self.assertGreater(b.burned_fuel_kg, a.burned_fuel_kg)
            self.assertAlmostEqual(b.mass_kg + b.burned_fuel_kg, 250000, places=7)
        self.assertLess(result.points[-1].fuel_flow_kg_h, result.points[0].fuel_flow_kg_h)

    def test_protected_fuel_event(self):
        request = CruiseRequest(distance_nmi=2000, protected_fuel_kg=49000)
        result = simulate_cruise(self.model, request)
        self.assertFalse(result.completed)
        self.assertEqual(result.stop_reason, "Protected fuel floor reached")
        self.assertAlmostEqual(result.fuel_burn_kg, 1000, places=7)
        self.assertGreater(result.points[-1].distance_nmi, 0)
        self.assertLess(result.points[-1].distance_nmi, 2000)
        self.assertTrue(all(p.remaining_fuel_kg >= 49000 for p in result.points))

    def test_headwind_increases_segment_burn(self):
        a = CruiseRequest(distance_nmi=500)
        b = replace(a, condition=replace(a.condition, headwind_kt=50))
        self.assertGreater(
            simulate_cruise(self.model, b).fuel_burn_kg, simulate_cruise(self.model, a).fuel_burn_kg
        )

    def test_convergence_against_analytic_solution(self):
        # Constant TSFC: dm/dt=-(a+b*m^2), with an exact tangent solution.
        tsfc = 55.0
        model = PerformanceModel(ModelSettings(tsfc_kg_kn_h=tsfc))
        request = CruiseRequest(distance_nmi=2000, protected_fuel_kg=0)
        condition = request.condition
        air = atmosphere(condition.altitude_ft)
        speed = condition.mach * air.speed_of_sound_m_s
        q_area = 0.5 * air.density_kg_m3 * speed**2 * model.wing_area_m2
        a = tsfc * model.polar["cd0"] * q_area / 1000
        b = tsfc * model.polar["k"] * G**2 / q_area / 1000
        duration = request.distance_nmi / (speed / KNOT)
        exact_mass = math.sqrt(a / b) * math.tan(
            math.atan(condition.mass_kg * math.sqrt(b / a)) - math.sqrt(a * b) * duration
        )
        errors = []
        for step in (120, 60, 30):
            result = simulate_cruise(model, replace(request, step_seconds=step))
            self.assertTrue(result.completed)
            errors.append(abs(result.points[-1].mass_kg - exact_mass))
        self.assertLess(errors[-1], 0.1)
        self.assertGreater(errors[0] / errors[1], 3.5)
        self.assertGreater(errors[1] / errors[2], 3.5)

    def test_invalid_mass_budget_and_scope(self):
        for edits in (
            {"protected_fuel_kg": 50000},
            {"zero_fuel_mass_kg": 260000},
            {"distance_nmi": -1},
            {"step_seconds": 0},
        ):
            with self.assertRaises(ValueError):
                simulate_cruise(self.model, replace(CruiseRequest(), **edits))
        with self.assertRaises(ValueError):
            simulate_cruise(
                self.model, CruiseRequest(condition=FlightCondition(351000, 41000, 0.70))
            )
