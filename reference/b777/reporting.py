"""Reproducible exports with model settings, inputs, and traceability."""

import csv
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .model import PerformanceModel
from .simulation import CruiseResult


def write_json(path: str | Path, model: PerformanceModel, result: dict) -> None:
    payload = {
        "created_utc": datetime.now(UTC).isoformat(),
        "model": model.provenance(),
        "result": result,
    }
    Path(path).write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_cruise_csv(path: str | Path, result: CruiseResult) -> None:
    """Trace export; accompanying JSON contains assumptions and provenance."""
    rows = [asdict(point) for point in result.points]
    with Path(path).open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def cruise_figure(result: CruiseResult):
    """Return a Figure without selecting a backend or opening a window."""
    from matplotlib.figure import Figure

    figure = Figure(figsize=(10, 6), facecolor="#f5f7fb", layout="constrained")
    axes = figure.subplots(2, 1, sharex=True)
    x = [point.distance_nmi for point in result.points]
    axes[0].plot(
        x,
        [point.remaining_fuel_kg / 1000 for point in result.points],
        color="#157f83",
        linewidth=2.3,
    )
    axes[0].axhline(
        result.request.protected_fuel_kg / 1000,
        color="#b56b21",
        linestyle="--",
        label="User-selected protected fuel",
    )
    axes[0].set_ylabel("Remaining fuel (tonnes)")
    axes[0].legend(loc="best", frameon=False)
    axes[1].plot(
        x, [point.fuel_flow_kg_h / 1000 for point in result.points], color="#2463b2", linewidth=2.3
    )
    axes[1].set_ylabel("Total fuel flow (tonnes/hour)")
    axes[1].set_xlabel("Cruise distance (nautical miles)")
    for ax in axes:
        ax.set_facecolor("#ffffff")
        ax.grid(alpha=0.18)
        ax.spines[["top", "right"]].set_visible(False)
    figure.suptitle(
        "B777 Performance Lab | Cruise segment\n"
        f"{result.stop_reason} · {result.points[-1].distance_nmi:,.0f} / "
        f"{result.request.distance_nmi:,.0f} nmi\n"
        "Model estimate · no independent B777 fuel validation",
        fontsize=14,
    )
    return figure


def save_cruise_plot(path: str | Path, result: CruiseResult) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    figure = cruise_figure(result)
    FigureCanvasAgg(figure)
    figure.savefig(path, dpi=160, bbox_inches="tight", pad_inches=0.15)
