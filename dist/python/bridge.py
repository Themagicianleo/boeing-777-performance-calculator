"""JSON interface shared by CPython tests and the Pyodide web worker."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from b777.model import FlightCondition, ModelSettings, PerformanceModel
from b777.simulation import CruiseRequest, simulate_cruise, compare_conditions, cruise_sensitivity
from b777.validation import evaluate_observations


def dispatch(request_json: str) -> str:
    try:
        request = json.loads(request_json)
        if not isinstance(request, dict):
            raise ValueError("Request must be an object")
        settings = ModelSettings(**request.get("settings", {}))
        condition = FlightCondition(**request.get("condition", {}))
        model = PerformanceModel(settings)
        action = request.get("action", "snapshot")
        if action == "snapshot":
            result = model.snapshot(condition, request.get("thrust_kn")).to_dict()
        elif action == "compare":
            result = {"base_condition": asdict(condition), "comparisons": compare_conditions(model, condition)}
        elif action in ("cruise", "sensitivity"):
            cruise_request = CruiseRequest(condition=condition, **request.get("cruise", {}))
            if action == "cruise":
                result = simulate_cruise(model, cruise_request).to_dict()
            else:
                result = {"request": asdict(cruise_request), "sensitivity": cruise_sensitivity(model, cruise_request)}
        elif action == "validate":
            result = evaluate_observations(model, request.get("dataset"))
        else:
            raise ValueError("Unknown experiment")
        return json.dumps({"ok": True, "created_utc": datetime.now(timezone.utc).isoformat(),
                           "model": model.provenance(), "result": result}, allow_nan=False)
    except (ValueError, TypeError, KeyError) as error:
        return json.dumps({"ok": False, "error": str(error)})
