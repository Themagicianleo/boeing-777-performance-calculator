# B777 Performance Lab — mobile web app

A responsive browser app for exploring 777-300ER cruise fuel estimates. Python
runs on the device through a pinned Pyodide 0.27.7 WebAssembly runtime, in a web
worker. No Python server or API key is required.

Local development also supports CPython through `b777_calculator.py`, using
the same scalar calculation package without downloading a browser runtime.

Educational estimates only: this is not Boeing-certified software and must not
be used for flight planning, dispatch, or real aircraft operation. Independent
aircraft-data validation has not established an accuracy percentage.

## Features

- Calculate: mass, Mach, pressure altitude, temperature deviation, wind and thrust.
- Cruise: mass-depleting fuel integration, fuel-floor stopping and a fuel chart.
- Compare: controlled weather/weight comparisons and assumed fuel-bias sensitivity.
- Evidence: model limitations, sources and local reference-data evaluation.
- JSON results, CSV cruise trace and home-screen metadata/icons.

On static hosting, the runtime downloads from jsDelivr on first use. Internet
access is required to load it; offline installation is not implemented.
The local launcher works without internet access. Inputs and uploaded reference
data stay on the device, using browser Python or the loopback Python server.
Hosting providers and the runtime CDN still receive normal asset requests.

## Run locally

For development, run the local Python launcher (Python 3.10+; no extra packages):

```bash
python b777_calculator.py --gui
```

On Windows with Codex, `./Start-Lab.ps1` uses the bundled Python automatically.

This opens http://127.0.0.1:8000 and executes the existing deployed Python model
locally, without a CDN download. The server accepts connections only from this
computer and serves the `dist` folder. Stop it with Ctrl+C. Use `--no-browser`
to keep browser launch manual, or `--port 8001` if port 8000 is occupied.

The same engine supports command-line experiments with JSON output:

```bash
python b777_calculator.py snapshot --mass-kg 280000 --headwind-kt 50
python b777_calculator.py cruise --distance-nmi 1500
python b777_calculator.py compare
```

For the static-hosted browser/Pyodide version, use:

From the project folder:

```bash
python -m http.server 8000 --directory dist
```

Open http://localhost:8000 in a browser. Do not open index.html directly with a
file URL: workers and Python source loading require HTTP(S).

## Publish to GitHub Pages

The repository contains `.github/workflows/pages.yml`, which verifies the engine
and deploys the `dist` folder on pushes to `main`.

1. Create or choose a GitHub repository and upload the complete project, including
   `.github/workflows/pages.yml`. Do not upload only the HTML file.
2. In repository Settings → Pages, select **GitHub Actions** as the source.
3. Push to `main`, or run the workflow manually under Actions.
4. Wait for the deployment job to succeed; GitHub reports the published URL.

Project repository: https://github.com/Themagicianleo/boeing-777-performance-calculator

After a successful Pages deployment, the app is available at:
https://themagicianleo.github.io/boeing-777-performance-calculator/

GitHub setup reference:
https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## Verification

The local launcher and model can be checked without installing dependencies:

```bash
python -m unittest discover -s tests -p test_local.py -v
```

The original desktop-reference and WebAssembly checks require their dependencies:

```bash
python -m pip install -r reference/requirements.txt
python tests/test_parity.py
npm ci
npm test
```

The browser Python adaptation was compared against the desktop engine at 81 flight
states, manual thrust points, constant TSFC settings and complete/fuel-limited
cruise segments. Four parity tests passed. Seven runtime checks passed inside
Pyodide 0.27.7 under Node, using the actual browser Python source package.
JavaScript syntax and local file references were checked.

The statements above describe verification from the imported project. During the
local handoff, eight launcher/HTTP tests and 21 existing physics, simulation and
reference-evaluation tests passed against the scalar Python package. OpenAP
cross-implementation/parity and Pyodide tests were not rerun: their optional
dependencies are not installed in this workspace.

The local interface was checked in the Codex browser: initial calculation,
edited headwind, reset, a 1,500 nmi cruise, chart, comparisons and a 390 px
viewport.

On 20 October 2026 the remaining checks were rerun on Linux (Python 3.13,
Node 22): 8 launcher, 4 OpenAP parity, 21 reference and 7 Pyodide checks passed.
A headless Chromium session emulating an iPhone 13 (390 px) drove both the local
CPython server and the static Pyodide 0.27.7 build: calculation, 1,500 nmi
cruise, JSON export and CSV export (373 trace rows) all succeeded with identical
results, no horizontal overflow and no console errors. Pyodide was served from
the pinned npm package rather than jsDelivr for that run. Behaviour on physical
phones is still unverified. No independent B777 aircraft-accuracy percentage is
established.

## Structure

- `dist/`: all deployed files, including the Python source.
- `dist/python/b777/`: atmosphere, engine adapter, model, integration and evaluation.
- `dist/worker.js`: loads Python and accepts JSON calculation requests.
- `dist/app.js`, `style.css`, `index.html`: interface and presentation only.
- `reference/`: desktop implementation for numerical comparisons.
- `tests/`: parity and WebAssembly checks.
- `b777_calculator.py`: local web server and JSON command-line experiments.
- `PROJECT_CONTEXT.md`: source commit and recovered ChatGPT project requirements.

See `dist/MODEL.md` and `dist/THIRD_PARTY_NOTICES.md` for model scope and attribution.
No secrets or credentials are included.
