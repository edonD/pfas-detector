"""
model.py — MEMS Cantilever PFAS Sensor Model

Topology: Single rectangular silicon nitride (SiN) cantilever with double-sided
          fluoropolymer coating, thermomechanical noise-limited detection,
          and small array averaging. Field-deployable design (air operation).

Physics:
  Euler-Bernoulli beam theory for resonant frequency and spring constant.
  Thermomechanical (Brownian) noise floor for minimum detectable frequency shift.
  Sader/viscous + thermoelastic damping for Q-factor in air.
  Partition coefficient model for PFAS concentration -> adsorbed mass.
"""

import numpy as np

# ─── Physical constants ────────────────────────────────────────────────────
KB = 1.381e-23   # Boltzmann constant [J/K]

# ─── Material constants (silicon nitride) ──────────────────────────────────
E_BEAM     = 270e9      # Young's modulus [Pa]
RHO_BEAM   = 3100.0     # density [kg/m³]
ALPHA_BEAM = 2.3e-6     # thermal expansion coefficient [K⁻¹]
KAP_BEAM   = 30.0       # thermal conductivity [W/(m·K)]
CP_BEAM    = 700.0      # specific heat [J/(kg·K)]
T0         = 300.0      # ambient temperature [K]

# ─── Air properties ────────────────────────────────────────────────────────
ETA_AIR  = 1.81e-5    # dynamic viscosity [Pa·s]
RHO_AIR  = 1.225      # density [kg/m³]

# ─── Fluorinated coating properties ────────────────────────────────────────
RHO_COAT = 2100.0     # density of fluoropolymer (Teflon-like) [kg/m³]
K_PFAS   = 150.0      # PFAS partition coefficient (coating/water)

# ─── Measurement parameters ───────────────────────────────────────────────
BW       = 1.0        # measurement bandwidth [Hz] (1 s integration)
A_OSC    = 20e-9      # oscillation amplitude [m] (20 nm — moderate)


def run_simulation(params):
    """
    SiN cantilever with double-sided fluoropolymer coating and small array.

    params keys:
      L_um      : beam length [um]
      w_um      : beam width [um]
      t_um      : beam thickness [um]
      h_coat_nm : coating thickness [nm]
      N_array   : number of cantilevers in array
    """

    L       = params['L_um']      * 1e-6
    w       = params['w_um']      * 1e-6
    t       = params['t_um']      * 1e-6
    h_coat  = params['h_coat_nm'] * 1e-9
    N_array = max(1, int(round(params['N_array'])))

    if L <= 0 or w <= 0 or t <= 0 or h_coat <= 0:
        return None
    if t > L:
        return None
    if L / t > 500 or L / t < 20:
        return None
    if h_coat > t * 0.10:
        return None

    m_beam = RHO_BEAM * w * t * L
    k      = E_BEAM * w * t**3 / (4 * L**3)

    A_coat = 2 * w * L  # double-sided
    m_coat = RHO_COAT * A_coat * h_coat
    m_total = m_beam + m_coat
    m_eff = 0.2357 * m_total

    if m_eff <= 0:
        return None

    f0 = (1 / (2 * np.pi)) * np.sqrt(k / m_eff)
    if f0 <= 0:
        return None

    S_Hz_kg = f0 / (2 * m_eff)
    sensitivity_hz_pg = S_Hz_kg * 1e-12

    omega0  = 2 * np.pi * f0
    tau_TED = RHO_BEAM * CP_BEAM * t**2 / (np.pi**2 * KAP_BEAM)
    xi      = omega0 * tau_TED

    Delta_E   = E_BEAM * ALPHA_BEAM**2 * T0 / (RHO_BEAM * CP_BEAM)
    Q_TED_inv = Delta_E * xi / (1 + xi**2)
    Q_TED     = 1.0 / Q_TED_inv if Q_TED_inv > 0 else 1e9

    denom_air = np.sqrt(RHO_AIR * ETA_AIR / (np.pi * f0))
    Q_air     = (RHO_BEAM * t) / (3.0 * denom_air) if denom_air > 0 else 1e9

    Q = 1.0 / (1.0 / Q_air + 1.0 / Q_TED)

    delta_f_min = (1.0 / A_OSC) * np.sqrt(KB * T0 * f0 * BW / (np.pi * k * Q))
    delta_m_min = 2 * m_eff * delta_f_min / f0
    delta_m_min = delta_m_min / np.sqrt(N_array)

    V_coat = A_coat * h_coat
    V_coat_liters = V_coat * 1e3
    lod_ng_per_L = delta_m_min / (V_coat_liters * K_PFAS * 1e-9)

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
        '_delta_m_min_fg':     delta_m_min * 1e15,
        '_m_coat_pg':          m_coat * 1e12,
    }
