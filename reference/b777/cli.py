"""Command line entry points; no UI imports in the calculation path."""

import argparse
import json
from pathlib import Path

from .atmosphere import atmosphere, pressure_altitude_ft
from .model import FlightCondition, ModelSettings, PerformanceModel
from .reporting import save_cruise_plot, write_cruise_csv, write_json
from .simulation import CruiseRequest, compare_conditions, cruise_sensitivity, simulate_cruise
from .validation import evaluate_observations


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="B777 Performance Lab — research cruise estimates")
    result.add_argument(
        "command",
        nargs="?",
        default="snapshot",
        choices=("snapshot", "cruise", "compare", "sensitivity", "validate", "gui"),
    )
    result.add_argument("--gui", action="store_true", help="Open the desktop interface")
    result.add_argument("--weight-kg", type=float, default=250000)
    result.add_argument("--altitude-ft", type=float, default=35000, help="Pressure altitude")
    temperature = result.add_mutually_exclusive_group()
    temperature.add_argument("--isa-delta-c", type=float, default=0)
    temperature.add_argument(
        "--temperature-c", type=float, help="Outside/static air temperature, not TAT"
    )
    result.add_argument(
        "--pressure-hpa", type=float, help="Local static pressure; replaces pressure altitude"
    )
    result.add_argument("--mach", type=float, default=0.84)
    result.add_argument("--headwind-kt", type=float, default=0)
    result.add_argument("--crosswind-kt", type=float, default=0)
    result.add_argument("--thrust-kn", type=float, help="Manual TOTAL net thrust; snapshot only")
    result.add_argument(
        "--tsfc", type=float, help="Optional constant TSFC (kg/kN/h); otherwise OpenAP"
    )
    result.add_argument("--fuel-scale", type=float, default=1)
    result.add_argument("--drag-scale", type=float, default=1)
    result.add_argument("--distance-nmi", type=float, default=2000)
    result.add_argument("--zero-fuel-mass-kg", type=float, default=200000)
    result.add_argument("--protected-fuel-kg", type=float, default=8000)
    result.add_argument("--step-seconds", type=float, default=30)
    result.add_argument("--data", type=Path, help="Reference observations JSON for validate")
    result.add_argument("--output", type=Path, help="Reproducible JSON output")
    result.add_argument(
        "--csv", type=Path, help="Cruise trace; also writes metadata JSON alongside"
    )
    result.add_argument("--plot", type=Path, help="Cruise plot PNG/PDF")
    return result


def main() -> None:
    argument_parser = parser()
    args = argument_parser.parse_args()
    if args.gui or args.command == "gui":
        from .gui import launch

        launch()
        return
    try:
        if args.thrust_kn is not None and args.command != "snapshot":
            raise ValueError("Manual thrust is supported only for instantaneous snapshots")
        if (args.csv or args.plot) and args.command != "cruise":
            raise ValueError("--csv and --plot require the cruise command")
        model = PerformanceModel(ModelSettings(args.fuel_scale, args.drag_scale, args.tsfc))
        altitude = (
            pressure_altitude_ft(args.pressure_hpa)
            if args.pressure_hpa is not None
            else args.altitude_ft
        )
        delta = (
            args.temperature_c + 273.15 - atmosphere(altitude).isa_temperature_k
            if args.temperature_c is not None
            else args.isa_delta_c
        )
        condition = FlightCondition(
            args.weight_kg, altitude, args.mach, delta, args.headwind_kt, args.crosswind_kt
        )
        request = CruiseRequest(
            condition,
            args.distance_nmi,
            args.zero_fuel_mass_kg,
            args.protected_fuel_kg,
            args.step_seconds,
        )
        if args.command == "snapshot":
            result = model.snapshot(condition, args.thrust_kn).to_dict()
        elif args.command == "compare":
            result = {
                "base_condition": condition.__dict__,
                "comparisons": compare_conditions(model, condition),
            }
        elif args.command == "sensitivity":
            result = {
                "request": request.__dict__ | {"condition": condition.__dict__},
                "sensitivity": cruise_sensitivity(model, request),
            }
        elif args.command == "validate":
            if args.data is None:
                raise ValueError(
                    "validate requires --data with independently sourced reference observations"
                )
            result = evaluate_observations(model, json.loads(args.data.read_text(encoding="utf-8")))
        else:
            cruise = simulate_cruise(model, request)
            result = cruise.to_dict()
            if args.csv:
                write_cruise_csv(args.csv, cruise)
                write_json(str(args.csv) + ".metadata.json", model, result)
            if args.plot:
                save_cruise_plot(args.plot, cruise)
        if args.output:
            write_json(args.output, model, result)
            print(f"Saved {args.output}")
        else:
            print(
                json.dumps(
                    {"model": model.provenance(), "result": result}, indent=2, allow_nan=False
                )
            )
    except (ValueError, OSError, RuntimeError) as error:
        argument_parser.error(str(error))


if __name__ == "__main__":
    main()
