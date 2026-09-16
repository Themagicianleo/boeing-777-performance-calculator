"""Dry-air ISA in pressure/geopotential altitude, SI internally.

At a fixed pressure altitude, pressure does not vary with ISA deviation.
This avoids conflating a warmer atmospheric column with pressure altitude.
"""

import math
from dataclasses import dataclass

G = 9.80665
R = 287.05287
GAMMA = 1.4
FT = 0.3048
KNOT = 1852.0 / 3600.0
P0 = 101325.0
T0 = 288.15
LAPSE = 0.0065
T11 = 216.65
P11 = P0 * (T11 / T0) ** (G / (R * LAPSE))


def bounded(name: str, value: float, low: float, high: float) -> None:
    """Reject invalid values rather than silently clipping them."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and between {low:g} and {high:g}")


@dataclass(frozen=True)
class Atmosphere:
    pressure_pa: float
    temperature_k: float
    isa_temperature_k: float
    density_kg_m3: float
    speed_of_sound_m_s: float


def atmosphere(altitude_ft: float, isa_delta_c: float = 0.0) -> Atmosphere:
    """ISA pressure plus measured temperature deviation, through 20 km."""
    bounded("pressure altitude (ft)", altitude_ft, 0, 20000 / FT)
    bounded("ISA deviation (C)", isa_delta_c, -40, 40)
    height = altitude_ft * FT
    isa_t = T0 - LAPSE * min(height, 11000.0)
    if height <= 11000.0:
        pressure = P0 * (isa_t / T0) ** (G / (R * LAPSE))
    else:
        pressure = P11 * math.exp(-G * (height - 11000.0) / (R * T11))
    temperature = isa_t + isa_delta_c
    return Atmosphere(
        pressure,
        temperature,
        isa_t,
        pressure / (R * temperature),
        math.sqrt(GAMMA * R * temperature),
    )


def pressure_altitude_ft(pressure_hpa: float) -> float:
    """Invert ISA pressure. Input is local static pressure, never QNH."""
    bounded("local static pressure (hPa)", pressure_hpa, 55, 1013.25)
    pressure = pressure_hpa * 100.0
    if pressure >= P11:
        height = T0 / LAPSE * (1 - (pressure / P0) ** (R * LAPSE / G))
    else:
        height = 11000 - R * T11 / G * math.log(pressure / P11)
    return height / FT


def groundspeed(tas_kt: float, headwind_kt: float, crosswind_kt: float) -> float:
    """Wind triangle for holding a ground track; signed along/across-track wind.

    Positive headwind opposes travel. Either crosswind sign has the same
    speed penalty; the required crab angle changes sign.
    """
    bounded("TAS (kt)", tas_kt, 1, 1000)
    bounded("headwind (kt)", headwind_kt, -400, 400)
    bounded("crosswind (kt)", crosswind_kt, -400, 400)
    if abs(crosswind_kt) >= tas_kt:
        raise ValueError("Crosswind is too strong to hold the requested track")
    speed = math.sqrt(tas_kt**2 - crosswind_kt**2) - headwind_kt
    if speed <= 0:
        raise ValueError("Wind prevents forward progress along the requested track")
    return speed
