from pathlib import Path

from chromly.triage import classify, dedup, repro, score


def test_classify_cases() -> None:
    oob = (
        "==12345==ERROR: AddressSanitizer: heap-buffer-overflow\n"
        "on address 0x61b000000000\n"
        "WRITE of size 8 at 0x61b0 thread T0\n"
    )
    assert classify.classify_text(oob)["class"] == "heap-buffer-overflow"
    assert classify.classify_text(oob)["access"] == {"kind": "write", "size": 8}
    uaf = "==1==ERROR: AddressSanitizer: heap-use-after-free on address 0x60\nREAD of size 4\n"
    assert classify.classify_text(uaf)["class"] == "use-after-free"
    assert classify.classify_text(uaf)["access"]["kind"] == "read"

    dcheck = (
        "Fatal error in ../../src/objects/map.cc, line 100\n"
        "Check failed: js_receiver.IsJSReceiver().\n"
    )
    assert classify.classify_text(dcheck)["class"] == "type-confusion-dcheck"

    assert classify.classify_text("(timeout)")["class"] == "timeout"
    assert classify.is_false_positive("timeout")
    assert classify.is_false_positive("oom")
    assert not classify.is_false_positive("heap-buffer-overflow")


def test_score_order() -> None:
    write = score.score({"class": "heap-buffer-overflow", "access": {"kind": "write"}}, "")
    read = score.score({"class": "heap-buffer-overflow", "access": {"kind": "read"}}, "")
    dcheck = score.score({"class": "dcheck-fail", "access": None}, "")
    assert write["score"] > read["score"] > 0
    assert dcheck["score"] <= 0

    jit = score.score(
        {"class": "heap-buffer-overflow", "access": {"kind": "write"}},
        "in Foo src/jit/x.cc:12",
    )
    assert jit["score"] == write["score"] + 2


def test_dedup_stable_across_addresses() -> None:
    a = "  #0 0x1234 in Foo src/x.cc:11\n  #1 0x99 in Bar src/y.cc:22"
    b = "  #0 0xabcd in Foo src/x.cc:99\n  #1 0x11 in Bar src/y.cc:44"
    assert dedup.stack_hash(a, "cls") == dedup.stack_hash(b, "cls")
    assert dedup.stack_hash(a, "cls") != dedup.stack_hash(a, "other")


def test_repro_run_fake_d8(tmp_path: Path) -> None:
    d8 = tmp_path / "d8"
    d8.write_text('#!/bin/bash\nif grep -q CRASH "$2"; then exit 134; fi\necho ok\nexit 0\n')
    d8.chmod(0o755)

    crash = tmp_path / "crash.js"
    crash.write_text("// CRASH\n")
    r = repro.repro_run(d8, crash, runs=5)
    assert r["crashed"] == 5
    assert r["stable"] is True

    ok = tmp_path / "ok.js"
    ok.write_text("print(1);\n")
    r2 = repro.repro_run(d8, ok, runs=5)
    assert r2["crashed"] == 0
    assert r2["stable"] is False


def test_triage_state_filter() -> None:
    from chromly.triage.cli import triage_state

    assert triage_state("0/5", False) == "raw"
    assert triage_state("1/5", False) == "flaky"
    assert triage_state("3/5", False) == "flaky"
    assert triage_state("5/5", True) == "triaged"
    assert triage_state("5/5", False) == "flaky"  # 5/5 nhưng không stable (timeout xen kẽ...)
