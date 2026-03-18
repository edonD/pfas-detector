"""
model.py — MEMS Cantilever PFAS Sensor Model

Topology: Proof-mass cantilever with double-sided fluoropolymer coating,
          thermomechanical noise-limited detection, and array averaging.

Physics:
  Euler-Bernoulli beam + lumped proof mass for resonant frequency.
  Thermomechanical (Brownian) noise floor for minimum detectable frequency shift.
  Sader/viscous + thermoelastic damping for Q-factor in air.
  Partition coefficient model for PFAS concentration → adsorbed mass.
  Array averaging: √N improvement in frequency noise.
  Double-sided coating: 2× mass uptake area.
"""

import numpy as np

# ─── Physical constants ────────────────────────────────────────────────────
KB = 1.381e-23   # Boltzmann constant [J/K]

# ─── Material constants (silicon) ──────────────────────────────────────────
E_SI     = 170e9      # Young's modulus [Pa]
RHO_SI   = 2330.0     # density [kg/m³]
ALPHA_SI = 2.6e-6     # thermal expansion coefficient [K⁻¹]
KAP_SI   = 148.0      # thermal conductivity [W/(m·K)]
CP_SI    = 700.0      # specific heat [J/(kg·K)]
T0       = 300.0      # ambient temperature [K]

# ─── Air properties ────────────────────────────────────────────────────────
ETA_AIR  = 1.81e-5    # dynamic viscosity [Pa·s]
RHO_AIR  = 1.225      # density [kg/m³]

# ─── Fluorinated coating properties ────────────────────────────────────────
RHO_COAT = 2100.0     # density of fluoropolymer (Teflon-like) [kg/m³]
K_PFAS   = 150.0      # PFAS partition coefficient (coating/water)

# ─── Measurement parameters ───────────────────────────────────────────────
BW       = 1.0        # measurement bandwidth [Hz] (1 s integration)
A_OSC    = 50e-9      # oscillation amplitude [m] (50 nm typical for MEMS)


def run_simulation(params):
    """
    Proof-mass silicon cantilever with double-sided fluoropolymer coating
    and array averaging.

    params keys:
      L_um      : beam length [μm]
      w_um      : beam width [μm]
      t_um      : beam thickness [μm]
      h_coat_nm : coating thickness [nm]
      Lm_um     : proof mass length [μm]
      wm_um     : proof mass width [μm]
      tm_um     : proof mass thickness [μm]
      N_array   : number of cantilevers in array (rounded to int)
    """

    # ── Unit conversions to SI ─────────────────────────────────────────────
    L       = params['L_um']      * 1e-6   # [m]
    w       = params['w_um']      * 1e-6   # [m]
    t       = params['t_um']      * 1e-6   # [m]
    h_coat  = params['h_coat_nm'] * 1e-9   # [m]
    Lm      = params['Lm_um']     * 1e-6   # proof mass length [m]
    wm      = params['wm_um']     * 1e-6   # proof mass width [m]
    tm      = params['tm_um']     * 1e-6   # proof mass thickness [m]
    N_array = max(1, int(round(params['N_array'])))

    # ── Sanity checks ──────────────────────────────────────────────────────
    if L <= 0 or w <= 0 or t <= 0 or h_coat <= 0:
        return None
    if t > L:
        return None
    if L / t > 500 or L / t < 20:
        return None
    if h_coat > t * 0.1:
        return None

    # ── Beam mechanics ─────────────────────────────────────────────────────
    m_beam = RHO_SI * w * t * L
    k      = E_SI * w * t**3 / (4 * L**3)   # spring constant

    # ── Proof mass ─────────────────────────────────────────────────────────
    m_proof = RHO_SI * Lm * wm * tm

    # ── Double-sided coating ───────────────────────────────────────────────
    # Coat both top and bottom of beam + top of proof mass
    A_coat_beam  = 2 * w * L           # double-sided beam coating area
    A_coat_proof = wm * Lm             # top of proof mass
    A_coat_total = A_coat_beam + A_coat_proof

    m_coat = RHO_COAT * A_coat_total * h_coat

    # ── Total effective mass ───────────────────────────────────────────────
    # For cantilever with tip mass: m_eff = 0.2357*m_beam + m_proof + m_coat_on_proof
    # Proof mass is at the tip → contributes fully to effective mass
    m_coat_beam  = RHO_COAT * A_coat_beam * h_coat
    m_coat_proof = RHO_COAT * A_coat_proof * h_coat
    m_eff = 0.2357 * (m_beam + m_coat_beam) + m_proof + m_coat_proof

    if m_eff <= 0:
        return None

    # ── Resonant frequency ─────────────────────────────────────────────────
    f0 = (1 / (2 * np.pi)) * np.sqrt(k / m_eff)

    if f0 <= 0:
        return None

    # ── Mass sensitivity (Sauerbrey) ───────────────────────────────────────
    S_Hz_kg = f0 / (2 * m_eff)
    sensitivity_hz_pg = S_Hz_kg * 1e-12

    # ── Q-factor ───────────────────────────────────────────────────────────
    omega0  = 2 * np.pi * f0
    tau_TED = RHO_SI * CP_SI * t**2 / (np.pi**2 * KAP_SI)
    xi      = omega0 * tau_TED

    # Thermoelastic damping (Zener)
    Delta_E   = E_SI * ALPHA_SI**2 * T0 / (RHO_SI * CP_SI)
    Q_TED_inv = Delta_E * xi / (1 + xi**2)
    Q_TED     = 1.0 / Q_TED_inv if Q_TED_inv > 0 else 1e9

    # Viscous air damping (Sader, simplified)
    denom_air = np.sqrt(RHO_AIR * ETA_AIR / (np.pi * f0))
    Q_air     = (RHO_SI * t) / (3.0 * denom_air) if denom_air > 0 else 1e9

    # Total Q
    Q = 1.0 / (1.0 / Q_air + 1.0 / Q_TED)

    # ── Thermomechanical noise-limited frequency resolution ────────────────
    # δf = (1/A) × √(kB × T × f0 × BW / (π × k × Q))
    # This is the fundamental Brownian noise floor for a resonant sensor
    delta_f_min = (1.0 / A_OSC) * np.sqrt(KB * T0 * f0 * BW / (np.pi * k * Q))

    # ── Minimum detectable mass ────────────────────────────────────────────
    delta_m_min = 2 * m_eff * delta_f_min / f0

    # ── Array averaging: √N noise reduction ────────────────────────────────
    delta_m_min_array = delta_m_min / np.sqrt(N_array)

    # ── PFAS detection limit ───────────────────────────────────────────────
    # Total coating volume (double-sided beam + proof mass top)
    V_coat = A_coat_total * h_coat
    V_coat_liters = V_coat * 1e3

    # LOD [ng/L] = Δm_min / (V_coat_L × K_PFAS × 1e-9)
    lod_ng_per_L = delta_m_min_array / (V_coat_liters * K_PFAS * 1e-9)

    # ── Package results ────────────────────────────────────────────────────
    return {
        'f0_khz':              f0 / 1e3,
        'Q_factor':            Q,
        'sensitivity_hz_pg':   sensitivity_hz_pg,
        'detection_limit':     lod_ng_per_L,
        '_f0_hz':              f0,
        '_m_eff_pg':           m_eff * 1e12,
        '_k_N_per_m':          k,
        '_Q_air':              Q_air,
        '_Q_TED':              Q_TED,
        '_delta_m_min_fg':     delta_m_min_array * 1e15,
        '_m_coat_pg':          m_coat * 1e12,
    }
