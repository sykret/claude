import json

import pytest

from sfit import __version__
from sfit.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_fit_then_gen(tmp_path, capsys):
    import numpy as np
    from sfit.tcad import DoubleExp

    p = DoubleExp(q=20e-15, tau_r=3e-12, tau_f=40e-12, t0=5e-12)
    t = np.linspace(0, 300e-12, 600)
    csv = tmp_path / "tr.csv"
    csv.write_text("time,current\n" + "\n".join(f"{a},{b}" for a, b in zip(t, p.current(t))))
    params = tmp_path / "p.json"
    assert main(["fit", str(csv), "-o", str(params)]) == 0
    fitted = json.loads(params.read_text())
    assert fitted["q"] == pytest.approx(20e-15, rel=1e-3)

    net = tmp_path / "c.sp"
    net.write_text("* inv\nR1 out 0 1k\nC1 out 0 1f\n.end\n")
    out = tmp_path / "o.sp"
    assert main(["gen", str(net), "--node", "out", "--params", str(params), "-o", str(out)]) == 0
    deck = out.read_text()
    assert "Istriker out 0 EXP(" in deck and deck.rstrip().endswith(".end")

    capsys.readouterr()
    assert main(["diff", str(out), str(out)]) == 0


def test_charge(capsys):
    assert main(["charge", "--let", "10", "--depth", "1"]) == 0
    assert "103.6 fC" in capsys.readouterr().out
