"""Run the existing Python calculator locally, from a browser or the CLI."""

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "dist" / "python"))
from bridge import dispatch

MAX_REQUEST_BYTES = 2_100_000


class LabHandler(SimpleHTTPRequestHandler):
    """Serve only dist/ and a loopback-only JSON interface to the same model."""

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def allowed_request(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") not in (expected, f"localhost:{self.server.server_port}"):
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in (f"http://{expected}", f"http://localhost:{self.server.server_port}")

    def send_json(self, payload, status=200):
        content = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if not self.allowed_request():
            self.send_json({"ok": False, "error": "Use the local calculator URL."}, 403)
        elif urlsplit(self.path).path == "/api/runtime":
            self.send_json({"runtime": "cpython-local", "version": sys.version.split()[0]})
        else:
            super().do_GET()

    def do_POST(self):
        if not self.allowed_request():
            self.send_json({"ok": False, "error": "Use the local calculator URL."}, 403)
            return
        if urlsplit(self.path).path != "/api/calculate":
            self.send_json({"ok": False, "error": "Unknown endpoint."}, 404)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json({"ok": False, "error": "Send application/json."}, 415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= MAX_REQUEST_BYTES:
            self.send_json({"ok": False, "error": "Use a JSON request smaller than 2.1 MB."}, 413)
            return
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request")
            result = json.loads(dispatch(body.decode("utf-8")))
        except (UnicodeDecodeError, ValueError):
            self.send_json({"ok": False, "error": "The request is not valid UTF-8 JSON."}, 400)
            return
        self.send_json(result)

    def list_directory(self, path):
        self.send_error(404, "Directory listings are disabled")
        return None


def create_server(port=8000):
    handler = partial(LabHandler, directory=str(ROOT / "dist"))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def parser():
    cli = argparse.ArgumentParser(description="B777 Performance Lab — local Python calculator")
    cli.add_argument("action", nargs="?", choices=("snapshot", "cruise", "compare", "sensitivity"))
    cli.add_argument("--gui", action="store_true", help="Open the local web interface (default with no action)")
    cli.add_argument("--no-browser", action="store_true", help="Start the interface without opening a browser")
    cli.add_argument("--port", type=int, default=8000, help="Local web port; 0 selects an available port")
    cli.add_argument("--mass-kg", type=float, default=250000)
    cli.add_argument("--altitude-ft", type=float, default=35000)
    cli.add_argument("--mach", type=float, default=0.84)
    cli.add_argument("--isa-delta-c", type=float, default=0)
    cli.add_argument("--headwind-kt", type=float, default=0)
    cli.add_argument("--crosswind-kt", type=float, default=0)
    cli.add_argument("--thrust-kn", type=float)
    cli.add_argument("--fuel-scale", type=float, default=1)
    cli.add_argument("--drag-scale", type=float, default=1)
    cli.add_argument("--tsfc-kg-kn-h", type=float)
    cli.add_argument("--uncalibrated", action="store_true", help="Use the raw OpenAP fuel curve without the Boeing payload/range calibration")
    cli.add_argument("--distance-nmi", type=float, default=1500)
    cli.add_argument("--zero-fuel-mass-kg", type=float, default=200000)
    cli.add_argument("--protected-fuel-kg", type=float, default=8000)
    cli.add_argument("--step-seconds", type=float, default=30)
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    if args.gui and args.action:
        cli.error("Choose --gui or a command-line experiment.")
    if not 0 <= args.port <= 65535:
        cli.error("Port must be between 0 and 65535.")
    if args.action:
        if args.thrust_kn is not None and args.action != "snapshot":
            cli.error("Manual thrust applies to snapshot only.")
        condition_keys = ("mass_kg", "altitude_ft", "mach", "isa_delta_c", "headwind_kt", "crosswind_kt")
        cruise_keys = ("distance_nmi", "zero_fuel_mass_kg", "protected_fuel_kg", "step_seconds")
        result = json.loads(dispatch(json.dumps({
            "action": args.action,
            "condition": {key: getattr(args, key) for key in condition_keys},
            "settings": {**{key: getattr(args, key) for key in ("fuel_scale", "drag_scale", "tsfc_kg_kn_h")},
                         "calibrated": not args.uncalibrated},
            "cruise": {key: getattr(args, key) for key in cruise_keys},
            "thrust_kn": args.thrust_kn,
        })))
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if result["ok"] else 1
    try:
        server = create_server(args.port)
    except OSError as error:
        cli.exit(1, f"Could not start the local calculator: {error}\nTry --port 8001.\n")
    with server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"B777 Performance Lab: {url}\nLocal Python engine ready. Press Ctrl+C to stop.", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
