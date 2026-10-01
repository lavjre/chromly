from chromly.intel.runner import priority_score


def test_security_beats_noise() -> None:
    sec = priority_score("Fix OOB read in WasmGC", ["src/wasm/x.cc"])
    noise = priority_score("Roll bazel to 123", ["infra/x.cfg"])
    assert sec >= 5
    assert noise < 0
    assert sec > noise


def test_test_only_penalty() -> None:
    assert priority_score("Add tests for X", ["test/mjsunit/x.js"]) < 0


def test_hot_path_bump() -> None:
    hot = priority_score("Tweak thing", ["src/compiler/a.cc"])
    cold = priority_score("Tweak thing", ["third_party/foo/a.cc"])
    assert hot > cold


def test_type_confusion_keyword() -> None:
    assert priority_score("Fix type confusion in X", ["src/objects/y.cc"]) >= 5
