"""Explicit aerodynamic model and a version-checked OpenAP engine adapter."""

from dataclasses import asdict, dataclass

from .atmosphere import KNOT, G, atmosphere, bounded, groundspeed

OPENAP_VERSION = "2.6.1"
AIRCRAFT = "B77W"
ENGINE = "GE90-115B"
MTOW_KG = 351530.0  # Boeing product specification, not OpenAP's rounded 351500.
NOTICE = (
    "Research estimate; no independent B777 fuel-flow validation has been supplied. "
    "OpenAP 2.6.1 uses a generic engine-scaled fuel curve for B77W. "
    "Not for dispatch, cockpit use, or operational fuel planning."
)


@dataclass(frozen=True)
class FlightCondition:
    """Clean, steady level flight; mass includes remaining fuel."""

    mass_kg: float = 250000.0
    altitude_ft: float = 35000.0
    mach: float = 0.84
    isa_delta_c: float = 0.0
    headwind_kt: float = 0.0
    crosswind_kt: float = 0.0

    def validate(self) -> None:
        # These are research scope limits, not a certified flight envelope.
        bounded("aircraft mass (kg)", self.mass_kg, 167800, MTOW_KG)
        bounded("pressure altitude (ft)", self.altitude_ft, 20000, 41000)
        bounded("Mach", self.mach, 0.70, 0.84)
        bounded("ISA deviation (C)", self.isa_delta_c, -25, 15)
        bounded("headwind (kt)", self.headwind_kt, -400, 400)
        bounded("crosswind (kt)", self.crosswind_kt, -400, 400)


@dataclass(frozen=True)
class ModelSettings:
    """Sensitivity factors are hypotheses, not confidence intervals."""

    fuel_scale: float = 1.0
    drag_scale: float = 1.0
    tsfc_kg_kn_h: float | None = None  # None selects OpenAP.

    def validate(self) -> None:
        bounded("fuel scale", self.fuel_scale, 0.5, 1.5)
        bounded("drag scale", self.drag_scale, 0.7, 1.3)
        if self.tsfc_kg_kn_h is not None:
            bounded("TSFC (kg/kN/h)", self.tsfc_kg_kn_h, 1, 200)


