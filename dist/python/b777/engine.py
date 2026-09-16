"""Scalar B77W subset adapted from OpenAP 2.6.1 (LGPL-3.0).

OpenAP: Junzi Sun and contributors, https://github.com/junzis/openap.
Modified for browser use: scalar math, fixed B77W/GE90-115B configuration,
ISA-only cruise thrust within 20,000–41,000 ft. No NumPy/Pandas dependencies.
See the shipped license and THIRD_PARTY_NOTICES.md. This does not add fidelity.
"""
import math


class FuelFlow:
    """OpenAP generic curve scaled by GE90-115B takeoff fuel-flow parameter."""

    def at_thrust(self, total_ac_thrust: float) -> float:
        ratio = total_ac_thrust / 2 / 513900.0
        ratio = ((math.log1p(math.exp(50 * (ratio - 0.03)))
                  - math.log1p(math.exp(45 * (ratio - 1.2))))
                 / math.log1p(math.exp(50))) + 0.03
        c1, c2, c3 = 0.937564901246902, 1.9767611682280135, 1.3954794843472482
        return 2 * 4.6 * (c1 - math.exp(-c2 * (
            ratio * math.exp(c3 * ratio) - math.log(c1) / c2)))


def _isa(height_m: float) -> tuple[float, float, float]:
    """OpenAP's atmosphere constants retained for thrust-reference parity."""
    temperature = max(288.15 - 0.0065 * height_m, 216.65)
    density = 1.225 * (temperature / 288.15) ** 4.256848030018761
    density *= math.exp(-max(0.0, height_m - 11000) / 6341.552161)
    return density * 287.05287 * temperature, density, temperature


def _cas(speed_m_s: float, height_m: float) -> float:
    pressure, density, _ = _isa(height_m)
    impact = pressure * ((1 + density * speed_m_s**2 / (7 * pressure))**3.5 - 1)
    return math.sqrt(7 * 101325 / 1.225 * ((impact / 101325 + 1)**(2/7) - 1))


class Thrust:
    """ISA cruise reference; no claim of non-ISA engine availability."""

    def cruise(self, tas: float, alt: float, dT: float = 0) -> float:
        if dT != 0 or not 20000 <= alt <= 41000:
            raise ValueError("Scalar thrust adapter only supports ISA cruise at 20,000–41,000 ft")
        height = alt * 0.3048
        speed = tas * 0.514444  # Deliberately match OpenAP's rounded conversion.
        pressure, _, temperature = _isa(height)
        reference_p, _, reference_t = _isa(11000.0)
        mach = speed / math.sqrt(1.4 * 287.05287 * temperature)
        if alt > 30000:
            ratio = (-0.4204 * mach / 0.84 + 1.0824) * math.log(pressure / reference_p)
            ratio += (mach / 0.84) ** (-0.11)
        else:
            cas_ratio = _cas(speed, height) / _cas(
                0.84 * math.sqrt(1.4 * 287.05287 * reference_t), 11000)
            ratio = cas_ratio**(-0.1) * (pressure / reference_p)**(-0.355 * cas_ratio + 0.8633)
        return ratio * 103670.0 * 2
