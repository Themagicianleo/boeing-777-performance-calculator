# B777 Performance Lab — mobile web app

A responsive browser app for exploring 777-300ER cruise fuel estimates. Python
runs on the device through a pinned Pyodide 0.27.7 WebAssembly runtime, in a web
worker. No Python server or API key is required.

Educational estimates only: this is not Boeing-certified software and must not
be used for flight planning, dispatch, or real aircraft operation. Independent
aircraft-data validation has not established an accuracy percentage.

## Features

- Calculate: mass, Mach, pressure altitude, temperature deviation, wind and thrust.
- Cruise: mass-depleting fuel integration, fuel-floor stopping and a fuel chart.
- Compare: controlled weather/weight comparisons and assumed fuel-bias sensitivity.
- Evidence: model limitations, sources and local reference-data evaluation.
- JSON results, CSV cruise trace and home-screen metadata/icons.

The runtime downloads from jsDelivr on first use. Internet access is required to
load the runtime and app sources; offline installation is not implemented.
Inputs and uploaded reference data are processed locally, not sent to a calculation server.
Hosting providers and the runtime CDN still receive normal asset requests.

## Run locally

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

These tests are not interactive browser/device tests. Mobile layout, downloads
and controls still need an end-to-end check on an actual phone before a public
portfolio demonstration. No independent B777 aircraft-accuracy percentage is established.

## Structure

- `dist/`: all deployed files, including the Python source.
- `dist/python/b777/`: atmosphere, engine adapter, model, integration and evaluation.
- `dist/worker.js`: loads Python and accepts JSON calculation requests.
- `dist/app.js`, `style.css`, `index.html`: interface and presentation only.
- `reference/`: desktop implementation for numerical comparisons.
- `tests/`: parity and WebAssembly checks.

See `dist/MODEL.md` and `dist/THIRD_PARTY_NOTICES.md` for model scope and attribution.
No secrets or credentials are included.
