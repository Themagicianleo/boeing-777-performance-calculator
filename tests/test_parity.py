"""Check the browser Python adaptation against the existing desktop engine."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference'))
from b777.model import FlightCondition, ModelSettings, PerformanceModel
from b777.simulation import CruiseRequest, simulate_cruise

spec = importlib.util.spec_from_file_location('web_b777', ROOT / 'dist/python/b777/__init__.py',
                                            submodule_search_locations=[str(ROOT / 'dist/python/b777')])
module = importlib.util.module_from_spec(spec)
sys.modules['web_b777'] = module
spec.loader.exec_module(module)
from web_b777.model import FlightCondition as WebCondition, ModelSettings as WebSettings, PerformanceModel as WebModel
from web_b777.simulation import CruiseRequest as WebRequest, simulate_cruise as web_cruise


class ParityTests(unittest.TestCase):
    def test_81_flight_states(self):
        original, web = PerformanceModel(), WebModel()
        for mass in (200000, 250000, 300000):
            for alt in (25000, 35000, 40000):
                for mach in (.70, .78, .84):
                    for delta in (-25, 0, 15):
                        args = dict(mass_kg=mass, altitude_ft=alt, mach=mach, isa_delta_c=delta,
                                    headwind_kt=30, crosswind_kt=50)
                        a = original.snapshot(FlightCondition(**args))
                        b = web.snapshot(WebCondition(**args))
                        for key in ('fuel_total_kg_h','drag_kn','isa_reference_max_thrust_kn','groundspeed_kt'):
                            self.assertAlmostEqual(getattr(a,key),getattr(b,key),delta=1e-7)
                        self.assertEqual(a.screening_passed,b.screening_passed)

    def test_manual_thrust_and_tsfc(self):
        for tsfc in (None,55):
            original=PerformanceModel(ModelSettings(tsfc_kg_kn_h=tsfc))
            web=WebModel(WebSettings(tsfc_kg_kn_h=tsfc))
            for thrust in (1, 50, 150, 400, 1027.8):
                a=original.snapshot(FlightCondition(),thrust)
                b=web.snapshot(WebCondition(),thrust)
                self.assertAlmostEqual(a.fuel_total_kg_h,b.fuel_total_kg_h,delta=1e-7)

    def test_complete_and_fuel_floor_segments(self):
        for distance in (1500, 2500):
            a=simulate_cruise(PerformanceModel(),CruiseRequest(distance_nmi=distance))
            b=web_cruise(WebModel(),WebRequest(distance_nmi=distance))
            self.assertEqual(a.completed,b.completed)
            self.assertAlmostEqual(a.fuel_burn_kg,b.fuel_burn_kg,delta=1e-7)
            self.assertAlmostEqual(a.points[-1].distance_nmi,b.points[-1].distance_nmi,delta=1e-7)

    def test_reject_invalid_inputs(self):
        for key,value in [('mass_kg',float('nan')),('mach',.95),('isa_delta_c',30)]:
            with self.assertRaises(ValueError):
                WebModel().snapshot(replace(WebCondition(),**{key:value}))


if __name__=='__main__':
    unittest.main(verbosity=2)
