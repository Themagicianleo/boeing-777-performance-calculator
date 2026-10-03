# Project handoff from ChatGPT

Imported on 3 October 2026 from the existing repository:
https://github.com/Themagicianleo/boeing-777-performance-calculator

Source commit: `2122cb87458649306840cc2330fb1bb62a8e58a2`.
All 41 imported files were checked against their Git blob hashes, including icons
and third-party licenses. The existing local Git folder was preserved.

Relevant ChatGPT conversations:
- “Build Boeing 777 Calculator”
- “Summarise Boeing Calculator”

The project is B777 Performance Lab, a Python aerospace portfolio project for
exploring how aircraft mass, atmosphere, speed, thrust and wind influence cruise
fuel burn. The intended direction is a reproducible, technically defensible
model with a mobile web interface and GitHub publication. The current aircraft
is the Boeing 777-300ER with GE90-115B engines.

The retrieved source already includes Calculate, Cruise, Compare, Evidence,
exports and a GitHub Pages workflow. It uses a scalar adaptation of OpenAP 2.6.1
in Pyodide, with a separate desktop reference implementation. Independent
aircraft validation remains outstanding; numerical parity is not a measured
accuracy claim. Preserve the source attribution and model limitations.

Initial local development adds `b777_calculator.py`: a standard-library Python
launcher that runs the same deployed calculation engine in CPython, serves the
existing web interface on loopback, and supports JSON CLI experiments. The web
worker detects the local engine; static hosting continues to use Pyodide.
