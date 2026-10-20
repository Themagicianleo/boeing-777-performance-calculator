"""Fit the model to Boeing's published 777-300ER payload/range chart.

Each chart point is a mission: brake-release weight, zero-fuel weight and still-air
range at Mach 0.84 with 2,000 ft step climbs. The model is cruise-only, so a mission
is represented as

    trip fuel = (TOW - ZFW - allowance) / (1 + contingency)
    range     = integral of best specific range over the trip-fuel mass interval

where the allowance is a fitted fixed mass (take-off, climb and descent extras plus
fixed reserves such as alternate and hold) and the contingency fraction is an
assumption. Two correction forms are fitted: a fuel-flow multiplier and a drag
multiplier. Standard library only; run with `python calibration/calibrate.py`.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dist" / "python"))
from b777.model import MTOW_KG, FlightCondition, ModelSettings, PerformanceModel  # noqa: E402

LB = 0.45359237
MACH = 0.84
LEVELS = range(29000, 41001, 2000)
MASS_STEP = 150.0
CONTINGENCY = 0.05


def specific_range_table(model, low, high):
    """Best still-air nmi per kg at each mass, over 2,000 ft levels that pass screening."""
    masses, best = [], []
    mass = low
    while mass <= high + 1e-9:
        rates = []
        for level in LEVELS:
            snap = model.snapshot(FlightCondition(mass_kg=min(mass, MTOW_KG), altitude_ft=level, mach=MACH))
            if snap.screening_passed:
                rates.append(snap.tas_kt / snap.fuel_total_kg_h)
        if not rates:
            raise ValueError(f"No screened cruise level at {mass:.0f} kg")
        masses.append(mass)
        best.append(max(rates))
        mass += MASS_STEP
    cumulative = [0.0]
    for i in range(1, len(best)):
        cumulative.append(cumulative[-1] + 0.5 * (best[i] + best[i - 1]) * MASS_STEP)
    return masses, cumulative


def integral(table, start, end):
    masses, cumulative = table

    def at(mass):
        position = (mass - masses[0]) / MASS_STEP
        i = max(0, min(len(masses) - 2, int(position)))
        return cumulative[i] + (cumulative[i + 1] - cumulative[i]) * (position - i)

    return at(end) - at(start)


def mission_integrals(table, points, allowance, contingency):
    values = []
    for p in points:
        tow, zfw = p["tow_kg"], p["zfw_kg"]
        trip = (tow - zfw - allowance) / (1 + contingency)
        values.append(integral(table, tow - trip, tow) if trip > 0 else 0.0)
    return values


def fit_fuel_scale(table, points, contingency):
    """Least-squares range fit; for a fixed allowance the best 1/k has a closed form."""
    best = None
    for allowance in range(0, 30001, 50):
        integrals = mission_integrals(table, points, allowance, contingency)
        u = sum(i * p["range_nmi"] for i, p in zip(integrals, points)) / sum(i * i for i in integrals)
        rms = math.sqrt(sum((u * i - p["range_nmi"]) ** 2 for i, p in zip(integrals, points)) / len(points))
        if best is None or rms < best["rms_nmi"]:
            best = {"fuel_scale": 1 / u, "allowance_kg": allowance, "rms_nmi": rms,
                    "model_range_nmi": [u * i for i in integrals]}
    return best


def fit_drag_scale(points, low, high, contingency):
    best = None
    for step in range(0, 61):
        scale = round(0.70 + 0.005 * step, 3)
        table = specific_range_table(PerformanceModel(ModelSettings(drag_scale=scale, calibrated=False)), low, high)
        for allowance in range(0, 30001, 250):
            ranges = mission_integrals(table, points, allowance, contingency)
            rms = math.sqrt(sum((r - p["range_nmi"]) ** 2 for r, p in zip(ranges, points)) / len(points))
            if best is None or rms < best["rms_nmi"]:
                best = {"drag_scale": scale, "allowance_kg": allowance, "rms_nmi": rms, "model_range_nmi": ranges}
    return best


def main():
    data = json.loads((ROOT / "calibration" / "boeing_777-300er_payload_range.json").read_text())
    points = [dict(p, tow_kg=min(p["brake_release_lb"] * LB, MTOW_KG), zfw_kg=p["zfw_lb"] * LB) for p in data["points"]]
    low = math.floor(min(p["zfw_kg"] for p in points) / 1000) * 1000
    high = MTOW_KG
    table = specific_range_table(PerformanceModel(ModelSettings(calibrated=False)), low, high)

    fuel = fit_fuel_scale(table, points, CONTINGENCY)
    sensitivity = {f"{c:.2f}": {k: round(v, 4) if isinstance(v, float) else v
                                for k, v in fit_fuel_scale(table, points, c).items() if k != "model_range_nmi"}
                   for c in (0.0, 0.05, 0.10)}
    drag = fit_drag_scale(points, low, high, CONTINGENCY)
    uncalibrated = mission_integrals(table, points, fuel["allowance_kg"], CONTINGENCY)

    rows = [{"label": p["label"], "boeing_nmi": p["range_nmi"],
             "uncalibrated_nmi": round(u), "fuel_scale_fit_nmi": round(f), "drag_scale_fit_nmi": round(d)}
            for p, u, f, d in zip(points, uncalibrated, fuel["model_range_nmi"], drag["model_range_nmi"])]
    result = {
        "source": data["source"],
        "assumptions": {"contingency_fraction": CONTINGENCY, "cruise_mach": MACH,
                        "levels_ft": [LEVELS.start, LEVELS.stop - 1, LEVELS.step],
                        "mission": "cruise-equivalent; fixed allowance carried as unburned fuel"},
        "fuel_scale_fit": {k: round(v, 4) if isinstance(v, float) else v for k, v in fuel.items() if k != "model_range_nmi"},
        "drag_scale_fit": {k: round(v, 4) if isinstance(v, float) else v for k, v in drag.items() if k != "model_range_nmi"},
        "contingency_sensitivity": sensitivity,
        "points": rows,
    }
    (ROOT / "calibration" / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
