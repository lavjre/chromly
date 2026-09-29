import pytest

from chromly.builds import args as bargs
from chromly.builds.v8 import recent_builds, run_build_cmd


def test_configs_load() -> None:
    for name in bargs.CONFIG_NAMES:
        cfg = bargs.load_config(name)
        assert cfg.target == "d8"
        assert cfg.gn_args["is_debug"] == "false"
        assert cfg.gn_args["use_lld"] == "true"
        # v8_monolithic yêu cầu external startup data tắt (BUILD.gn assert)
        assert cfg.gn_args["v8_use_external_startup_data"] == "false"


def test_asan_flags() -> None:
    cfg = bargs.load_config("asan")
    assert cfg.gn_args["is_asan"] == "true"
    assert cfg.gn_args["v8_enable_verify_heap"] == "true"
    assert cfg.gn_args["symbol_level"] == "2"


def test_dcheck_flag() -> None:
    assert bargs.load_config("dcheck").gn_args["dcheck_always_on"] == "true"
    assert "dcheck_always_on" not in bargs.load_config("release").gn_args


def test_args_gn_text_roundtrip() -> None:
    text = bargs.args_gn_text("release")
    assert "is_debug = false" in text
    assert text.endswith("\n")


def test_invalid_config() -> None:
    with pytest.raises(ValueError):
        bargs.load_config("nope")


def test_build_status_empty(capsys: pytest.CaptureFixture) -> None:
    import argparse

    rc = run_build_cmd(
        argparse.Namespace(status=True, config="release", rev=None, fetch_only=False)
    )
    assert rc == 0
    capsys.readouterr()


def test_recent_builds_list() -> None:
    assert isinstance(recent_builds(5), list)
