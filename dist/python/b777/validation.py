"""Empirical comparison, with flight-level separation of fit and evaluation."""

import math

from .atmosphere import bounded
from .model import FlightCondition, PerformanceModel


def error_metrics(predicted: list[float], observed: list[float]) -> dict:
    if not observed or len(predicted) != len(observed):
        raise ValueError("Predicted/observed arrays must have the same nonzero length")
    for value in predicted + observed:
        bounded("fuel-flow observation/prediction", value, 0.001, 100000)
    residuals = [p - o for p, o in zip(predicted, observed, strict=True)]
    count = len(observed)
    return {
        "count": count,
        "mae_kg_h": sum(abs(r) for r in residuals) / count,
        "rmse_kg_h": math.sqrt(sum(r * r for r in residuals) / count),
        "bias_kg_h": sum(residuals) / count,
        "mape_percent": 100
        * sum(abs(r) / o for r, o in zip(residuals, observed, strict=True))
        / count,
    }


def evaluate_observations(model: PerformanceModel, dataset: dict) -> dict:
    """Fit one multiplier to training rows; evaluate only on distinct flights.

    JSON records need: id, flight_id, split ('train'/'test'), condition (the
    FlightCondition fields), and observed_fuel_kg_h (TOTAL both engines).
    Unknown or synthetic provenance can exercise code but cannot establish
    aircraft accuracy. Nothing in this routine authenticates supplied records.
    """
    if not isinstance(dataset, dict) or dataset.get("aircraft") != "B77W":
        raise ValueError("Dataset must identify aircraft B77W")
    if dataset.get("engine") != "GE90-115B":
        raise ValueError("Dataset must identify engine GE90-115B")
    kind = dataset.get("source_type")
    if kind not in ("measured", "simulator", "synthetic"):
        raise ValueError("source_type must be measured, simulator, or synthetic")
    if not isinstance(dataset.get("source"), str) or not dataset["source"].strip():
        raise ValueError("Provide a traceable source description")
    records = dataset.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("No reference observations supplied; aircraft accuracy is unknown")
    ids: set[str] = set()
    flights = {"train": set(), "test": set()}
    splits = {"train": [], "test": []}
    rows = []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each observation must be an object")
        ident, flight_id, split = record.get("id"), record.get("flight_id"), record.get("split")
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError("Observation ids must be nonempty unique strings")
        if (
            not isinstance(flight_id, str)
            or not flight_id.strip()
            or not isinstance(split, str)
            or split not in splits
        ):
            raise ValueError("Each row needs flight_id and split train/test")
        ids.add(ident)
        flights[split].add(flight_id)
        if not isinstance(record.get("condition"), dict):
            raise ValueError("Each row needs a complete condition object")
        required = {"mass_kg", "altitude_ft", "mach", "isa_delta_c"}
        if not required.issubset(record["condition"]):
            raise ValueError("Reference rows require mass, altitude, Mach, and ISA deviation")
        try:
            condition = FlightCondition(**record["condition"])
        except TypeError as error:
            raise ValueError(f"Invalid condition fields: {error}") from error
        observation = record.get("observed_fuel_kg_h")
        bounded("observed total fuel (kg/h)", observation, 1, 50000)
        prediction = model.snapshot(condition).fuel_total_kg_h
        row = {
            "id": ident,
            "flight_id": flight_id,
            "split": split,
            "predicted_kg_h": prediction,
            "observed_kg_h": observation,
        }
        splits[split].append(row)
        rows.append(row)
    if flights["train"] & flights["test"]:
        raise ValueError("Train/test leakage: a flight_id occurs in both splits")
    if any(len(splits[key]) < 2 for key in splits):
        raise ValueError("Supply at least two observations in each split")
    training = splits["train"]
    scale = sum(r["predicted_kg_h"] * r["observed_kg_h"] for r in training) / sum(
        r["predicted_kg_h"] ** 2 for r in training
    )
    bounded("fitted relative scale", scale, 0.5, 1.5)
    metrics = {}
    for split, values in splits.items():
        observed = [r["observed_kg_h"] for r in values]
        predicted = [r["predicted_kg_h"] for r in values]
        metrics[split] = {
            "baseline": error_metrics(predicted, observed),
            "fitted": error_metrics([scale * p for p in predicted], observed),
            "flight_count": len(flights[split]),
        }
    return {
        "source": dataset["source"],
        "source_type": kind,
        "relative_fitted_scale": scale,
        "absolute_fuel_scale": model.settings.fuel_scale * scale,
        "metrics": metrics,
        "rows": rows,
        "scope": "Only the supplied conditions and flights; no fleet-wide accuracy claim.",
        "qualification": "Source type is user-declared, not independently authenticated. "
        "A scalar fit cannot establish an engine map. Synthetic or simulator "
        "data do not establish real-aircraft accuracy.",
    }
