"""Exercise the local HTTP interface, shared model, and command-line launcher."""

import json
from http.client import HTTPConnection
from pathlib import Path
import subprocess
import sys
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from b777_calculator import create_server, MAX_REQUEST_BYTES


class LocalCalculatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def calculate(self, payload):
        status, body, _ = self.request("POST", "/api/calculate", json.dumps(payload), {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        return json.loads(body)

    def test_local_runtime_and_static_interface(self):
        status, body, _ = self.request("GET", "/api/runtime")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["runtime"], "cpython-local")
        status, body, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"B777 Performance Lab", body)

    def test_snapshot_and_headwind_physics(self):
        base = self.calculate({"action": "snapshot"})["result"]
        wind = self.calculate({"condition": {"headwind_kt": 50}})["result"]
        self.assertAlmostEqual(base["fuel_total_kg_h"], 10710.224648, places=5)
        self.assertEqual(base["fuel_total_kg_h"], wind["fuel_total_kg_h"])
        self.assertGreater(wind["fuel_kg_nmi"], base["fuel_kg_nmi"])

    def test_cruise_completion_and_protected_fuel(self):
        result = self.calculate({"action": "cruise", "cruise": {"distance_nmi": 1500}})["result"]
        self.assertTrue(result["completed"])
        self.assertAlmostEqual(result["fuel_burn_kg"], 31997.461084, places=5)
        stopped = self.calculate({"action": "cruise", "cruise": {"distance_nmi": 2500}})["result"]
        self.assertFalse(stopped["completed"])
        self.assertEqual(stopped["points"][-1]["remaining_fuel_kg"], 8000)

    def test_other_experiments_and_invalid_inputs(self):
        self.assertEqual(len(self.calculate({"action": "compare"})["result"]["comparisons"]), 5)
        self.assertEqual(len(self.calculate({"action": "sensitivity", "cruise": {"distance_nmi": 100}})["result"]["sensitivity"]), 3)
        for payload in ({"condition": {"mach": .99}}, {"action": "unknown"}, {"action": "validate", "dataset": {}}):
            self.assertFalse(self.calculate(payload)["ok"])

    def test_request_format_and_size(self):
        for body, headers, expected in (
            ("broken", {"Content-Type": "application/json"}, 200),
            (b"\xff", {"Content-Type": "application/json"}, 400),
            ("{}", {"Content-Type": "text/plain"}, 415),
            (None, {"Content-Type": "application/json", "Content-Length": str(MAX_REQUEST_BYTES + 1)}, 413),
        ):
            status, response, _ = self.request("POST", "/api/calculate", body, headers)
            self.assertEqual(status, expected)
            self.assertFalse(json.loads(response)["ok"])

    def test_foreign_origin_and_host_are_rejected(self):
        status, _, _ = self.request("POST", "/api/calculate", "{}", {"Content-Type": "application/json", "Origin": "https://example.com"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("GET", "/api/runtime", headers={"Host": "example.com"})
        self.assertEqual(status, 403)

    def test_project_files_are_not_served(self):
        for path in ("/b777_calculator.py", "/.git/config", "/../README.md", "/python/"):
            status, _, _ = self.request("GET", path)
            self.assertEqual(status, 404)

    def test_cli_outputs_json_and_failure_status(self):
        valid = subprocess.run([sys.executable, str(ROOT / "b777_calculator.py"), "snapshot"], capture_output=True, text=True)
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertTrue(json.loads(valid.stdout)["ok"])
        invalid = subprocess.run([sys.executable, str(ROOT / "b777_calculator.py"), "snapshot", "--mach", ".99"], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 1)
        self.assertFalse(json.loads(invalid.stdout)["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
