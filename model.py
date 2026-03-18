"""
model.py — MEMS Cantilever PFAS Sensor Model

Topology: Single rectangular silicon cantilever with single-sided fluoropolymer
          coating, thermomechanical noise-limited detection, conservative amplitude,
          and small array averaging. Traditional MEMS geometry (L/t >= 50).

          Vacuum-packaged design: air damping eliminated, Q limited by
          thermoelastic damping only. Realistic for hermetically sealed MEMS.

Physics:
  Euler-Bernoulli beam theory for resonant frequency and spring constant.
  Thermomechanical (Brownian) noise floor for minimum detectable frequency shift.
  Thermoelastic damping (Zener) for Q-factor — no air damping in vacuum.
  Partition coefficient model for PFAS concentration -> adsorbed mass.
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

# ─── Fluorinated coating properties ────────────────────────────────────────
RHO_COAT = 2100.0     # density of fluoropolymer (Teflon-like) [kg/m³]
K_PFAS   = 150.0      # PFAS partition coefficient (coating/water)

# ─── Measurement parameters ───────────────────────────────────────────────
BW       = 1.0        # measurement bandwidth [Hz] (1 s integration)
A_OSC    = 10e-9      # oscillation amplitude [m] (10 nm — conservative)


def run_simulation(params):
    """
    Single rectangular silicon cantilever, vacuum-packaged, with single-sided
    fluoropolymer coating and small array.

    params keys:
      L_um      : beam length [um]
      w_um      : beam width [um]
      t_um      : beam thickness [um]
      h_coat_nm : coating thickness [nm]
      N_array   : number of cantilevers in array
    """

    # ── Unit conversions to SI ─────────────────────────────────────────────
    L       = params['L_um']      * 1e-6
    w       = params['w_um']      * 1e-6
    t       = params['t_um']      * 1e-6
    h_coat  = params['h_coat_nm'] * 1e-9
    N_array = max(1, int(round(params['N_array'])))

    # ── Sanity checks ──────────────────────────────────────────────────────
    if L <= 0 or w <= 0 or t <= 0 or h_coat <= 0:
        return None
    if t > L:
        return None
    if L / t > 500 or L / t < 50:
        return None
    if h_coat > t * 0.15:
        return None

    # ── Beam mechanics ─────────────────────────────────────────────────────
    m_beam = RHO_SI * w * t * L
    k      = E_SI * w * t**3 / (4 * L**3)

    # ── Single-sided coating ───────────────────────────────────────────────
    A_coat = w * L
    m_coat = RHO_COAT * A_coat * h_coat
    m_total = m_beam + m_coat
    m_eff = 0.2357 * m_total

    if m_eff <= 0:
        return None

    # ── Resonant frequency ─────────────────────────────────────────────────
    f0 = (1 / (2 * np.pi)) * np.sqrt(k / m_eff)
    if f0 <= 0:
        return None

    # ── Mass sensitivity ───────────────────────────────────────────────────
    S_Hz_kg = f0 / (2 * m_eff)
    sensitivity_hz_pg = S_Hz_kg * 1e-12

    # ── Q-factor (vacuum — thermoelastic damping only) ─────────────────────
    omega0  = 2 * np.pi * f0
    tau_TED = RHO_SI * CP_SI * t**2 / (np.pi**2 * KAP_SI)
    xi      = omega0 * tau_TED

    Delta_E   = E_SI * ALPHA_SI**2 * T0 / (RHO_SI * CP_SI)
    Q_TED_inv = Delta_E * xi / (1 + xi**2)
    Q_TED     = 1.0 / Q_TED_inv if Q_TED_inv > 0 else 1e9

    # In vacuum, Q is limited only by TED (typically 10,000 - 1,000,000)
    # Add a practical upper limit of 100,000 for realistic electronics
    Q = min(Q_TED, 100000)

    # ── Thermomechanical noise-limited frequency resolution ────────────────
    delta_f_min = (1.0 / A_OSC) * np.sqrt(KB * T0 * f0 * BW / (np.pi * k * Q))

    # ── Minimum detectable mass ────────────────────────────────────────────
    delta_m_min = 2 * m_eff * delta_f_min / f0

    # ── Array averaging ───────────────────────────────────────────────────
    delta_m_min_array = delta_m_min / np.sqrt(N_array)

    # ── PFAS detection limit ──────────────────────────────────────────────
    V_coat = A_coat * h_coat
    V_coat_liters = V_coat * 1e3
    lod_ng_per_L = delta_m_min_array / (V_coat_liters * K_PFAS * 1e-9)

    # ── Package results ───────────────────────────────────────────────────
    return {
        'f0_khz':              f0 / 1e3,
        'Q_factor':            Q,
        'sensitivity_hz_pg':   sensitivity_hz_pg,
        'detection_limit':     lod_ng_per_L,
        '_f0_hz':              f0,
        '_m_eff_pg':           m_eff * 1e12,
        '_k_N_per_m':          k,
        '_Q_air':              0,
        '_Q_TED':              Q_TED,
        '_delta_m_min_fg':     delta_m_min_array * 1e15,
        '_m_coat_pg':          m_coat * 1e12,
    }
