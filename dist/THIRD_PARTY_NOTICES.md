# Third-party notices

## OpenAP

OpenAP, by Junzi Sun and contributors: https://github.com/junzis/openap
Reference release: 2.6.1.

`python/b777/engine.py` adapts the scalar fuel-flow and ISA cruise-thrust calculations
from OpenAP. Changes: replaced array operations with Python scalar math, fixed the
aircraft/engine to B77W/GE90-115B, omitted unsupported flight regimes, and removed
runtime dependence on the full OpenAP package. Attribution is also included in
that file. The original OpenAP code license is provided in OPENAP_CODE_LICENSE.txt
(GNU LGPL version 3). The OpenAP data-directory license supplied by the installed
package is provided in OPENAP_DATA_LICENSE.txt (GNU GPL version 3). Corresponding
adapted source and the used numerical parameters are distributed in this app's
Python files. No proprietary Boeing or GE performance deck is included.

## Pyodide

Pyodide, by its contributors: https://pyodide.org/
Runtime version: 0.27.7. Downloaded at runtime from jsDelivr; not bundled in this
archive. The Node development dependency uses the same pinned release.
Repository and licensing: https://github.com/pyodide/pyodide

## IBM Plex fonts

IBM Plex Sans and IBM Plex Mono, Copyright © 2017 IBM Corp., with Reserved Font
Name "Plex". Latin subsets from Fontsource 5.2.6 are bundled in `fonts/` under the
SIL Open Font License 1.1; the full license is in `fonts/OFL.txt`.

## Header photograph

`photo-777-300er.jpg` and `photo-777-300er-900.jpg`: Emirates Boeing 777-300ER A6-EBM
landing at London Heathrow, by Adrian Pingstone, released into the public domain
(Wikimedia Commons, `File:Emirates_b777-300er_a6-ebm_arp.jpg`). Cropped, resized and
converted to a two-tone print for this app. Airline names and marks visible in the
photo belong to their owners; no affiliation or endorsement is implied.

## Project development

This implementation was developed with AI assistance. It does not claim authorship
of third-party models or independently measured aircraft data. Boeing and GE names
identify the modeled aircraft and engine; no affiliation or endorsement is implied.
