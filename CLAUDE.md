# PFAS Sensor Autoresearch

Read `program.md` completely before doing anything.

## Quick Start
1. Read `program.md` — understand the physics and the loop
2. Read `specs.json` — know the target (detection limit < 4 ng/L, f₀ > 100 kHz, Q > 50)
3. Read `model.py` — understand the cantilever physics model
4. Read `parameters.csv` — understand what DE sweeps (L, w, t, h_coat in μm/nm)
5. Run `python3 evaluate.py --quick` for a fast baseline
6. Begin the experiment loop

## Key Commands
```bash
python3 evaluate.py --quick 2>&1 | tee run.log   # fast (30 gen)
python3 evaluate.py 2>&1 | tee run.log            # full (500 gen, all 16 CPUs)
```

## Output
- `best_parameters.json` — best geometry found by DE
- `plots/sensor_hero.png` — scorecard + geometry + comparison to existing methods
- `plots/cantilever_3d.png` — 3D render of the cantilever with PFAS molecules
- `plots/frequency_response.png` — resonance shift at EPA limit
- `plots/sensitivity_map.png` — LOD heatmap across geometry space

## Rules
- Modify ONLY `model.py` and `parameters.csv`
- NEVER edit `evaluate.py`, `specs.json`, or `program.md`
- NEVER set parameter values yourself — define ranges, let DE find values
- ALWAYS update `README.md` after each run and commit everything
- Work on `dev` branch
- NEVER stop
