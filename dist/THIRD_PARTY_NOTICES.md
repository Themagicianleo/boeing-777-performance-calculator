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

## Project development

This implementation was developed with AI assistance. It does not claim authorship
of third-party models or independently measured aircraft data. Boeing and GE names
identify the modeled aircraft and engine; no affiliation or endorsement is implied.
