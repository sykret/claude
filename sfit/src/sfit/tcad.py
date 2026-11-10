"""TCAD transient-current handling: load, integrate, and fit to a compact model.

The compact model is the standard double-exponential current pulse used for
single-event / particle-strike injection in SPICE:

    I(t) = Q / (tau_f - tau_r) * (exp(-(t-t0)/tau_f) - exp(-(t-t0)/tau_r)),  t >= t0

Its integral over time is exactly Q (the collected charge).
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

# Charge deposited per unit length in silicon: 1 MeV*cm^2/mg -> 0.01036 pC/um
# (3.6 eV per e-h pair, density 2.33 g/cm^3).
PC_PER_UM_PER_LET = 0.01036


def let_to_charge(let_mev_cm2_mg: float, depth_um: float) -> float:
    """Deposited charge [C] for an ion of given LET crossing ``depth_um`` of silicon."""
    return let_mev_cm2_mg * depth_um * PC_PER_UM_PER_LET * 1e-12


@dataclass
class DoubleExp:
    q: float  # collected charge [C]
    tau_r: float  # rise time constant [s]
    tau_f: float  # fall time constant [s]
    t0: float = 0.0  # strike time [s]

    def current(self, t: np.ndarray) -> np.ndarray:
        return double_exp(np.asarray(t, dtype=float), self.q, self.tau_r, self.tau_f, self.t0)

    @property
    def t_peak(self) -> float:
        r, f = self.tau_r, self.tau_f
        return self.t0 + r * f / (f - r) * np.log(f / r)

    @property
    def i_peak(self) -> float:
        return float(self.current(np.array([self.t_peak]))[0])

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(t_peak=self.t_peak, i_peak=self.i_peak)
        return d


def double_exp(t, q, tau_r, tau_f, t0):
    dt = np.clip(t - t0, 0.0, None)
    i = q / (tau_f - tau_r) * (np.exp(-dt / tau_f) - np.exp(-dt / tau_r))
    return np.where(t >= t0, i, 0.0)


def load_transient(path: str | Path, time_col: int = 0, current_col: int = 1):
    """Load a time/current transient exported from TCAD (CSV or whitespace text).

    Non-numeric rows (headers, comments) are skipped. Units are assumed SI.
    """
    rows = []
    with open(path, newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        delim = "," if "," in sample else None
        reader = csv.reader(fh) if delim else (line.split() for line in fh)
        for row in reader:
            try:
                rows.append((float(row[time_col]), float(row[current_col])))
            except (ValueError, IndexError):
                continue
    if len(rows) < 4:
        raise ValueError(f"{path}: need at least 4 numeric rows, got {len(rows)}")
    data = np.array(sorted(rows))
    return data[:, 0], data[:, 1]


def collected_charge(t: np.ndarray, i: np.ndarray) -> float:
    return float(np.trapezoid(i, t))


def fit_double_exp(t: np.ndarray, i: np.ndarray) -> DoubleExp:
    """Fit a double-exponential pulse to a TCAD current transient.

    The sign of the pulse is preserved in ``q`` (negative for electron collection
    at an n+ drain if the TCAD convention reports it that way).
    """
    t = np.asarray(t, dtype=float)
    i = np.asarray(i, dtype=float)
    sign = 1.0 if abs(i.max()) >= abs(i.min()) else -1.0
    y = sign * i

    k = int(np.argmax(y))
    above = np.nonzero(y > 0.01 * y[k])[0]
    t0_guess = t[above[0]] if len(above) else t[0]
    q_guess = max(collected_charge(t, np.clip(y, 0, None)), 1e-30)
    rise = max(t[k] - t0_guess, (t[-1] - t[0]) * 1e-4)
    tail = y[k:]
    below = np.nonzero(tail < y[k] / np.e)[0]
    fall = (t[k + below[0]] - t[k]) if len(below) else (t[-1] - t[k])
    tau_r0 = rise / 3
    tau_f0 = max(fall, 2 * tau_r0)

    def model(tt, q, log_r, log_ratio, t0):
        tau_r = np.exp(log_r)
        return double_exp(tt, q, tau_r, tau_r * (1 + np.exp(log_ratio)), t0)

    p0 = [q_guess, np.log(tau_r0), np.log(tau_f0 / tau_r0 - 1 + 1e-9), t0_guess]
    scale = y[k] if y[k] != 0 else 1.0
    popt, _ = curve_fit(
        lambda tt, *p: model(tt, *p) / scale, t, y / scale, p0=p0, maxfev=20000
    )
    q, log_r, log_ratio, t0 = popt
    tau_r = float(np.exp(log_r))
    tau_f = float(tau_r * (1 + np.exp(log_ratio)))
    return DoubleExp(q=float(sign * q), tau_r=tau_r, tau_f=tau_f, t0=float(t0))
