# Model notes

This app models clean, steady level cruise for the Boeing 777-300ER with two
GE90-115B engines. It is an educational research tool, not an operational fuel planner.

## Python execution

The UI uses a web worker running Pyodide 0.27.7. The browser serves and executes
the same scalar Python files tested in CPython. NumPy, Pandas and SciPy are not
required by the deployed package. The desktop OpenAP implementation is retained
separately for comparisons.

The browser engine adapter is a scalar adaptation of the relevant OpenAP 2.6.1
fuel and ISA cruise-thrust equations, with fixed B77W/GE90-115B parameters. This
reduces runtime dependencies; it does not improve the underlying aircraft model.

## Inputs and equations

- Mass includes remaining fuel. Zero-fuel mass includes aircraft, occupants and payload.
- Altitude means ISA pressure altitude, not geometric height.
- Temperature is a deviation from ISA static/outside temperature, not total air temperature.
- Positive headwind opposes travel; a negative value is a tailwind.
- Crosswind is included using a track-holding wind triangle.
- Manual thrust is total net thrust of both engines, not N1, throttle position or rated-thrust percentage.

Atmosphere: ISA pressure; rho = p/(R T); speed of sound = sqrt(gamma R T).
Aerodynamics: q = rho V²/2; CL = mg/(q S); CD = 0.024 + 0.043 CL²;
wing area S = 436.8 m². Automatic thrust balances modeled drag.

At fixed Mach and pressure altitude, q = gamma p Mach²/2, so temperature cancels
from dynamic pressure. Direct engine thermal effects are not modeled. Fuel flow
can therefore remain unchanged as temperature changes even though speed and fuel
per ground distance change.

The OpenAP generic fuel curve is scaled to GE90-115B parameters. OpenAP 2.6.1
has no dedicated B77W fuel-fit row. The ISA thrust reference is a coarse estimate,
not actual non-ISA available thrust or a certified limit.

Cruise integrates dm/dt = -fuel_flow(m) using midpoint integration, stopping at
the requested distance or chosen protected-fuel floor. This excludes takeoff,
taxi, climb, descent, APU and regulatory reserve calculations.

## Verification completed

- Four parity tests passed, including 81 flight states, manual-thrust/TSFC cases,
  and complete and fuel-floor cruise segments.
- Fuel flow, drag, groundspeed and ISA thrust reference matched the desktop
  implementation within an absolute 1e-7 tolerance in their reported units at
  the tested states.
- Seven checks passed under the pinned Pyodide runtime in Node.
- Default fuel estimate: 10,710.224648 kg/h total. A 1,500 nmi default segment
  burned 31,997.461084 kg in this model. These are generated examples, not observations.
- JavaScript syntax and static local asset references were checked.

Interactive browser and real-device verification remain outstanding. Matching a
shared model does not establish accuracy against actual aircraft measurements.

## Scope and limitations

Mach 0.70–0.84, pressure altitude 20,000–41,000 ft, ISA deviation −25 to +15 °C.
These are research scope limits, not a certified flight envelope. CL and ISA-thrust
screening do not establish stall/buffet margin. Wave drag, icing, anti-ice, bleed
and engine deterioration are excluded. Fuel ±10% is a hypothetical sensitivity,
not a confidence interval.

Reference evaluation fits one multiplier on training flights and evaluates different
test flights. Source provenance is user-declared. Simulator/synthetic data cannot
establish real-aircraft accuracy. No fit is automatically applied.

Sources:
- https://github.com/junzis/openap
- https://openap.dev/fuel_emission.html
- https://www.boeing.com/commercial/777
- https://www.grc.nasa.gov/www/k-12/airplane/sfc.html

Licenses and modifications: THIRD_PARTY_NOTICES.md.
