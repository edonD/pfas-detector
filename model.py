"""
model.py — MEMS Cantilever PFAS Sensor Model

YOU EDIT THIS FILE to change the cantilever topology.

Defines one function: run_simulation(params) → dict of physical measurements.

Physics basis:
  Euler-Bernoulli beam theory for resonant frequency and spring constant.
  Sauerbrey equation for mass sensitivity.
  Sader/viscous model for Q-factor in air.
  Partition coefficient model for PFAS concentration → adsorbed mass.

All units are SI internally (meters, kg, Hz, Pa).
Parameters in parameters.csv use practical units — conversions are done here.

TOPOLOGY — WHAT YOU CAN CHANGE:
  The cantilever geometry and sensing mechanism. Start simple, add complexity only
  when DE cannot meet specs with the current topology.

  1. Rectangular beam (current — baseline)
       Standard silicon cantilever. Parameters: L, w, t, h_coat.
       Best for: simplicity, well-understood fabrication.

  2. Add proof mass at tip
       A large silicon block at the free end.
       Effect: lowers frequency (k unchanged, m >> m_beam), increases coating area.
       Add params: L_mass, w_mass, t_mass (proof mass dimensions in μm).

  3. Paddle beam (T-shape)
       Wide sensing pad at tip, narrow stem connecting to anchor.
       Effect: large coating area on paddle, high sensitivity.
       Modify: split into stem (L_stem, w_stem) + paddle (L_pad, w_pad).

  4. Double-sided coating
       Coat both top and bottom faces.
       Effect: 2× the mass uptake → 2× the frequency shift.
       Modify: double the coating mass contribution.

  5. Array of cantilevers
       N identical cantilevers in parallel, signals averaged.
       Effect: √N improvement in frequency noise (LOD improves by √N).
       Add param: N_array (integer 1–100).

  6. Change material: silicon nitride (SiN)
       E = 270 GPa, ρ = 3100 kg/m³ — higher stiffness-to-mass ratio.
       Effect: higher f₀ for same geometry → better sensitivity.
       Modify: E and rho_beam constants.

WHEN TO CHANGE TOPOLOGY:
  - detection_limit > 4 ng/L AND f0 already in range → add proof mass or array
  - Q_factor too low → try SiN (higher E, better TED), or increase t
  - sensitivity too low → add proof mass, paddle design, or double coating
  - f0 out of range → adjust L and t ranges in parameters.csv
"""

import numpy as np

# ─── Material constants (silicon, default) ───────────────────────────────────
E_SI     = 170e9      # Young's modulus [Pa]
RHO_SI   = 2330.0     # density [kg/m³]
ALPHA_SI = 2.6e-6     # thermal expansion coefficient [K⁻¹]
KAP_SI   = 148.0      # thermal conductivity [W/(m·K)]
CP_SI    = 700.0      # specific heat [J/(kg·K)]
T0       = 300.0      # ambient temperature [K]

# ─── Air properties ──────────────────────────────────────────────────────────
ETA_AIR  = 1.81e-5    # dynamic viscosity [Pa·s]
RHO_AIR  = 1.225      # density [kg/m³]

# ─── Fluorinated coating properties ──────────────────────────────────────────
RHO_COAT = 2100.0     # density of fluoropolymer (Teflon-like) [kg/m³]
K_PFAS   = 150.0      # PFAS partition coefficient (coating/water) — typical for fluoropolymer


