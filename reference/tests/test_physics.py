"""Reference atmosphere and metamorphic physical checks."""

import unittest
from dataclasses import replace

from b777.atmosphere import FT, G, atmosphere, groundspeed, pressure_altitude_ft
from b777.model import FlightCondition, ModelSettings, PerformanceModel


class AtmosphereTests(unittest.TestCase):
    def test_reference_layers(self):
        for height, temperature, pressure in [
            (0, 288.15, 101325),
            (11000, 216.65, 22632.1),
            (20000, 216.65, 5474.89),
        ]:
            with self.subTest(height=height):
                air = atmosphere(height / FT)
                self.assertAlmostEqual(air.temperature_k, temperature, places=6)
                self.assertLess(abs(air.pressure_pa - pressure), 0.1)
        self.assertAlmostEqual(atmosphere(0).density_kg_m3, 1.225, places=5)

    def test_tropopause_continuity(self):
        a = atmosphere((11000 - 0.001) / FT)
        b = atmosphere((11000 + 0.001) / FT)
        self.assertLess(abs(a.pressure_pa - b.pressure_pa), 0.01)

    def test_pressure_inverse(self):
        for altitude in (0, 20000, 35000, 41000, 60000):
            self.assertAlmostEqual(
                pressure_altitude_ft(atmosphere(altitude).pressure_pa / 100), altitude, places=7
            )

    def test_warm_air_at_fixed_pressure_altitude(self):
        cold, warm = atmosphere(35000), atmosphere(35000, 10)
        self.assertEqual(cold.pressure_pa, warm.pressure_pa)
        self.assertLess(warm.density_kg_m3, cold.density_kg_m3)
        self.assertGreater(warm.speed_of_sound_m_s, cold.speed_of_sound_m_s)

    def test_wind_triangle_345(self):
        self.assertAlmostEqual(groundspeed(500, 20, 300), 380)
        self.assertAlmostEqual(groundspeed(500, 20, -300), 380)
        with self.assertRaises(ValueError):
            groundspeed(300, 0, 300)
        with self.assertRaises(ValueError):
            groundspeed(300, 400, 0)


class PerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = PerformanceModel()
        cls.base = FlightCondition()

    def test_tsfc_total_engine_units(self):
        result = PerformanceModel(ModelSettings(tsfc_kg_kn_h=50)).snapshot(self.base, 100)
        self.assertEqual(result.fuel_total_kg_h, 5000)
        self.assertEqual(result.fuel_per_engine_kg_h, 2500)

    def test_manual_thrust_does_not_depend_on_mass(self):
        a = self.model.snapshot(self.base, 150)
        b = self.model.snapshot(replace(self.base, mass_kg=280000), 150)
        self.assertEqual(a.fuel_total_kg_h, b.fuel_total_kg_h)
        self.assertGreater(b.drag_kn, a.drag_kn)
        self.assertTrue(any("does not balance" in note for note in b.warnings))

    def test_mass_increases_required_thrust(self):
        a = self.model.snapshot(self.base)
        b = self.model.snapshot(replace(self.base, mass_kg=280000))
        self.assertGreater(b.total_thrust_kn, a.total_thrust_kn)
        self.assertGreater(b.fuel_total_kg_h, a.fuel_total_kg_h)

    def test_headwind_changes_distance_but_not_instantaneous_flow(self):
        a = self.model.snapshot(self.base)
        b = self.model.snapshot(replace(self.base, headwind_kt=50))
        self.assertEqual(a.fuel_total_kg_h, b.fuel_total_kg_h)
        self.assertGreater(b.fuel_kg_nmi, a.fuel_kg_nmi)

    def test_temperature_mach_pressure_invariance(self):
        a = self.model.snapshot(self.base)
        b = self.model.snapshot(replace(self.base, isa_delta_c=10))
        self.assertAlmostEqual(a.drag_kn, b.drag_kn, places=8)
        self.assertAlmostEqual(a.fuel_total_kg_h, b.fuel_total_kg_h, places=8)
        self.assertGreater(b.tas_kt, a.tas_kt)

    def test_force_balance(self):
        result = self.model.snapshot(self.base)
        self.assertEqual(result.longitudinal_acceleration_m_s2, 0)
        self.assertAlmostEqual(result.lift_to_drag, self.base.mass_kg * G / (result.drag_kn * 1000))

    def test_openap_isa_cross_implementation(self):
        # This checks wiring/model consistency, not independent aircraft accuracy.
        from openap import Drag, FuelFlow

        drag = Drag("B77W")
        fuel = FuelFlow("B77W", eng="GE90-115B")
        for mass in (200000, 250000, 300000):
            for altitude in (25000, 35000, 40000):
                for mach in (0.72, 0.78, 0.84):
                    output = self.model.snapshot(FlightCondition(mass, altitude, mach))
                    reference_drag = float(drag.clean(mass, output.tas_kt, altitude)) / 1000
                    self.assertLess(abs(output.drag_kn / reference_drag - 1), 0.001)
                    reference_fuel = float(fuel.at_thrust(output.total_thrust_kn * 1000)) * 3600
                    self.assertAlmostEqual(output.fuel_total_kg_h, reference_fuel, places=8)

    def test_invalid_inputs_are_rejected(self):
        for edits in (
            {"mass_kg": float("nan")},
            {"mach": float("inf")},
            {"mass_kg": -1},
            {"mach": 0.9},
            {"isa_delta_c": 20},
            {"mass_kg": True},
            {"headwind_kt": 500},
        ):
            with self.subTest(edits=edits), self.assertRaises(ValueError):
                self.model.snapshot(replace(self.base, **edits))
        for thrust in (-1, 0, float("nan"), 2000):
            with self.assertRaises(ValueError):
                self.model.snapshot(self.base, thrust)
