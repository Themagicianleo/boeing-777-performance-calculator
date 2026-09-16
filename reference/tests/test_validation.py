"""Synthetic fixtures exercise software, never aircraft accuracy."""

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from b777.model import FlightCondition, PerformanceModel
from b777.validation import error_metrics, evaluate_observations


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = PerformanceModel()
        cls.data = {
            "aircraft": "B77W",
            "engine": "GE90-115B",
            "source_type": "synthetic",
            "source": "Unit-test fixture, not aircraft measurements",
            "records": [],
        }
        for i, mass in enumerate((220000, 230000, 240000, 250000)):
            condition = FlightCondition(mass_kg=mass)
            cls.data["records"].append(
                {
                    "id": str(i),
                    "flight_id": f"synthetic-{i}",
                    "split": "train" if i < 2 else "test",
                    "condition": asdict(condition),
                    "observed_fuel_kg_h": 1.1 * cls.model.snapshot(condition).fuel_total_kg_h,
                }
            )

    def test_known_error_metrics(self):
        result = error_metrics([110, 180], [100, 200])
        self.assertEqual(result["mae_kg_h"], 15)
        self.assertEqual(result["bias_kg_h"], -5)
        self.assertAlmostEqual(result["mape_percent"], 10)
        self.assertAlmostEqual(result["rmse_kg_h"], 250**0.5)

    def test_known_scale_recovery(self):
        result = evaluate_observations(self.model, self.data)
        self.assertAlmostEqual(result["relative_fitted_scale"], 1.1)
        self.assertLess(result["metrics"]["test"]["fitted"]["rmse_kg_h"], 1e-8)
        self.assertEqual(result["source_type"], "synthetic")

    def test_flight_leakage_rejected(self):
        data = deepcopy(self.data)
        data["records"][2]["flight_id"] = data["records"][0]["flight_id"]
        with self.assertRaisesRegex(ValueError, "leakage"):
            evaluate_observations(self.model, data)

    def test_missing_data_and_duplicate_id_rejected(self):
        data = deepcopy(self.data)
        data["records"] = []
        with self.assertRaises(ValueError):
            evaluate_observations(self.model, data)
        data = deepcopy(self.data)
        data["records"][1]["id"] = data["records"][0]["id"]
        with self.assertRaises(ValueError):
            evaluate_observations(self.model, data)

    def test_cli_export_and_invalid_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            subprocess.run(
                [sys.executable, "-m", "b777", "snapshot", "--output", str(path)],
                check=True,
                capture_output=True,
            )
            data = json.loads(path.read_text())
            self.assertEqual(data["model"]["openap_version"], "2.6.1")
            self.assertGreater(data["result"]["fuel_total_kg_h"], 0)
        invalid = subprocess.run(
            [sys.executable, "-m", "b777", "cruise", "--thrust-kn", "150"], capture_output=True
        )
        self.assertNotEqual(invalid.returncode, 0)
