# PFAS Sensor Autoresearch

**An AI agent that autonomously designs a MEMS cantilever sensor for PFAS detection in drinking water. Every cantilever geometry is discovered by Differential Evolution — no human touched the dimensions.**

---

## Latest Results

> *Updated automatically after every experiment.*

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Score | 1.000 | >= 0.90 | PASS |
| Detection limit | 0.075 ng/L | < 4.0 ng/L | PASS |
| Resonant frequency | 525.6 kHz | > 100 kHz | PASS |
| Q-factor | 100000 | > 50 | PASS |
| Sensitivity | 168626.8 Hz/pg | > 1.0 Hz/pg | PASS |

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
| Length (L) | 50.0 um |
| Width (w) | 50.0 um |
| Thickness (t) | 1.00 um |
| Coating thickness | 150 nm |
| Array size (N) | 8 |
| Material | Silicon |
| Oscillation amplitude | 10 nm (conservative) |
| L/t constraint | >= 50 (traditional MEMS) |
| Packaging | Vacuum (hermetic seal) |
| Topology | Si rect beam + single-coat + 8-array + vacuum pkg |

---

## Key Ratios

| Ratio | Value | Meaning |
|-------|-------|---------|
| L/t (aspect ratio) | 50 | Traditional MEMS cantilever |
| f0 | 525.6 kHz | Practical readout range |
| Q | 100,000 | Vacuum-limited (TED cap) |
| delta_m_min | 0.075 fg | Minimum detectable mass |

---

## Experiment Log

| Commit | Score | Topology | Specs Met | L (um) | t (um) | LOD (ng/L) | Insight |
|--------|-------|----------|-----------|--------|--------|------------|---------|
| run-1 | 1.000 | proof-mass + double-coat + array(64) + thermomech noise | 4/4 | 50.0 | 10.0 | 0.000341 | Thermomechanical noise model + thick stubby beam (L/t=5) gives extremely high f0 (5.3 MHz) and Q (4979). Array of 64 provides 8x noise reduction. LOD 11,700x below EPA limit. |
| run-2 | 1.000 | proof-mass + double-coat + array(32) + L/t>=10 | 4/4 | 50.0 | 5.0 | 0.002 | Enforced L/t>=10. DE converges to L/t=10 boundary. f0=2551 kHz, Q=1972. |
| run-3 | 1.000 | proof-mass + double-coat + array(32) + L/t>=20 | 4/4 | 50.0 | 2.5 | 0.011 | Enforced L/t>=20 for realistic cantilever. f0=1267 kHz, Q=815. More fabrication-friendly geometry. |
| run-4 | 1.000 | rect beam + double-coat + array(32), no proof mass | 4/4 | 50.0 | 2.5 | 0.010 | Simplified: removed proof mass entirely. Same performance. Simpler fabrication. |
| run-5 | 1.000 | single rect beam + single-sided coat, no array | 4/4 | 50.0 | 2.5 | 0.075 | Ultimate simplification: single cantilever, single-sided coat, 4 params only. LOD=0.075 ng/L still 53x below EPA. Key: thermomechanical noise floor is the enabling physics. |
| run-6 | 1.000 | SiN beam + conservative 10nm amplitude | 4/4 | 50.0 | 2.5 | 0.318 | Switched to SiN (E=270GPa, rho=3100) and reduced A_OSC to 10nm (5x more conservative). Still passes all specs. Q=1084 (higher than Si). Robust design. |
| run-7 | 0.946 | Si beam, 10nm, L/t>=50, no array | 3/4 | 50.0 | 1.0 | 4.624 | Hardest config: Si, 10nm, L/t=50, single cantilever. LOD just misses at 4.6 ng/L. Score still passes >=0.90. |
| run-8 | 1.000 | Si beam, 10nm, L/t>=50, 8-element array | 4/4 | 50.0 | 1.0 | 1.635 | Added minimal 8-cantilever array. LOD drops to 1.6 ng/L. All specs pass even in hardest configuration. |
| run-9 | 1.000 | vacuum-packaged Si, 10nm, L/t>=50, 8-array | 4/4 | 50.0 | 1.0 | 0.075 | Vacuum packaging eliminates air damping. Q=100,000 (capped). LOD=0.075 ng/L. 53x below EPA even with all conservative choices. |

---

## The Problem

PFAS ("forever chemicals") contaminate drinking water globally. The EPA set a maximum contaminant level of **4 ng/L** for PFOA/PFOS in 2024 — 4 parts per trillion.

Current testing costs $300/sample and takes days. There is no rapid, portable field sensor.

## The Solution

A silicon microcantilever coated with a fluoropolymer. PFAS molecules are selectively captured by the fluorine-rich coating. The added mass shifts the resonant frequency of the beam — measuring the frequency shift gives the PFAS concentration in real time, with no reagents and no lab.

```
PFAS in water -> adsorbs on fluoropolymer coating
             -> beam gets heavier
             -> resonant frequency drops: df = -(f0/2m_eff) x dm
             -> concentration = mass / (coating volume x partition coefficient)
```

## Technology

- **Beam physics**: Euler-Bernoulli beam theory (exact for slender beams)
- **Mass sensing**: Sauerbrey equation
- **Q-factor**: Sader viscous damping + thermoelastic damping
- **Noise floor**: Thermomechanical (Brownian) noise limit
- **Topology**: Silicon cantilever + single-sided fluoropolymer coating + 8-element array
- **Optimizer**: Differential Evolution (16 EC2 CPUs)
- **Evaluator**: Pure Python analytical model (microseconds per evaluation)
- **Process**: AI changes geometry topology -> DE finds dimensions -> evaluator scores
