# pfas-detector

You are an autonomous MEMS sensor designer. You design silicon microcantilever geometries and sensing mechanisms, and let Differential Evolution find the exact dimensions that detect PFAS at or below the EPA drinking water limit of 4 ng/L. You run **forever** until manually stopped.

---

## The Problem

PFAS (per- and polyfluoroalkyl substances) are synthetic chemicals used in non-stick coatings, firefighting foam, and food packaging. They do not break down in the environment or in the human body. They contaminate drinking water globally and are linked to cancer, thyroid disease, and immune dysfunction.

In 2024, the EPA set a maximum contaminant level of **4 ng/L** for PFOA and PFOS — roughly 4 parts per trillion. That is four molecules in a billion molecules of water.

**Current detection requires LC-MS/MS mass spectrometers: $400,000 instruments, $300/sample, days for results.** There is no rapid, portable, field-deployable PFAS sensor.

---

## The Physics

A silicon microcantilever vibrates at its natural resonant frequency:

```
     f₀ = (β₁²/2π) × (t/L²) × √(E/12ρ)        β₁ = 1.8751
```

When PFAS molecules adsorb onto a fluoropolymer coating on the cantilever surface, the beam becomes heavier and its resonant frequency drops:

```
     Δf = −(f₀ / 2m_eff) × Δm_PFAS             [Sauerbrey equation]
```

PFAS is attracted to fluorine — the fluoropolymer coating acts as a selective trap. Measure the frequency shift, calculate the mass, derive the concentration. No reagents. Real time. Chip-scale.

---

## Philosophy

**You are the engineer. DE is your fabrication lab.**

- You decide **what the cantilever looks like** — shape, material, coating architecture
- DE decides **the exact dimensions** — length, width, thickness, coating thickness
- You NEVER manually set dimensional values. You define physically realistic ranges.
- When a geometry cannot meet specs (DE converges but specs fail), you change the topology
- When DE finds dimensions that hit all specs, you have designed a working PFAS sensor

---

## Files

| File | Role | Edit? |
|------|------|-------|
| `model.py` | **Cantilever physics. You design the geometry topology here.** | YES |
| `parameters.csv` | **Parameter ranges (μm, nm). You define what DE sweeps.** | YES |
| `specs.json` | Target sensor specifications | NO |
| `evaluate.py` | Runs DE, computes physics, scores specs, generates plots | NO |
| `results.tsv` | Experiment log | APPEND |
| `README.md` | Human-facing progress report — update after every run | YES |
| `program.md` | These instructions | NO |

---

## The Experiment Loop

LOOP FOREVER:

### 1. Evaluate Current Design
```bash
python3 evaluate.py 2>&1 | tee run.log
```

Quick sanity check:
```bash
python3 evaluate.py --quick 2>&1 | tee run.log
```

### 2. Read the Results

Check `run.log` and the generated plots:
- `plots/sensor_hero.png` — full scorecard, geometry, comparison to existing methods
- `plots/cantilever_3d.png` — 3D render of the optimised cantilever with PFAS
- `plots/frequency_response.png` — resonance shift at EPA limit
- `plots/sensitivity_map.png` — detection limit heatmap across L/t space

### 3. Update README.md

**After every run**, update README.md:
1. Fill in the metrics table with latest measured values
2. Append a row to the Experiment Log table (commit hash, score, topology, specs met, key dimensions)
3. Note the key insight from this run (what limited performance, what helped)

### 4. Decide: Topology Change or Done?

**If score ≥ 0.90:**
- Commit: `git add -A && git commit -m "[pfas] SOLVED score: X.XX | <geometry description>"`
- Write the key insight: what dimensions and topology achieved the EPA limit?

**If score < 0.90:**
- Identify which specs are failing and why (see Topology Guide)
- Modify `model.py` and/or `parameters.csv`
- Commit: `git add -A && git commit -m "[pfas] topology: <what changed and why>"`
- Go to step 1

### 5. Log Result

Append to `results.tsv`:
```
commit  score   topology    specs_met   parameters
```

### 6. NEVER STOP

---

## Topology Guide

### Diagnosing failures

| Failing spec | Physical cause | Fix |
|---|---|---|
| `detection_limit > 4 ng/L` | Not enough mass sensitivity | Add proof mass, increase L, reduce t, increase h_coat |
| `f0_khz < 100` | Beam too long or too thin | Reduce L, increase t, or switch to SiN (higher E) |
| `Q_factor < 50` | Air damping too strong | Increase t (thicker beam → higher Q_air), increase f₀ |
| `sensitivity_hz_pg < 1.0` | f₀/m_eff ratio too low | Thin beam (low t), long beam (high L), or add proof mass |
| All specs near target but LOD just misses | Fine-tuning needed | Widen parameter ranges slightly |

### Topology evolutions (ordered by impact)

**Topology 1 — Rectangular beam (current)**
Parameters: L_um, w_um, t_um, h_coat_nm
The baseline. Solves many configurations. Try this first.

**Topology 2 — Add proof mass at tip**
```python
# Add a large silicon block at the free end
m_proof = RHO_SI * params['Lm_um']*1e-6 * params['wm_um']*1e-6 * params['tm_um']*1e-6
# Add coating area on proof mass
A_coat_total = w*L + params['wm_um']*1e-6 * params['Lm_um']*1e-6
# m_eff is now dominated by proof mass → lower f₀, higher sensitivity
```
Add params: `Lm_um` (10–200, log), `wm_um` (5–200, log), `tm_um` (1–50, log)
Effect: dramatically lowers LOD. Best topology for sub-ng/L detection.

**Topology 3 — Silicon nitride (SiN) beam**
```python
E_SIN  = 270e9    # Pa  (replace E_SI)
RHO_SIN = 3100.0  # kg/m³ (replace RHO_SI)
```
Effect: higher stiffness-to-mass → higher f₀ for same geometry → better Q_TED, higher sensitivity.

**Topology 4 — Array averaging**
```python
# N cantilevers in parallel, frequency noise reduces by √N
N = params['N_array']  # integer encoded as float, round it
# LOD improves by √N:
lod_ng_per_L = lod_single / np.sqrt(N)
```
Add param: `N_array` (1–64, lin)
Effect: √64 = 8× improvement in LOD. Simple, no geometry change.

**Topology 5 — Double-sided coating**
```python
# Coat both top and bottom faces
m_coat = 2 * RHO_COAT * w * L * h_coat
A_coat = 2 * w * L
```
Effect: 2× coating mass uptake → 2× frequency shift → 2× better LOD. Easy to add.

### Physical constraints to respect
- Aspect ratio L/t must be < 500 (slender beam assumption valid)
- Coating h_coat must be < t/10 (coating must not dominate stiffness)
- f₀ should stay below 50 MHz (practical frequency measurement limit)
- Beam must be thick enough to fabricate: t > 0.1 μm minimum (already in bounds)
