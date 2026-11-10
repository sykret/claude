import pytest

from sfit import __version__
from sfit.cli import main


def test_main_runs(capsys):
    assert main([]) == 0
    assert "sfit" in capsys.readouterr().out


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
