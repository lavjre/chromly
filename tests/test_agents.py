from chromly.orchestrator.agents import parse_session_usage


def test_parse_session_usage() -> None:
    out = "\n".join(
        [
            '{"type":"step_finish","part":{"cost":0.01,"tokens":{"input":10,"output":20,"cache":{"read":100}}}}',
            "noise",
            '{"type":"text","part":{"text":"hi"}}',
            '{"type":"step_finish","part":{"cost":0.02,"tokens":{"input":5,"output":7,"cache":{"read":50}}}}',
        ]
    )
    usage = parse_session_usage(out)
    assert usage["cost_est"] == 0.03
    assert usage["tokens_in"] == 165
    assert usage["tokens_out"] == 27


def test_parse_session_usage_empty() -> None:
    assert parse_session_usage("")["cost_est"] == 0.0