@dataclass(frozen=True)
class Snapshot:
    condition: FlightCondition
    temperature_c: float
    pressure_hpa: float
    density_kg_m3: float
    tas_kt: float
    groundspeed_kt: float
    lift_coefficient: float
    drag_kn: float
    lift_to_drag: float
    total_thrust_kn: float
    isa_reference_max_thrust_kn: float
    isa_reference_margin_kn: float
    fuel_total_kg_h: float
    fuel_per_engine_kg_h: float
    effective_tsfc_kg_kn_h: float
    fuel_kg_nmi: float
    longitudinal_acceleration_m_s2: float
    screening_passed: bool
    engine_model: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class PerformanceModel:
    """B77W data + parabolic drag + OpenAP fuel(total net thrust).

    The separately displayed maximum thrust is an ISA reference at the same
    Mach and pressure altitude. Non-ISA engine availability is not established.
    This model intentionally adds no unsupported engine-temperature correction.
    """

    def __init__(self, settings: ModelSettings | None = None):
        from .engine import FuelFlow, Thrust

        self.settings = settings or ModelSettings()
        self.settings.validate()
        self.aircraft = {"wing": {"area": 436.8}, "engine": {"number": 2}}
        self.engine = {"max_thrust": 513900.0}
        self.polar = {"cd0": 0.024, "k": 0.043, "e": 0.765}
        self.wing_area_m2 = 436.8
        self.fuel_model = FuelFlow()
        self.thrust_model = Thrust()

    def snapshot(
        self, condition: FlightCondition, total_thrust_kn: float | None = None
    ) -> Snapshot:
        condition.validate()
        air = atmosphere(condition.altitude_ft, condition.isa_delta_c)
        tas_m_s = condition.mach * air.speed_of_sound_m_s
        tas_kt = tas_m_s / KNOT
        gs = groundspeed(tas_kt, condition.headwind_kt, condition.crosswind_kt)
        q_area = 0.5 * air.density_kg_m3 * tas_m_s**2 * self.wing_area_m2
        weight_n = condition.mass_kg * G
        cl = weight_n / q_area
        cd = self.polar["cd0"] + self.polar["k"] * cl**2
        drag_kn = q_area * cd * self.settings.drag_scale / 1000.0
        thrust_kn = drag_kn if total_thrust_kn is None else total_thrust_kn
        bounded("total net thrust (kN)", thrust_kn, 1, self.engine["max_thrust"] * 2 / 1000.0)

        if self.settings.tsfc_kg_kn_h is None:
            fuel_kg_h = float(self.fuel_model.at_thrust(thrust_kn * 1000)) * 3600
            model_name = "OpenAP 2.6.1 generic curve scaled to GE90-115B"
        else:
            fuel_kg_h = self.settings.tsfc_kg_kn_h * thrust_kn
            model_name = "User-supplied constant TSFC"
        fuel_kg_h *= self.settings.fuel_scale
        bounded("model fuel flow (kg/h)", fuel_kg_h, 0.001, 100000)

        isa_tas = condition.mach * atmosphere(condition.altitude_ft).speed_of_sound_m_s / KNOT
        max_thrust_kn = (
            float(self.thrust_model.cruise(tas=isa_tas, alt=condition.altitude_ft, dT=0)) / 1000.0
        )
        bounded("ISA reference thrust (kN)", max_thrust_kn, 0.001, 2000)
        margin = max_thrust_kn - thrust_kn
        notes = [NOTICE, "Clean parabolic drag; no explicit wave drag or buffet/stall model."]
        if condition.isa_delta_c != 0:
            notes.append(
                "Non-ISA: atmospheric/speed effects included; engine thermal effects "
                "are not. Displayed available thrust is an ISA reference only."
            )
        if cl > 0.7:
            notes.append("CL exceeds the research screening threshold of 0.70.")
        if margin < 0:
            notes.append("Requested thrust exceeds the modeled ISA reference maximum.")
        acceleration = (thrust_kn - drag_kn) * 1000 / condition.mass_kg
        if total_thrust_kn is not None and abs(thrust_kn - drag_kn) > 0.01 * drag_kn:
            notes.append("Manual thrust does not balance drag: instantaneous snapshot only.")
        if self.settings != ModelSettings():
            notes.append("User model settings differ from the uncalibrated baseline.")
        return Snapshot(
            condition,
            air.temperature_k - 273.15,
            air.pressure_pa / 100,
            air.density_kg_m3,
            tas_kt,
            gs,
            cl,
            drag_kn,
            weight_n / (drag_kn * 1000),
            thrust_kn,
            max_thrust_kn,
            margin,
            fuel_kg_h,
            fuel_kg_h / 2,
            fuel_kg_h / thrust_kn,
            fuel_kg_h / gs,
            acceleration,
            cl <= 0.7 and margin >= 0,
            model_name,
            tuple(notes),
        )

    def provenance(self) -> dict:
        return {
            "application_version": "3.0.0-web",
            "openap_reference_version": OPENAP_VERSION,
            "implementation": "scalar Python adaptation; see THIRD_PARTY_NOTICES.md",
            "aircraft": AIRCRAFT,
            "engine": ENGINE,
            "wing_area_m2": self.wing_area_m2,
            "drag_polar": self.polar,
            "settings": asdict(self.settings),
            "mtow_kg": MTOW_KG,
            "status": "unvalidated_against_independent_B777_measurements",
            "fuel_model_family": "generic_scaled"
            if self.settings.tsfc_kg_kn_h is None
            else "constant_user_tsfc",
            "notice": NOTICE,
        }
