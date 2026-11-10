import numpy as np
import pytest

from sfit.tcad import DoubleExp, collected_charge, fit_double_exp, let_to_charge


def test_integral_equals_q():
    p = DoubleExp(q=10e-15, tau_r=2e-12, tau_f=30e-12)
    t = np.linspace(0, 1e-9, 20001)
    assert collected_charge(t, p.current(t)) == pytest.approx(10e-15, rel=1e-3)


@pytest.mark.parametrize("sign", [1, -1])
def test_fit_recovers_params_with_noise(sign):
    true = DoubleExp(q=sign * 15e-15, tau_r=4e-12, tau_f=60e-12, t0=10e-12)
    t = np.linspace(0, 500e-12, 1000)
    rng = np.random.default_rng(0)
    i = true.current(t)
    i = i + rng.normal(0, 0.01 * abs(i).max(), t.size)
    p = fit_double_exp(t, i)
    assert p.q == pytest.approx(true.q, rel=0.03)
    assert p.tau_r == pytest.approx(true.tau_r, rel=0.15)
    assert p.tau_f == pytest.approx(true.tau_f, rel=0.05)
    assert p.t0 == pytest.approx(true.t0, abs=1e-12)


def test_let_to_charge():
    assert let_to_charge(1.0, 1.0) == pytest.approx(10.36e-15)
