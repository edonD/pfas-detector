# PFAS Sensor Autoresearch

**An AI agent that autonomously designs a MEMS cantilever sensor for PFAS detection in drinking water. Every cantilever geometry is discovered by Differential Evolution — no human touched the dimensions.**

---

## Latest Results

> *Updated automatically after every experiment.*

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Score | — | ≥ 0.90 | — |
| Detection limit | — ng/L | < 4.0 ng/L | — |
| Resonant frequency | — kHz | > 100 kHz | — |
| Q-factor | — | > 50 | — |
| Sensitivity | — Hz/pg | > 1.0 Hz/pg | — |

---

## Hero Visualization

![Sensor Hero](plots/sensor_hero.png)

---

## Cantilever 3D Render

![Cantilever 3D](plots/cantilever_3d.png)

---

## Frequency Response at EPA Limit

![Frequency Response](plots/frequency_response.png)

---

## Detection Limit Map

![Sensitivity Map](plots/sensitivity_map.png)

---

## Optimised Geometry

| Parameter | Value |
|-----------|-------|
| Length (L) | — μm |
| Width (w) | — μm |
| Thickness (t) | — μm |
| Coating thickness | — nm |
| χ topology | Rectangular beam |

---

## Key Ratios

| Ratio | Value | Meaning |
|-------|-------|---------|
| L/t (aspect ratio) | — | Slender beam regime (< 500) |
| f₀ | — kHz | Practical readout range |
| Δm_min | — fg | Minimum detectable mass |

---

## Experiment Log

| Commit | Score | Topology | Specs Met | L (μm) | t (μm) | LOD (ng/L) | Insight |
|--------|-------|----------|-----------|--------|--------|------------|---------|
| — | — | baseline | — | — | — | — | — |

---

## The Problem

PFAS ("forever chemicals") contaminate drinking water globally. The EPA set a maximum contaminant level of **4 ng/L** for PFOA/PFOS in 2024 — 4 parts per trillion.

Current testing costs $300/sample and takes days. There is no rapid, portable field sensor.

## The Solution

A silicon microcantilever coated with a fluoropolymer. PFAS molecules are selectively captured by the fluorine-rich coating. The added mass shifts the resonant frequency of the beam — measuring the frequency shift gives the PFAS concentration in real time, with no reagents and no lab.

```
PFAS in water → adsorbs on fluoropolymer coating
             → beam gets heavier
             → resonant frequency drops: Δf = −(f₀/2m_eff) × Δm
             → concentration = mass / (coating volume × partition coefficient)
```

## Technology

- **Beam physics**: Euler-Bernoulli beam theory (exact for slender beams)
- **Mass sensing**: Sauerbrey equation
- **Q-factor**: Sader viscous damping + thermoelastic damping
- **Optimizer**: Differential Evolution (16 EC2 CPUs)
- **Evaluator**: Pure Python analytical model (microseconds per evaluation)
- **Process**: AI changes geometry topology → DE finds dimensions → evaluator scores
