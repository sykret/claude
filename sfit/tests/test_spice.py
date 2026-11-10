import numpy as np
import pytest

from sfit.spice import inject, parse, pulse_source
from sfit.tcad import DoubleExp

P = DoubleExp(q=10e-15, tau_r=2e-12, tau_f=30e-12, t0=1e-12)


def _exp_src(t, i1, i2, td1, tau1, td2, tau2):
    """Reference SPICE EXP source waveform."""
    v = np.full_like(t, i1)
    m = t >= td1
    v[m] += (i2 - i1) * (1 - np.exp(-(t[m] - td1) / tau1))
    m = t >= td2
    v[m] += (i1 - i2) * (1 - np.exp(-(t[m] - td2) / tau2))
    return v


def test_exp_style_matches_double_exp():
    lines = pulse_source("s", "n", "0", P, style="exp")
    t = np.linspace(0, 300e-12, 3000)
    total = np.zeros_like(t)
    for ln in lines:
        args = [float(x) for x in ln.split("EXP(")[1].rstrip(")").split()]
        total += _exp_src(t, *args)
    assert np.allclose(total, P.current(t), atol=1e-6 * P.i_peak)


def test_pwl_style_matches_double_exp():
    (ln,) = pulse_source("s", "n", "0", P, style="pwl")
    vals = [float(x) for x in ln.split("PWL(")[1].rstrip(")").split()]
    t, i = np.array(vals[0::2]), np.array(vals[1::2])
    assert np.all(np.diff(t) > 0)
    assert np.allclose(i, P.current(t), atol=1e-4 * P.i_peak)


def test_parse_existing_rc_deck():
    deck = parse("* title\nr_1_2 n8 n1 1.0e+03\nc_1_0 n8 0 5e-13\n"
                 "M1 d g s b nch W=1u L=0.1u\n+ m=2\n.model nch nmos level=54\n.end\n")
    s = deck.summary()
    assert s["element_counts"] == {"R": 2 - 1, "C": 1, "M": 1}
    assert s["models"] == {"nch": "nmos level=54"}
    m = deck.elements[2]
    assert m.nodes == ["d", "g", "s", "b"] and m.value == "nch"
    assert m.params == {"W": "1u", "L": "0.1u", "m": "2"}


def test_inject_adds_tran_once():
    out = inject("* t\nR1 a 0 1k\n.tran 1p 1n\n.end", "a", P)
    assert out.lower().count(".tran") == 1
    assert out.count(".end") == 1 and out.rstrip().endswith(".end")
