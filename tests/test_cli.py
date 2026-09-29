import pytest

from chromly.cli.app import main


def test_version(capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "chromly" in capsys.readouterr().out


def test_no_args_prints_help(capsys: pytest.CaptureFixture) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "check" in out
    assert "doctor" in out


def test_stub_exit_code(capsys: pytest.CaptureFixture) -> None:
    for cmd, ms in (("override", "M4"),):
        assert main([cmd]) == 3
        err = capsys.readouterr().err
        assert f"scheduled {ms}" in err
