"""Mass-depleting cruise integration and controlled comparative experiments."""

from dataclasses import asdict, dataclass, field, replace

from .atmosphere import bounded
from .model import FlightCondition, PerformanceModel


@dataclass(frozen=True)
class CruiseRequest:
    condition: FlightCondition = field(default_factory=FlightCondition)
    distance_nmi: float = 2000.0
    zero_fuel_mass_kg: float = 200000.0
    protected_fuel_kg: float = 8000.0
    step_seconds: float = 30.0

    def validate(self) -> None:
        self.condition.validate()
        bounded("cruise distance (nmi)", self.distance_nmi, 0.01, 10000)
        bounded("zero-fuel mass (kg)", self.zero_fuel_mass_kg, 167800, self.condition.mass_kg)
        bounded(
            "protected fuel (kg)",
            self.protected_fuel_kg,
            0,
            self.condition.mass_kg - self.zero_fuel_mass_kg,
        )
        bounded("integration step (s)", self.step_seconds, 1, 300)
        if self.mass_floor >= self.condition.mass_kg:
            raise ValueError("No fuel is available above the selected protected-fuel floor")

    @property
    def mass_floor(self) -> float:
        return self.zero_fuel_mass_kg + self.protected_fuel_kg


@dataclass(frozen=True)
class CruisePoint:
    elapsed_h: float
    distance_nmi: float
    mass_kg: float
    remaining_fuel_kg: float
    burned_fuel_kg: float
    fuel_flow_kg_h: float


@dataclass(frozen=True)
class CruiseResult:
    request: CruiseRequest
    completed: bool
    stop_reason: str
    points: tuple[CruisePoint, ...]
    warnings: tuple[str, ...]

    @property
    def fuel_burn_kg(self) -> float:
        return self.points[-1].burned_fuel_kg

    def to_dict(self) -> dict:
        result = asdict(self)
        result["fuel_burn_kg"] = self.fuel_burn_kg
        return result


def simulate_cruise(model: PerformanceModel, request: CruiseRequest) -> CruiseResult:
    """Midpoint integration of dm/dt=-fuel(m) at fixed Mach/altitude/weather.

    Fuel-floor crossing is resolved by bisection in time, not by silently
    clipping fuel or flying beyond the floor. This is only a cruise segment.
    """
    request.validate()
    initial = model.snapshot(request.condition)
    warnings = list(initial.warnings)
    warnings.append("Cruise segment only: excludes taxi, climb, descent, APU and reserve policy.")
    if not initial.screening_passed:
        raise ValueError(
            "Initial state fails the model's CL/ISA-thrust screening; "
            "inspect a snapshot or reduce mass/altitude"
        )
    gs = initial.groundspeed_kt
    mass = request.condition.mass_kg
    elapsed = 0.0
    points: list[CruisePoint] = []

    def append_point() -> None:
        snapshot = model.snapshot(replace(request.condition, mass_kg=mass))
        points.append(
            CruisePoint(
                elapsed,
                elapsed * gs,
                mass,
                mass - request.zero_fuel_mass_kg,
                request.condition.mass_kg - mass,
                snapshot.fuel_total_kg_h,
            )
        )

    append_point()
    total_h = request.distance_nmi / gs
    while elapsed < total_h - 1e-12:
        rate = model.snapshot(replace(request.condition, mass_kg=mass)).fuel_total_kg_h
        dt = min(request.step_seconds / 3600, total_h - elapsed)

        def burn_over(hours: float, start_mass: float = mass, start_rate: float = rate) -> float:
            # Avoid evaluating the midpoint outside the permitted mass domain
            # during event bracketing; accepted steps have midpoints above floor.
            midpoint_mass = max(request.mass_floor, start_mass - start_rate * hours / 2)
            midpoint_rate = model.snapshot(
                replace(request.condition, mass_kg=midpoint_mass)
            ).fuel_total_kg_h
            return midpoint_rate * hours

        burn = burn_over(dt)
        if burn >= mass - request.mass_floor:
            low, high = 0.0, dt
            for _ in range(45):
                middle = (low + high) / 2
                if burn_over(middle) < mass - request.mass_floor:
                    low = middle
                else:
                    high = middle
            elapsed += (low + high) / 2
            mass = request.mass_floor
            append_point()
            completed = elapsed >= total_h - 1e-9
            return CruiseResult(
                request,
                completed,
                "Requested distance reached" if completed else "Protected fuel floor reached",
                tuple(points),
                tuple(warnings),
            )
        mass -= burn
        elapsed += dt
        append_point()
    return CruiseResult(request, True, "Requested distance reached", tuple(points), tuple(warnings))


def compare_conditions(model: PerformanceModel, base: FlightCondition) -> list[dict]:
    """One variable at a time; failed research screens remain visible."""
    scenarios = [
        ("Baseline", base),
        ("Mass +10,000 kg", replace(base, mass_kg=base.mass_kg + 10000)),
        ("Headwind +50 kt", replace(base, headwind_kt=base.headwind_kt + 50)),
        ("Crosswind +50 kt", replace(base, crosswind_kt=base.crosswind_kt + 50)),
        ("ISA deviation +10 C", replace(base, isa_delta_c=base.isa_delta_c + 10)),
    ]
    rows = []
    for name, condition in scenarios:
        try:
            result = model.snapshot(condition)
            rows.append(
                {
                    "scenario": name,
                    "fuel_kg_h": result.fuel_total_kg_h,
                    "fuel_kg_nmi": result.fuel_kg_nmi,
                    "groundspeed_kt": result.groundspeed_kt,
                    "screening_passed": result.screening_passed,
                }
            )
        except ValueError as error:
            rows.append({"scenario": name, "error": str(error)})
    return rows


def cruise_sensitivity(
    model: PerformanceModel, request: CruiseRequest, fractional_change: float = 0.10
) -> list[dict]:
    """Rerun integration for assumed fuel bias; NOT a statistical error bound."""
    bounded("assumed fractional fuel change", fractional_change, 0.001, 0.3)
    rows = []
    for factor in (1 - fractional_change, 1.0, 1 + fractional_change):
        settings = replace(model.settings, fuel_scale=model.settings.fuel_scale * factor)
        result = simulate_cruise(PerformanceModel(settings), request)
        rows.append(
            {
                "relative_fuel_factor": factor,
                "completed": result.completed,
                "distance_nmi": result.points[-1].distance_nmi,
                "fuel_burn_kg": result.fuel_burn_kg,
                "label": "assumption sensitivity, not confidence interval",
            }
        )
    return rows
