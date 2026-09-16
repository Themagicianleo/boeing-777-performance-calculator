"""Tk desktop explorer; numerical work is isolated from the UI thread."""

import json
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .model import FlightCondition, ModelSettings, PerformanceModel
from .reporting import cruise_figure, save_cruise_plot, write_cruise_csv, write_json
from .simulation import CruiseRequest, compare_conditions, cruise_sensitivity, simulate_cruise
from .validation import evaluate_observations

FIELDS = (
    ("mass_kg", "Aircraft mass · kg", "250000"),
    ("altitude_ft", "Pressure altitude · ft", "35000"),
    ("mach", "Mach · 0.70–0.84", "0.84"),
    ("isa_delta_c", "ISA deviation · °C", "0"),
    ("headwind_kt", "Headwind · kt (− = tailwind)", "0"),
    ("crosswind_kt", "Crosswind · kt", "0"),
    ("total_thrust_kn", "Total thrust · kN (blank = auto)", ""),
    ("distance_nmi", "Cruise distance · nmi", "2000"),
    ("zero_fuel_mass_kg", "Zero-fuel mass · kg", "200000"),
    ("protected_fuel_kg", "Protected fuel · kg", "8000"),
    ("fuel_scale", "Fuel sensitivity multiplier", "1.0"),
    ("drag_scale", "Drag sensitivity multiplier", "1.0"),
    ("tsfc_kg_kn_h", "Optional TSFC · kg/kN/h", ""),
)


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.future = None
        self.export_model = None
        self.export_result = None
        self.cruise_result = None
        self.canvas = None
        self.revision = 0
        root.title("B777 Performance Lab")
        root.geometry("1240x850")
        root.minsize(1060, 780)
        root.configure(bg="#f1f4f8")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f1f4f8")
        style.configure("TLabel", background="#f1f4f8", foreground="#203047", font=("Arial", 10))
        style.configure("Title.TLabel", font=("Arial", 24, "bold"))
        style.configure("TButton", padding=7)
        style.configure("Treeview", rowheight=29, font=("Arial", 10))
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        header = ttk.Frame(root, padding=(22, 18))
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="B777 Performance Lab", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header, text="777-300ER / GE90-115B  •  Cruise experiments  •  Research estimate"
        ).pack(anchor="w", pady=5)
        body = ttk.Frame(root, padding=(18, 0, 18, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        inputs = ttk.Frame(body, padding=(8, 0, 20, 0))
        inputs.grid(row=0, column=0, sticky="ns")
        self.variables = {}
        for row, (key, label, default) in enumerate(FIELDS):
            ttk.Label(inputs, text=label).grid(row=row * 2, column=0, sticky="w", pady=(4, 0))
            variable = tk.StringVar(value=default)
            ttk.Entry(inputs, textvariable=variable, width=31).grid(
                row=row * 2 + 1, column=0, sticky="ew"
            )
            variable.trace_add("write", self.invalidate)
            self.variables[key] = variable
        self.notebook = ttk.Notebook(body)
        self.notebook.grid(row=0, column=1, sticky="nsew")
        self.summary = self.text_tab("Results")
        self.plot_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.plot_frame, text="Cruise plot")
        self.comparison = self.text_tab("Comparisons")
        self.evidence = self.text_tab("Validation")
        self.methods = self.text_tab("Model & limits")
        self.put(self.methods, METHODS)
        actions = ttk.Frame(root, padding=(22, 0, 22, 8))
        actions.grid(row=2, column=0, sticky="ew")
        self.buttons = []
        for label, command in (
            ("Snapshot", lambda: self.start("snapshot")),
            ("Simulate cruise", lambda: self.start("cruise")),
            ("Compare", lambda: self.start("compare")),
            ("Fuel ±10%", lambda: self.start("sensitivity")),
            ("Validate data…", self.load_validation),
            ("Export JSON…", self.export_json),
            ("Export trace…", self.export_trace),
            ("Save plot…", self.export_plot),
        ):
            button = ttk.Button(actions, text=label, command=command)
            button.pack(side="left", padx=(0, 5))
            self.buttons.append(button)
        self.status = tk.StringVar(value="Ready. Run a snapshot or cruise experiment.")
        ttk.Label(root, textvariable=self.status, padding=(22, 0, 22, 12)).grid(
            row=3, column=0, sticky="ew"
        )
        self.put(
            self.summary,
            "Start with a snapshot to inspect fuel flow and model screening.\n\n"
            "Simulate cruise integrates fuel burn as aircraft mass decreases.\n\n"
            "No independent B777 fuel-flow validation has been supplied.\n"
            "Use Model & limits for the supported scope and assumptions.",
        )
        root.protocol("WM_DELETE_WINDOW", self.close)

    def text_tab(self, title):
        frame = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(frame, text=title)
        text = tk.Text(
            frame,
            wrap="word",
            font=("Arial", 11),
            relief="flat",
            padx=16,
            pady=16,
            bg="white",
            fg="#203047",
            width=65,
        )
        scrollbar = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        return text

    @staticmethod
    def put(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def invalidate(self, *_):
        self.revision += 1
        self.export_result = None
        self.cruise_result = None
        if hasattr(self, "status"):
            self.status.set(
                "Inputs changed. Rerun before exporting; displayed results are from the previous run."
            )

    def parameters(self):
        values = {}
        for key, variable in self.variables.items():
            content = variable.get().strip()
            if not content and key in ("total_thrust_kn", "tsfc_kg_kn_h"):
                values[key] = None
            else:
                try:
                    values[key] = float(content)
                except ValueError as error:
                    raise ValueError(f"Enter a number for {key}") from error
        condition = FlightCondition(**{key: values[key] for key in asdict(FlightCondition())})
        settings = ModelSettings(values["fuel_scale"], values["drag_scale"], values["tsfc_kg_kn_h"])
        request = CruiseRequest(
            condition,
            values["distance_nmi"],
            values["zero_fuel_mass_kg"],
            values["protected_fuel_kg"],
        )
        return settings, condition, request, values["total_thrust_kn"]

    def start(self, kind, dataset=None):
        if self.future is not None:
            return
        try:
            settings, condition, request, thrust = self.parameters()
            if thrust is not None and kind not in ("snapshot", "validate"):
                raise ValueError("Clear manual thrust for cruise/comparison experiments")
        except ValueError as error:
            messagebox.showerror("Input error", str(error))
            return
        revision = self.revision
        self.status.set("Calculating…")
        for button in self.buttons:
            button.state(["disabled"])

        def work():
            model = PerformanceModel(settings)
            if kind == "snapshot":
                result = model.snapshot(condition, thrust)
            elif kind == "cruise":
                result = simulate_cruise(model, request)
            elif kind == "compare":
                result = {
                    "base_condition": asdict(condition),
                    "comparisons": compare_conditions(model, condition),
                }
            elif kind == "sensitivity":
                result = {
                    "request": asdict(request),
                    "sensitivity": cruise_sensitivity(model, request),
                }
            else:
                result = evaluate_observations(model, dataset)
            return model, result

        self.future = self.pool.submit(work)
        self.root.after(50, lambda: self.poll(kind, revision))

    def poll(self, kind, revision):
        if not self.future.done():
            self.root.after(50, lambda: self.poll(kind, revision))
            return
        try:
            model, result = self.future.result()
            if revision != self.revision:
                self.status.set("Inputs changed during calculation. Rerun with current inputs.")
                return
            self.export_model = model
            self.export_result = result.to_dict() if hasattr(result, "to_dict") else result
            self.cruise_result = result if kind == "cruise" else None
            if kind == "snapshot":
                summary = (
                    f"TOTAL FUEL FLOW     {result.fuel_total_kg_h:,.0f} kg/h\n"
                    f"Per engine                    {result.fuel_per_engine_kg_h:,.0f} kg/h\n"
                    f"Fuel per ground distance  {result.fuel_kg_nmi:.2f} kg/nmi\n\n"
                    f"Required drag / thrust      {result.drag_kn:.1f} / {result.total_thrust_kn:.1f} kN\n"
                    f"ISA reference thrust margin  {result.isa_reference_margin_kn:.1f} kN\n"
                    f"TAS / groundspeed          {result.tas_kt:.1f} / {result.groundspeed_kt:.1f} kt\n"
                    f"Lift-to-drag ratio              {result.lift_to_drag:.2f}\n"
                    f"Lift coefficient                  {result.lift_coefficient:.3f}\n"
                    f"Outside temperature          {result.temperature_c:.1f} °C\n"
                    f"Pressure                          {result.pressure_hpa:.1f} hPa\n\n"
                    f"Research screening: {'passed' if result.screening_passed else 'failed'}\n"
                    "This does not establish a certified flight envelope.\n\n"
                    + "\n\n".join(result.warnings)
                )
                self.put(self.summary, summary)
                self.notebook.select(0)
            elif kind == "cruise":
                last = result.points[-1]
                self.put(
                    self.summary,
                    f"CRUISE FUEL BURN     {result.fuel_burn_kg:,.0f} kg\n\n"
                    f"Distance covered              {last.distance_nmi:,.1f} nmi\n"
                    f"Elapsed time                     {last.elapsed_h:.2f} hours\n"
                    f"Remaining fuel                  {last.remaining_fuel_kg:,.0f} kg\n"
                    f"Final aircraft mass             {last.mass_kg:,.0f} kg\n\n"
                    f"{result.stop_reason}\n\n" + "\n\n".join(result.warnings),
                )
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

                if self.canvas is not None:
                    self.canvas.get_tk_widget().destroy()
                self.canvas = FigureCanvasTkAgg(cruise_figure(result), master=self.plot_frame)
                self.canvas.draw()
                self.canvas.get_tk_widget().pack(fill="both", expand=True)
                self.notebook.select(1)
            else:
                target = self.evidence if kind == "validate" else self.comparison
                self.put(target, format_experiment(kind, result))
                self.notebook.select(3 if kind == "validate" else 2)
            self.status.set(
                "Calculation complete. Results are estimates; inputs and provenance are included in JSON exports."
            )
        except Exception as error:
            self.export_result = None
            self.cruise_result = None
            self.status.set("Calculation failed. Correct the inputs and rerun.")
            messagebox.showerror("Calculation error", str(error))
        finally:
            self.future = None
            for button in self.buttons:
                button.state(["!disabled"])

    def load_validation(self):
        path = filedialog.askopenfilename(filetypes=[("Reference data", "*.json")])
        if path:
            try:
                dataset = json.loads(Path(path).read_text(encoding="utf-8"))
                self.start("validate", dataset)
            except (ValueError, OSError) as error:
                messagebox.showerror("Reference data error", str(error))

    def export_json(self):
        if self.export_result is None:
            messagebox.showinfo("Run an experiment", "Calculate current inputs before exporting.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json")
        if path:
            self.save_safely(lambda: write_json(path, self.export_model, self.export_result))

    def export_trace(self):
        if self.cruise_result is None:
            messagebox.showinfo("Run cruise", "Run a cruise experiment first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv")
        if path:

            def save():
                write_cruise_csv(path, self.cruise_result)
                write_json(path + ".metadata.json", self.export_model, self.export_result)

            self.save_safely(save)

    def export_plot(self):
        if self.cruise_result is None:
            messagebox.showinfo("Run cruise", "Run a cruise experiment first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png")
        if path:
            self.save_safely(lambda: save_cruise_plot(path, self.cruise_result))

    @staticmethod
    def save_safely(action):
        try:
            action()
        except (OSError, ValueError) as error:
            messagebox.showerror("Export error", str(error))

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def format_experiment(kind: str, result: dict) -> str:
    """Human-readable summaries; full precision remains in the JSON export."""
    if kind == "compare":
        lines = ["ONE-VARIABLE COMPARISONS", "", "Other conditions held at the input baseline.", ""]
        for row in result["comparisons"]:
            lines.append(row["scenario"])
            if "error" in row:
                lines.append("  Outside supported scope: " + row["error"])
            else:
                lines.extend(
                    [
                        f"  Fuel flow: {row['fuel_kg_h']:,.0f} kg/h",
                        f"  Fuel per distance: {row['fuel_kg_nmi']:.2f} kg/nmi",
                        f"  Groundspeed: {row['groundspeed_kt']:.1f} kt",
                        "  Research screening: "
                        + ("passed" if row["screening_passed"] else "failed"),
                    ]
                )
            lines.append("")
        lines.append("Temperature changes here exclude direct engine thermal effects.")
        return "\n".join(lines)
    if kind == "sensitivity":
        lines = ["FUEL-MODEL SENSITIVITY", "", "Assumed fuel bias, not a confidence interval.", ""]
        for row in result["sensitivity"]:
            lines.extend(
                [
                    f"Fuel multiplier: {row['relative_fuel_factor']:.2f} × current model",
                    f"  Burn: {row['fuel_burn_kg']:,.0f} kg",
                    f"  Distance covered: {row['distance_nmi']:,.1f} nmi",
                    "  "
                    + (
                        "Requested distance completed"
                        if row["completed"]
                        else "Fuel floor reached early"
                    ),
                    "",
                ]
            )
        return "\n".join(lines)
    lines = [
        "REFERENCE-DATA EVALUATION",
        "",
        "Source: " + result["source"],
        "Declared data type: " + result["source_type"],
        "",
        f"Fitted multiplier relative to current model: {result['relative_fitted_scale']:.4f}",
        "This fit has not been automatically applied.",
        "",
    ]
    for split, values in result["metrics"].items():
        lines.append(f"{split.upper()} — {values['flight_count']} flight(s)")
        for name in ("baseline", "fitted"):
            score = values[name]
            lines.append(
                f"  {name}: MAE {score['mae_kg_h']:.1f} kg/h; "
                f"RMSE {score['rmse_kg_h']:.1f} kg/h; MAPE {score['mape_percent']:.2f}%"
            )
        lines.append("")
    lines.extend([result["scope"], "", result["qualification"]])
    return "\n".join(lines)


METHODS = """MODEL & LIMITS

Aircraft: Boeing 777-300ER (B77W), two GE90-115B engines.

OpenAP 2.6.1 supplies aircraft geometry, estimated drag coefficients and an engine-scaled generic fuel curve. B77W has no dedicated fuel-fit row in this version. A fuel curve is not a certified engine performance deck.

Fuel flow is a function of total net thrust. Automatic thrust balances clean, level-flight drag. Manual thrust is an instantaneous experiment; it does not hold speed when thrust differs from drag.

Atmosphere: ISA pressure altitude and dry-air temperature deviation. Pressure altitude is not geometric height or QNH. At fixed pressure altitude and Mach, dynamic pressure does not change with temperature. Consequently this model's drag and fuel flow can remain unchanged as temperature changes, while true airspeed and fuel per mile change. Direct engine thermal efficiency is not represented.

Wind: along-track headwind and crosswind, with a track-holding wind triangle. No live weather retrieval. Maximum thrust is only an ISA reference. Research CL/thrust screening is not a buffet or stall check.

Cruise integration updates mass using midpoint integration and stops at the selected protected-fuel floor. Zero-fuel mass includes aircraft, occupants and payload. The chosen protected fuel is not a regulatory reserve. No taxi, climb, descent, takeoff, landing or aircraft-specific loading-envelope validation.

Fuel ±10% explores an assumed model bias. It is not a 90%, 95% or other confidence interval.

Validation imports independently sourced observations, fits a single fuel multiplier on training flights, and evaluates separate test flights. Synthetic data test software only. Genuine B777 fuel observations have not been included.

Sources and reproducible validation details: docs/METHODS.md and docs/VALIDATION.md in the project.
"""


def launch():
    root = tk.Tk()
    Application(root)
    root.mainloop()
