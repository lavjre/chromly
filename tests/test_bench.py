from chromly.bench import suite


def test_t3_accuracy() -> None:
    res = suite.t3()
    assert res["n"] == 20
    assert res["accuracy"] == 1.0
    assert res["fp_accuracy"] == 1.0
    assert res["score_order_ok"] is True
