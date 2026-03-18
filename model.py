"""
model.py — MEMS Cantilever PFAS Sensor Model

Topology: Paddle (T-shape) silicon nitride cantilever with double-sided
          fluoropolymer coating and array averaging.
          Narrow stem for high f0, wide paddle for maximum coating area.

Physics:
  Euler-Bernoulli beam theory (stem determines f0 and k).
  Paddle mass at tip (lumped mass model).
  Thermomechanical (Brownian) noise floor.
  Sader/viscous + thermoelastic damping for Q in air.
  Double-sided coating on both stem and paddle.
"""

import numpy as np

KB = 1.381e-23

# Material: SiN (optimal)
E_BEAM     = 270e9
RHO_BEAM   = 3100.0
ALPHA_BEAM = 2.3e-6
KAP_BEAM   = 30.0
CP_BEAM    = 700.0
T0         = 300.0

# Air
ETA_AIR  = 1.81e-5
RHO_AIR  = 1.225

# Coating
RHO_COAT = 2100.0
K_PFAS   = 150.0      # standard fluoropolymer

# Measurement
BW       = 1.0        # 1 s integration (standard)
A_OSC    = 20e-9      # moderate (standard field operation)


def run_simulation(params):
    """
    Paddle (T-shape) SiN cantilever: narrow stem + wide paddle.

    params keys:
      Ls_um     : stem length [um]
      ws_um     : stem width [um]
      t_um      : thickness (uniform) [um]
      Lp_um     : paddle length [um]
      wp_um     : paddle width [um]
      h_coat_nm : coating thickness [nm]
      N_array   : number of cantilevers
    """

    Ls      = params['Ls_um']     * 1e-6
    ws      = params['ws_um']     * 1e-6
    t       = params['t_um']      * 1e-6
    Lp      = params['Lp_um']     * 1e-6
    wp      = params['wp_um']     * 1e-6
    h_coat  = params['h_coat_nm'] * 1e-9
    N_array = max(1, int(round(params['N_array'])))

    L_total = Ls + Lp

    if Ls <= 0 or ws <= 0 or t <= 0 or Lp <= 0 or wp <= 0 or h_coat <= 0:
        return None
    if t > Ls:
        return None
    if L_total / t > 500 or L_total / t < 20:
        return None
    if h_coat > t * 0.10:
        return None
    if wp < ws:  # paddle must be wider than stem
        return None

    # Stem mechanics (determines spring constant)
    k = E_BEAM * ws * t**3 / (4 * Ls**3)

    # Masses
    m_stem   = RHO_BEAM * ws * t * Ls
    m_paddle = RHO_BEAM * wp * t * Lp

    # Double-sided coating on both
    A_coat_stem   = 2 * ws * Ls   # double-sided coating
    A_coat_paddle = 2 * wp * Lp
    A_coat_total  = A_coat_stem + A_coat_paddle

    m_coat_stem   = RHO_COAT * A_coat_stem * h_coat
    m_coat_paddle = RHO_COAT * A_coat_paddle * h_coat

    # Effective mass: stem contributes 0.2357x, paddle at tip contributes fully
    m_eff = 0.2357 * (m_stem + m_coat_stem) + m_paddle + m_coat_paddle

    if m_eff <= 0:
        return None

    f0 = (1 / (2 * np.pi)) * np.sqrt(k / m_eff)
    if f0 <= 0:
        return None

    S_Hz_kg = f0 / (2 * m_eff)
    sensitivity_hz_pg = S_Hz_kg * 1e-12

    # Q-factor (use stem thickness for damping)
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

    V_coat = A_coat_total * h_coat
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
        '_m_coat_pg':          (m_coat_stem + m_coat_paddle) * 1e12,
    }
