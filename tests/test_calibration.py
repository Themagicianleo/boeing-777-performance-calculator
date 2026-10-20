"""Keep the shipped fuel calibration tied to Boeing's payload/range chart."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("calibrate", ROOT / "calibration/calibrate.py")
calibrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calibrate)
from b777.model import BOEING_FUEL_CALIBRATION, FlightCondition, ModelSettings, PerformanceModel  # noqa: E402


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        data = json.loads((ROOT / "calibration/boeing_777-300er_payload_range.json").read_text())
        cls.points = [dict(p, tow_kg=min(p["brake_release_lb"] * calibrate.LB, calibrate.MTOW_KG),
                           zfw_kg=p["zfw_lb"] * calibrate.LB) for p in data["points"]]
        raw = PerformanceModel(ModelSettings(calibrated=False))
        cls.table = calibrate.specific_range_table(raw, 185000, calibrate.MTOW_KG)
        cls.fit = calibrate.fit_fuel_scale(cls.table, cls.points, calibrate.CONTINGENCY)

    def test_shipped_factor_matches_refit(self):
        self.assertAlmostEqual(self.fit["fuel_scale"], BOEING_FUEL_CALIBRATION, delta=0.002)

    def test_calibrated_ranges_track_boeing_chart(self):
        self.assertLess(self.fit["rms_nmi"], 40)
        for point, model_range in zip(self.points, self.fit["model_range_nmi"]):
            self.assertLess(abs(model_range - point["range_nmi"]), 60, point["label"])

    def test_default_model_applies_calibration(self):
        condition = FlightCondition()
        raw = PerformanceModel(ModelSettings(calibrated=False)).snapshot(condition)
        calibrated = PerformanceModel().snapshot(condition)
        self.assertAlmostEqual(calibrated.fuel_total_kg_h, raw.fuel_total_kg_h * BOEING_FUEL_CALIBRATION, places=6)
        self.assertEqual(calibrated.drag_kn, raw.drag_kn)

    def test_user_tsfc_is_not_calibrated(self):
        result = PerformanceModel(ModelSettings(tsfc_kg_kn_h=50)).snapshot(FlightCondition(), 100)
        self.assertEqual(result.fuel_total_kg_h, 5000)


if __name__ == "__main__":
    unittest.main()