def run_simulation(params):
    """
    Rectangular silicon cantilever with fluorinated PFAS-selective coating.

    params keys (all in practical units, converted to SI here):
      L_um      : cantilever length [μm]
      w_um      : cantilever width [μm]
      t_um      : cantilever thickness [μm]
      h_coat_nm : coating thickness [nm]

    Returns dict with keys matching specs.json measurement names.
    Returns None for physically unrealistic geometries.
    """

    # ── Unit conversions to SI ─────────────────────────────────────────────
    L       = params['L_um']      * 1e-6   # [m]
    w       = params['w_um']      * 1e-6   # [m]
    t       = params['t_um']      * 1e-6   # [m]
    h_coat  = params['h_coat_nm'] * 1e-9   # [m]

    # ── Sanity checks ──────────────────────────────────────────────────────
    if L <= 0 or w <= 0 or t <= 0 or h_coat <= 0:
        return None
    if t > L or w > L:          # physically nonsensical proportions
        return None
    if t > 0.5 * w:             # thick beams violate slender beam assumption
        pass                    # allow but accuracy degrades — DE will learn

    # ── Euler-Bernoulli beam: resonant frequency ───────────────────────────
    # First bending mode: f₀ = (β₁²/2π) × (t/L²) × √(E/12ρ)
    # β₁L = 1.8751 (clamped-free boundary condition)
    beta1 = 1.8751
    I     = w * t**3 / 12          # second moment of area [m⁴]
    A     = w * t                  # cross-sectional area [m²]
    m_beam = RHO_SI * A * L        # total beam mass [kg]

    f0_bare = (beta1**2 / (2 * np.pi)) * np.sqrt(E_SI * I / (RHO_SI * A * L**4))

    # ── Coating mass and frequency shift ──────────────────────────────────
    # Coating on top face only (standard single-sided functionalization)
    m_coat  = RHO_COAT * w * L * h_coat
    m_total = m_beam + m_coat

    # Effective mass for first mode (0.2357 × total for Euler-Bernoulli)
    m_eff   = 0.2357 * m_total

    # Spring constant (coating negligibly stiff relative to silicon beam)
    k       = E_SI * w * t**3 / (4 * L**3)

    # Coated resonant frequency
    f0      = (1 / (2 * np.pi)) * np.sqrt(k / m_eff)

    # ── Mass sensitivity (Sauerbrey) ──────────────────────────────────────
    # S [Hz/kg] = f₀ / (2 × m_eff)
    # S_pgHz [Hz/pg] = S × 1e-12
    S_Hz_kg = f0 / (2 * m_eff)
    sensitivity_hz_pg = S_Hz_kg * 1e-12     # Hz per picogram

    # ── Q-factor (air damping) ─────────────────────────────────────────────
    # Viscous air damping (Sader model, simplified):
    #   Q_air ≈ (ρ_Si × t) / (C × √(ρ_air × η_air / (π × f₀)))
    # Thermoelastic damping (Zener):
    #   Q_TED = (ρ_Si × Cp × E_Si × α²× T₀)⁻¹ × (1 + (ω₀τ)²)/(ω₀τ)
    omega0    = 2 * np.pi * f0
    tau_TED   = RHO_SI * CP_SI * t**2 / (np.pi**2 * KAP_SI)  # thermal relaxation time
    xi        = omega0 * tau_TED

    # Q_TED
    Delta_E   = E_SI * ALPHA_SI**2 * T0 / (RHO_SI * CP_SI)
    Q_TED_inv = Delta_E * xi / (1 + xi**2)
    Q_TED     = 1.0 / Q_TED_inv if Q_TED_inv > 0 else 1e9

    # Q_air (viscous drag, simplified Sader)
    denom_air = np.sqrt(RHO_AIR * ETA_AIR / (np.pi * f0))
    Q_air     = (RHO_SI * t) / (3.0 * denom_air) if denom_air > 0 else 1e9

    # Total Q (dominant mechanism sets Q)
    Q = 1.0 / (1.0 / Q_air + 1.0 / Q_TED)

    # ── Minimum detectable frequency shift ────────────────────────────────
    # Practical frequency resolution: Δf_min ≈ f₀/(2Q)  (resonance half-linewidth)
    delta_f_min = f0 / (2 * Q)

    # ── PFAS detection limit in water ────────────────────────────────────
    # Δm_min [kg] = 2 × m_eff × Δf_min / f₀
    delta_m_min = 2 * m_eff * delta_f_min / f0   # [kg]

    # Active coating volume [m³]
    V_coat = w * L * h_coat

    # PFAS mass in coating at concentration C [ng/L]:
    #   Δm_PFAS = C [ng/L] × V_coat [m³] × K_PFAS × ρ_water [kg/m³] / 1e6
    #   (K_PFAS = mass fraction coating / mass fraction water)
    # Simplify: Δm_PFAS [kg] = C [ng/L] × V_coat [L] × K_PFAS × 1e-9
    V_coat_liters = V_coat * 1e3   # m³ → L

    # Detection limit [ng/L]: concentration at which Δm_PFAS = delta_m_min
    # delta_m_min = LOD [ng/L] × V_coat_liters × K_PFAS × 1e-9
    # LOD = delta_m_min / (V_coat_liters × K_PFAS × 1e-9)
    lod_ng_per_L = delta_m_min / (V_coat_liters * K_PFAS * 1e-9)

    # ── Package results ────────────────────────────────────────────────────
    return {
        'f0_khz':              f0 / 1e3,               # [kHz]
        'Q_factor':            Q,                      # [—]
        'sensitivity_hz_pg':   sensitivity_hz_pg,      # [Hz/pg]
        'detection_limit':     lod_ng_per_L,           # [ng/L]
        # Extra diagnostics (not in specs, but useful for analysis)
        '_f0_hz':              f0,
        '_m_eff_pg':           m_eff * 1e12,           # [pg]
        '_k_N_per_m':          k,                      # [N/m]
        '_Q_air':              Q_air,
        '_Q_TED':              Q_TED,
        '_delta_m_min_fg':     delta_m_min * 1e15,     # [fg]
        '_m_coat_pg':          m_coat * 1e12,          # [pg]
    }
