"""
evaluate.py — PFAS Sensor Evaluator

Reads model.py + parameters.csv + specs.json.
Runs Differential Evolution to find cantilever geometry that meets all specs.
Generates publication-quality visualizations.

DO NOT MODIFY. The AI modifies model.py and parameters.csv only.

Usage:
    python3 evaluate.py              # full run
    python3 evaluate.py --quick      # fast sanity check
"""

import os
import sys
import json
import csv
import time
import argparse
import importlib.util
import multiprocessing
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from mpl_toolkits.mplot3d import Axes3D  # noqa

# ─── Paths ────────────────────────────────────────────────────────────────────
MODEL_FILE   = "model.py"
PARAMS_FILE  = "parameters.csv"
SPECS_FILE   = "specs.json"
RESULTS_FILE = "results.tsv"
PLOTS_DIR    = "plots"

DARK_BG    = "#090909"
DARK_PANEL = "#111111"
ACCENT     = "#00d4ff"
ACCENT2    = "#ff6b35"
TEXT       = "#dddddd"

# ─── Worker globals ───────────────────────────────────────────────────────────
_SIM_FUNC   = None
_PARAM_DEFS = None
_SPECS      = None


def _worker_init(model_path, param_defs, specs):
    global _SIM_FUNC, _PARAM_DEFS, _SPECS
    s = importlib.util.spec_from_file_location("model", model_path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    _SIM_FUNC   = m.run_simulation
    _PARAM_DEFS = param_defs
    _SPECS      = specs


def _worker_eval(x):
    params = _vec_to_params(x, _PARAM_DEFS)
    try:
        result = _SIM_FUNC(params)
        if result is None:
            return 1e6
        return compute_cost(result, _SPECS)
    except Exception:
        return 1e6


# ─── I/O ─────────────────────────────────────────────────────────────────────

def load_model(path=MODEL_FILE):
    s = importlib.util.spec_from_file_location("model", os.path.abspath(path))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m.run_simulation


def load_parameters(path=PARAMS_FILE):
    params = []
    with open(path) as f:
        for row in csv.DictReader(f):
            params.append({"name":  row["name"].strip(),
                           "min":   float(row["min"]),
                           "max":   float(row["max"]),
                           "scale": row.get("scale", "lin").strip()})
    return params


def load_specs(path=SPECS_FILE):
    with open(path) as f:
        return json.load(f)


# ─── Parameter transforms ─────────────────────────────────────────────────────

def _get_bounds(param_defs):
    return [(np.log(p["min"]), np.log(p["max"])) if p["scale"] == "log"
            else (p["min"], p["max"]) for p in param_defs]


def _vec_to_params(x, param_defs):
    return {p["name"]: (np.exp(x[i]) if p["scale"] == "log" else x[i])
            for i, p in enumerate(param_defs)}


# ─── Cost function ────────────────────────────────────────────────────────────

def compute_cost(measurements, specs):
    if not measurements:
        return 1e6
    cost = 0.0
    for name, spec in specs["measurements"].items():
        t_str  = spec["target"]
        weight = spec["weight"] / 100.0
        val    = measurements.get(name)
        if val is None:
            cost += weight * 1000
            continue
        if t_str.startswith(">"):
            tv = float(t_str[1:])
            cost += (0 if val >= tv else weight * ((tv - val) / max(abs(tv), 1e-30))**2 * 500)
            cost -= (0 if val < tv  else weight * min((val/max(abs(tv),1e-30))-1, 1.0) * 10)
        elif t_str.startswith("<"):
            tv = float(t_str[1:])
            cost += (0 if val <= tv else weight * ((val - tv) / max(abs(tv), 1e-30))**2 * 500)
            cost -= (0 if val > tv  else weight * min(1 - val/max(abs(tv),1e-30), 1.0) * 10)
    return cost


# ─── Scoring ──────────────────────────────────────────────────────────────────

def score_measurements(measurements, specs):
    details  = {}
    total_w, weighted = 0, 0
    for name, spec in specs["measurements"].items():
        w   = spec["weight"]
        t_s = spec["target"]
        unit = spec.get("unit", "")
        total_w += w
        val = measurements.get(name)
        if val is None:
            details[name] = {"measured": None, "target": t_s, "met": False, "score": 0.0, "unit": unit}
            continue
        if t_s.startswith(">"):
            tv = float(t_s[1:]); met = val >= tv
            sc = 1.0 if met else max(0.0, val / max(abs(tv), 1e-30))
        elif t_s.startswith("<"):
            tv = float(t_s[1:]); met = val <= tv
            sc = 1.0 if met else max(0.0, tv / max(abs(val), 1e-30))
        else:
            met, sc = False, 0.0
        weighted += w * sc
        details[name] = {"measured": val, "target": t_s, "met": met, "score": sc, "unit": unit}
    return weighted / total_w if total_w > 0 else 0.0, details


# ─── DE ──────────────────────────────────────────────────────────────────────

def run_de(param_defs, specs, quick=False, n_workers=-1):
    bounds   = _get_bounds(param_defs)
    n_params = len(param_defs)
    pop_size = max(10, 3*n_params) if quick else max(20, 8*n_params)
    max_iter = 30 if quick else 500
    F, CR    = 0.8, 0.9

    if n_workers < 0:
        n_workers = multiprocessing.cpu_count()

    model_path = os.path.abspath(MODEL_FILE)
    print(f"DE: {n_params} params | pop={pop_size} | maxiter={max_iter} | workers={n_workers}")

    with multiprocessing.Pool(processes=n_workers,
                              initializer=_worker_init,
                              initargs=(model_path, param_defs, specs)) as pool:

        rng = np.random.default_rng(seed=1)
        lo  = np.array([b[0] for b in bounds])
        hi  = np.array([b[1] for b in bounds])
        pop = rng.uniform(lo, hi, (pop_size, n_params))
        fit = np.array(pool.map(_worker_eval, list(pop)))

        best = int(np.argmin(fit))
        last_improvement = 0

        for gen in range(max_iter):
            cands = []
            for i in range(pop_size):
                idx = list(range(pop_size)); idx.remove(i)
                a, b_v, c = pop[rng.choice(idx, 3, replace=False)]
                mut  = np.clip(a + F*(b_v - c), lo, hi)
                mask = rng.random(n_params) < CR
                mask[rng.integers(n_params)] = True
                cands.append(np.where(mask, mut, pop[i]))

            tf = np.array(pool.map(_worker_eval, cands))
            improved = False
            for i in range(pop_size):
                if tf[i] < fit[i]:
                    pop[i], fit[i] = cands[i], tf[i]
                    improved = True

            new_best = int(np.argmin(fit))
            if new_best != best or gen % 20 == 0:
                best = new_best
                bp   = _vec_to_params(pop[best], param_defs)
                res  = _SIM_FUNC(bp) if _SIM_FUNC else {}
                lod  = (res or {}).get("detection_limit", 99)
                f0   = (res or {}).get("f0_khz", 0)
                Q    = (res or {}).get("Q_factor", 0)
                print(f"  gen {gen:>4}  cost={fit[best]:>9.2f}  "
                      f"LOD={lod:.2f} ng/L  f0={f0:.0f} kHz  Q={Q:.0f}  "
                      f"L={bp.get('L_um',0):.1f}μm  t={bp.get('t_um',0):.2f}μm")

            if improved:
                last_improvement = gen
            if fit[best] < -45 or (gen - last_improvement > 60 and gen > 50):
                print(f"  Converged at generation {gen}")
                break

    return pop[best], fit[best]


# ─── Visualizations ──────────────────────────────────────────────────────────

def generate_plots(best_result, measurements, params, specs, score):
    os.makedirs(PLOTS_DIR, exist_ok=True)
    _plot_hero(measurements, params, score, specs)
    _plot_cantilever_3d(params)
    _plot_sensitivity_sweep(params)
    _plot_frequency_response(measurements, params)
    print(f"\nAll plots saved to ./{PLOTS_DIR}/")


def _plot_hero(measurements, params, score, specs):
    fig = plt.figure(figsize=(18, 8), facecolor=DARK_BG)
    gs  = GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.35)

    # ── Left: scorecard ───────────────────────────────────────────────────
    ax_sc = fig.add_subplot(gs[:, 0])
    ax_sc.set_facecolor(DARK_PANEL)
    ax_sc.axis("off")
    ax_sc.set_title("PFAS Sensor Scorecard", color=TEXT, fontsize=13, pad=10)

    EPA_LIMIT = 4.0
    comparisons = [
        ("LC-MS/MS (lab)", 0.001, "#666666"),
        ("ELISA kit",      2.0,   "#666666"),
        ("This sensor",    measurements.get("detection_limit", 99), ACCENT),
        ("EPA MCL limit",  EPA_LIMIT, ACCENT2),
    ]

    lod_vals   = [c[1] for c in comparisons]
    lod_labels = [c[0] for c in comparisons]
    lod_colors = [c[2] for c in comparisons]

    ax_bar = fig.add_subplot(gs[0, 0])
    ax_bar.set_facecolor(DARK_PANEL)
    bars = ax_bar.barh(lod_labels, lod_vals, color=lod_colors, alpha=0.85, height=0.5)
    ax_bar.axvline(EPA_LIMIT, color=ACCENT2, linestyle="--", linewidth=1.5, label=f"EPA MCL {EPA_LIMIT} ng/L")
    ax_bar.set_xlabel("Detection Limit (ng/L)", color=TEXT, fontsize=9)
    ax_bar.set_title("vs. Existing Methods", color=TEXT, fontsize=11)
    ax_bar.tick_params(colors=TEXT, labelsize=8)
    for sp in ax_bar.spines.values(): sp.set_color("#333")
    ax_bar.set_xscale("log")
    ax_bar.legend(facecolor=DARK_PANEL, labelcolor=TEXT, fontsize=8)

    # ── Center: spec table ────────────────────────────────────────────────
    ax_spec = fig.add_subplot(gs[1, 0])
    ax_spec.set_facecolor(DARK_PANEL)
    ax_spec.axis("off")

    y = 0.9
    ax_spec.text(0.5, 1.0, "Specification Results", transform=ax_spec.transAxes,
                 ha="center", va="top", color=TEXT, fontsize=11)
    for name, spec in specs["measurements"].items():
        val = measurements.get(name)
        tv  = float(spec["target"][1:])
        if spec["target"].startswith(">"):
            met = val is not None and val >= tv
        else:
            met = val is not None and val <= tv
        icon  = "✓" if met else "✗"
        color = "#44ff88" if met else "#ff4444"
        line  = f"{icon}  {name}: {val:.2f} {spec.get('unit','')}  (target {spec['target']})"
        ax_spec.text(0.05, y, line, transform=ax_spec.transAxes,
                     color=color, fontsize=9, va="top", fontfamily="monospace")
        y -= 0.2

    # ── Right top: geometry ────────────────────────────────────────────────
    ax_geo = fig.add_subplot(gs[0, 1])
    ax_geo.set_facecolor(DARK_PANEL)
    ax_geo.axis("off")
    ax_geo.set_title("Optimised Geometry", color=TEXT, fontsize=11)

    L    = params.get("L_um", 0)
    w    = params.get("w_um", 0)
    t    = params.get("t_um", 0)
    h    = params.get("h_coat_nm", 0)

    geo_lines = [
        f"  Length (L)    : {L:.1f} μm",
        f"  Width  (w)    : {w:.1f} μm",
        f"  Thickness (t) : {t:.2f} μm",
        f"  Coating       : {h:.0f} nm",
        f"",
        f"  Aspect L/t    : {L/max(t,0.001):.0f}",
        f"  Aspect L/w    : {L/max(w,0.001):.1f}",
        f"",
        f"  f₀            : {measurements.get('f0_khz',0):.0f} kHz",
        f"  Q             : {measurements.get('Q_factor',0):.0f}",
        f"  Sensitivity   : {measurements.get('sensitivity_hz_pg',0):.2f} Hz/pg",
        f"  LOD           : {measurements.get('detection_limit',0):.2f} ng/L",
        f"",
        f"  Score         : {score:.3f} / 1.00",
    ]

    ax_geo.text(0.05, 0.95, "\n".join(geo_lines), transform=ax_geo.transAxes,
                va="top", ha="left", color=TEXT, fontsize=9.5,
                fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.5", facecolor="#0d0d0d", alpha=0.9))

    # ── Right bottom: diagnostics ─────────────────────────────────────────
    ax_diag = fig.add_subplot(gs[1, 1])
    ax_diag.set_facecolor(DARK_PANEL)
    ax_diag.axis("off")
    ax_diag.set_title("Internal Diagnostics", color=TEXT, fontsize=11)

    diag_lines = [
        f"  m_eff         : {measurements.get('_m_eff_pg',0):.1f} pg",
        f"  Δm_min        : {measurements.get('_delta_m_min_fg',0):.2f} fg",
        f"  k             : {measurements.get('_k_N_per_m',0):.3e} N/m",
        f"  Q_air         : {measurements.get('_Q_air',0):.0f}",
        f"  Q_TED         : {measurements.get('_Q_TED',0):.0f}",
        f"  m_coat        : {measurements.get('_m_coat_pg',0):.1f} pg",
    ]

    ax_diag.text(0.05, 0.95, "\n".join(diag_lines), transform=ax_diag.transAxes,
                 va="top", ha="left", color=TEXT, fontsize=9.5,
                 fontfamily="monospace",
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#0d0d0d", alpha=0.9))

    # ── Far right: story ──────────────────────────────────────────────────
    ax_story = fig.add_subplot(gs[:, 2])
    ax_story.set_facecolor(DARK_PANEL)
    ax_story.axis("off")
    ax_story.set_title("The PFAS Problem", color=TEXT, fontsize=12, pad=10)

    story = (
        "PFAS ('forever chemicals') contaminate\n"
        "drinking water globally. The EPA set a\n"
        "limit of 4 ng/L for PFOA/PFOS in 2024.\n\n"
        "Current testing requires LC-MS/MS mass\n"
        "spectrometers: $300/sample, days to result.\n\n"
        "This AI-designed MEMS cantilever achieves\n"
        f"the EPA limit at {measurements.get('detection_limit',0):.2f} ng/L using only\n"
        "a vibrating silicon beam coated with a\n"
        "fluoropolymer that selectively captures\n"
        "PFAS molecules from water.\n\n"
        "PFAS lands on coating\n"
        "→ beam gets heavier\n"
        "→ resonant frequency drops\n"
        "→ concentration measured in real time\n\n"
        "No lab. No reagents. Chip-scale."
    )
    ax_story.text(0.05, 0.95, story, transform=ax_story.transAxes,
                  va="top", ha="left", color=TEXT, fontsize=10,
                  bbox=dict(boxstyle="round,pad=0.6", facecolor="#0d0d0d", alpha=0.9))

    fig.suptitle(f"PFAS Sensor Autoresearch — {specs.get('name','')}",
                 color=TEXT, fontsize=15, fontweight="bold", y=0.98)

    plt.savefig(f"{PLOTS_DIR}/sensor_hero.png", dpi=160,
                bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  Saved: {PLOTS_DIR}/sensor_hero.png")


def _plot_cantilever_3d(params):
    """3D schematic of the optimised cantilever."""
    fig = plt.figure(figsize=(10, 6), facecolor=DARK_BG)
    ax  = fig.add_subplot(111, projection="3d")
    ax.set_facecolor(DARK_BG)

    L = params.get("L_um", 100)
    w = params.get("w_um", 10)
    t = params.get("t_um", 1)
    h = params.get("h_coat_nm", 100) / 1000   # convert nm → μm for display

    def draw_box(ax, x0, y0, z0, dx, dy, dz, color, alpha=0.85, label=None):
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        verts = [
            [[x0,y0,z0],[x0+dx,y0,z0],[x0+dx,y0+dy,z0],[x0,y0+dy,z0]],
            [[x0,y0,z0+dz],[x0+dx,y0,z0+dz],[x0+dx,y0+dy,z0+dz],[x0,y0+dy,z0+dz]],
            [[x0,y0,z0],[x0+dx,y0,z0],[x0+dx,y0,z0+dz],[x0,y0,z0+dz]],
            [[x0,y0+dy,z0],[x0+dx,y0+dy,z0],[x0+dx,y0+dy,z0+dz],[x0,y0+dy,z0+dz]],
            [[x0,y0,z0],[x0,y0+dy,z0],[x0,y0+dy,z0+dz],[x0,y0,z0+dz]],
            [[x0+dx,y0,z0],[x0+dx,y0+dy,z0],[x0+dx,y0+dy,z0+dz],[x0+dx,y0,z0+dz]],
        ]
        poly = Poly3DCollection(verts, alpha=alpha, facecolor=color, edgecolor="#333")
        ax.add_collection3d(poly)

    # Silicon beam
    draw_box(ax, 0, 0, 0, L, w, t, "#7eb3d4", alpha=0.8)
    # Fluoropolymer coating (top face)
    draw_box(ax, 0, 0, t, L, w, h, "#ff6b35", alpha=0.7)
    # Anchor block
    draw_box(ax, -15, -5, -5, 15, w+10, t+10, "#444444", alpha=0.9)

    # PFAS molecules (dots on coating)
    rng = np.random.default_rng(42)
    n_dots = 30
    xs = rng.uniform(5, L-5, n_dots)
    ys = rng.uniform(1, w-1, n_dots)
    zs = np.full(n_dots, t + h + 0.5)
    ax.scatter(xs, ys, zs, color="#44ffaa", s=18, zorder=10, label="PFAS molecules")

    ax.set_xlabel("Length (μm)", color=TEXT, fontsize=9)
    ax.set_ylabel("Width (μm)", color=TEXT, fontsize=9)
    ax.set_zlabel("Height (μm)", color=TEXT, fontsize=9)
    ax.set_title(f"Cantilever: {L:.0f}×{w:.0f}×{t:.2f} μm  |  Coating: {h*1000:.0f} nm",
                 color=TEXT, fontsize=11)
    ax.tick_params(colors=TEXT, labelsize=7)
    for pane in [ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane]:
        pane.fill = False
        pane.set_edgecolor("#1a1a1a")

    legend_items = [
        mpatches.Patch(color="#7eb3d4", label="Silicon beam"),
        mpatches.Patch(color="#ff6b35", label="Fluoropolymer coating"),
        mpatches.Patch(color="#44ffaa", label="PFAS molecules"),
    ]
    ax.legend(handles=legend_items, facecolor=DARK_PANEL, labelcolor=TEXT, fontsize=8, loc="upper left")

    plt.savefig(f"{PLOTS_DIR}/cantilever_3d.png", dpi=150,
                bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  Saved: {PLOTS_DIR}/cantilever_3d.png")


def _plot_frequency_response(measurements, params):
    """Lorentzian frequency response before and after PFAS loading."""
    f0    = measurements.get("_f0_hz", 1e6)
    Q     = max(measurements.get("Q_factor", 100), 1)
    S     = measurements.get("sensitivity_hz_pg", 1)
    lod   = measurements.get("detection_limit", 4)

    # Mass added at EPA limit
    delta_f_at_epa = S * (lod * 1e-9 * 1e12)  # convert ng/L → pg (assume 1 mL sample)

    freqs   = np.linspace(f0 * 0.995, f0 * 1.005, 2000)
    gamma   = f0 / (2 * Q)

    def lorentz(f, f_center):
        return 1.0 / (1 + ((f - f_center) / gamma)**2)

    response_clean = lorentz(freqs, f0)
    response_pfas  = lorentz(freqs, f0 - delta_f_at_epa)

    fig, ax = plt.subplots(figsize=(10, 5), facecolor=DARK_BG)
    ax.set_facecolor(DARK_PANEL)

    ax.plot(freqs / 1e3, response_clean, color=ACCENT,  linewidth=2,   label="Clean water")
    ax.plot(freqs / 1e3, response_pfas,  color=ACCENT2, linewidth=2,   label=f"+ PFAS @ EPA limit ({lod:.1f} ng/L)")
    ax.axvline(f0 / 1e3,                color=ACCENT,  linestyle="--", linewidth=1, alpha=0.4)
    ax.axvline((f0 - delta_f_at_epa)/1e3, color=ACCENT2, linestyle="--", linewidth=1, alpha=0.4)

    ax.annotate("", xy=((f0 - delta_f_at_epa)/1e3, 0.5),
                xytext=(f0/1e3, 0.5),
                arrowprops=dict(arrowstyle="<->", color="white", lw=1.5))
    ax.text((f0 - delta_f_at_epa/2)/1e3, 0.53,
            f"Δf = {delta_f_at_epa:.1f} Hz",
            ha="center", color="white", fontsize=9)

    ax.set_xlabel("Frequency (kHz)", color=TEXT)
    ax.set_ylabel("Normalised response", color=TEXT)
    ax.set_title("Resonance Shift at EPA PFAS Limit", color=TEXT, fontsize=12)
    ax.tick_params(colors=TEXT)
    ax.legend(facecolor=DARK_PANEL, labelcolor=TEXT)
    for sp in ax.spines.values(): sp.set_color("#333")

    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/frequency_response.png", dpi=150,
                bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  Saved: {PLOTS_DIR}/frequency_response.png")


def _plot_sensitivity_sweep(params):
    """Heatmap of detection limit vs. L and t."""
    sim_func = load_model()

    L_vals = np.logspace(1, 2.7, 30)   # 10–500 μm
    t_vals = np.logspace(-0.7, 1, 30)   # 0.2–10 μm

    lod_map = np.zeros((len(t_vals), len(L_vals)))
    for i, t in enumerate(t_vals):
        for j, L in enumerate(L_vals):
            p = dict(params)
            p["L_um"] = L
            p["t_um"] = t
            try:
                r = sim_func(p)
                lod_map[i, j] = r["detection_limit"] if r else 999
            except Exception:
                lod_map[i, j] = 999

    lod_map = np.clip(lod_map, 0.01, 200)

    fig, ax = plt.subplots(figsize=(9, 6), facecolor=DARK_BG)
    ax.set_facecolor(DARK_BG)

    im = ax.contourf(L_vals, t_vals, np.log10(lod_map),
                     levels=30, cmap="RdYlGn_r")
    fig.colorbar(im, ax=ax, label="log₁₀ Detection Limit (ng/L)")
    ax.contour(L_vals, t_vals, lod_map,
               levels=[4.0], colors=["white"], linewidths=2)
    ax.text(L_vals[-5], t_vals[3], "EPA limit (4 ng/L)",
            color="white", fontsize=9, ha="right")

    # Mark best point
    best_L = params.get("L_um", 100)
    best_t = params.get("t_um", 1)
    ax.plot(best_L, best_t, "*", color=ACCENT, markersize=14, label="AI-optimised design")

    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Cantilever length L (μm)", color=TEXT)
    ax.set_ylabel("Thickness t (μm)", color=TEXT)
    ax.set_title("Detection Limit Map: L vs. t\n(green = better, white contour = EPA limit)",
                 color=TEXT, fontsize=11)
    ax.tick_params(colors=TEXT)
    ax.legend(facecolor=DARK_PANEL, labelcolor=TEXT)
    for sp in ax.spines.values(): sp.set_color("#333")

    plt.tight_layout()
    plt.savefig(f"{PLOTS_DIR}/sensitivity_map.png", dpi=150,
                bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  Saved: {PLOTS_DIR}/sensitivity_map.png")


# ─── Report ───────────────────────────────────────────────────────────────────

def print_report(params, measurements, score, details, specs, elapsed):
    print(f"\n{'═'*70}")
    print(f"  EVALUATION REPORT — {specs.get('name','Sensor')}")
    print(f"{'═'*70}")
    print(f"\n  Score: {score:.3f} / 1.00    Time: {elapsed:.1f}s\n")
    print(f"  {'Spec':<22} {'Target':>8} {'Measured':>12} {'Unit':>6}  Status")
    print(f"  {'─'*60}")
    for name, d in details.items():
        m = d["measured"]; ms = f"{m:.3f}" if m is not None else "N/A"
        print(f"  {name:<22} {d['target']:>8} {ms:>12} {d['unit']:>6}  "
              f"{'PASS ✓' if d['met'] else 'FAIL ✗'}")
    print(f"\n  Geometry:")
    for k, v in sorted(params.items()):
        print(f"    {k:<14} = {v:.4e}")
    print(f"\n{'═'*70}\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick",   action="store_true")
    parser.add_argument("--workers", type=int, default=-1)
    args = parser.parse_args()

    print("=" * 70)
    print("  PFAS Sensor Autoresearch — Evaluator")
    print("=" * 70 + "\n")

    sim_func   = load_model()
    param_defs = load_parameters()
    specs      = load_specs()

    print(f"  Target: {specs.get('name')}")
    print(f"  Params: {len(param_defs)}   Specs: {len(specs['measurements'])}\n")

    t0 = time.time()
    best_x, best_cost = run_de(param_defs, specs, quick=args.quick, n_workers=args.workers)
    elapsed = time.time() - t0

    best_params  = _vec_to_params(best_x, param_defs)
    measurements = sim_func(best_params) or {}
    score, details = score_measurements(measurements, specs)

    print_report(best_params, measurements, score, details, specs, elapsed)

    with open("best_parameters.json", "w") as f:
        json.dump({"parameters": best_params, "measurements": measurements,
                   "score": score}, f, indent=2)

    print("Generating visualizations...")
    generate_plots(None, measurements, best_params, specs, score)

    # Log
    try:
        import subprocess
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                         stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        commit = "unknown"

    specs_met = sum(1 for d in details.values() if d["met"])
    Path(RESULTS_FILE).touch()
    with open(RESULTS_FILE, "a") as f:
        ps = ", ".join(f"{k}={v:.3e}" for k, v in sorted(best_params.items()))
        f.write(f"{commit}\t{score:.3f}\t{specs.get('name')}\t"
                f"{specs_met}/{len(details)}\t{ps}\n")

    print(f"\nScore: {score:.3f}  ({'PASS' if score >= 0.9 else 'FAIL — keep iterating'})\n")
    return score


if __name__ == "__main__":
    score = main()
    sys.exit(0 if score >= 0.9 else 1)
