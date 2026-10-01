import pytest

from chromly.mcp import tools


def test_repro_run_invalid_build() -> None:
    with pytest.raises(ValueError):
        tools.repro_run({"crash_id": "abc", "build": "bogus"})


def test_build_request_invalid_config() -> None:
    with pytest.raises(ValueError):
        tools.build_request({"config": "bogus"})
