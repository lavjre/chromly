from chromly.doctor import FAIL, INFO, OK, WARN, Check, exit_code


def _c(status: str) -> Check:
    return Check("x", status, "d")


def test_exit_code_semantics() -> None:
    assert exit_code([_c(OK), _c(WARN), _c(INFO)]) == 0
    assert exit_code([_c(OK), _c(FAIL)]) == 1
    assert exit_code([]) == 0


def test_check_defaults() -> None:
    c = Check("swap", OK, "16G")
    assert c.fix == ""
