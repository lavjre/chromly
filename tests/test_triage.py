import os
from pathlib import Path

from chromly import paths
from chromly.store import db
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


def _fake_asan_d8(tmp_path: Path) -> Path:
    d8 = tmp_path / "v8" / "out" / "asan" / "d8"
    d8.parent.mkdir(parents=True)
    d8.write_text('#!/bin/bash\nif grep -q CRASH "$2"; then exit 134; fi\nexit 0\n')
    d8.chmod(0o755)
    return d8


def test_triage_once_marks_triaged(monkeypatch, tmp_path: Path) -> None:
    import hashlib

    from chromly.triage import cli as tcli

    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    _fake_asan_d8(tmp_path)
    src = "// CRASH\nprint(1);"
    h = hashlib.sha256(src.encode()).hexdigest()
    d = tmp_path / "store" / "crashes" / h
    d.mkdir(parents=True)
    (d / "program_x.js").write_text(src)
    con = db.ensure_db()
    with con:
        con.execute("INSERT INTO crashes (hash, source, state) VALUES (?, 'fuzzilli', 'raw')", (h,))
    con.close()

    assert tcli.triage_once() is True
    con = db.ensure_db()
    row = con.execute(
        "SELECT state, fault_type FROM crashes WHERE hash LIKE ?", (h[:12] + "%",)
    ).fetchone()
    con.close()
    assert row["state"] == "triaged"


def test_pick_candidate_backoff(monkeypatch, tmp_path: Path) -> None:
    import hashlib
    import time as _t

    from chromly.triage import cli as tcli

    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    h = hashlib.sha256(b"x").hexdigest()
    con = db.ensure_db()
    with con:
        con.execute("INSERT INTO crashes (hash, source, state) VALUES (?, 'fuzzilli', 'raw')", (h,))
    con.close()
    # chưa từng triage → nhặt
    assert tcli.pick_candidate() == (h[:12], 5)
    # vừa triage xong (asan.txt mới) → backoff, không nhặt
    td = tmp_path / "store" / "triage" / h
    td.mkdir(parents=True)
    (td / "asan.txt").write_text("x")
    assert tcli.pick_candidate() is None
    # cũ hơn 6h → nhặt lại
    old = _t.time() - tcli.RAW_RETRY_S - 60
    os.utime(td / "asan.txt", (old, old))
    assert tcli.pick_candidate() == (h[:12], 5)


def test_backoff_covers_failed_attempt(monkeypatch, tmp_path: Path) -> None:
    """Lỗi không-triagable (error.txt) cũng tính vào backoff — không quay mỗi tick."""
    import hashlib

    from chromly.triage import cli as tcli

    monkeypatch.setattr(paths, "V8_ROOT", tmp_path / "v8")
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    h = hashlib.sha256(b"bin").hexdigest()
    con = db.ensure_db()
    with con:
        con.execute("INSERT INTO crashes (hash, source, state) VALUES (?, 'fuzzilli', 'raw')", (h,))
    con.close()
    # không có script js/fzil → triage_one lỗi, ghi error.txt
    assert tcli.triage_once() is True
    td = tmp_path / "store" / "triage" / h
    assert (td / "error.txt").is_file()
    # lượt kế: bị backoff, không nhặt lại
    assert tcli.pick_candidate() is None


def test_triage_fuzzilli_fallback_build(monkeypatch, tmp_path: Path) -> None:
    """Crash source=fuzzilli, asan 0 repro → thử lại out/fuzzilli/d8 với --fuzzing."""
    from chromly import paths
    from chromly.triage import repro as R

    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    ad = tmp_path / "store" / "crashes" / ("a" * 64)
    ad.mkdir(parents=True)
    (ad / "program_x.js").write_text("print(1)\n")
    (ad / "meta.json").write_text('{"unit": "fuzzilli"}')
    d8a = tmp_path / "out" / "asan" / "d8"
    d8a.parent.mkdir(parents=True)
    d8a.write_bytes(b"")
    d8f = tmp_path / "out" / "fuzzilli" / "d8"
    d8f.parent.mkdir(parents=True)
    d8f.write_bytes(b"")
    monkeypatch.setattr(R, "d8_asan", lambda: d8a)
    monkeypatch.setattr(R, "d8_fuzzilli", lambda: d8f)
    monkeypatch.setattr(paths, "V8_ROOT", tmp_path)

    calls: list[tuple] = []

    def fake_run(d8, script, runs=5, timeout=60, extra_flags=None):
        calls.append((str(d8), tuple(extra_flags or [])))
        if str(d8) == str(d8f):
            return {
                "crashed": 5,
                "of": 5,
                "stable": True,
                "last_rc": 133,
                "output": "Check failed: x",
            }
        return {"crashed": 0, "of": 5, "stable": False, "last_rc": 0, "output": "ok"}

    monkeypatch.setattr(R, "repro_run", fake_run)
    res = R.run_triage("a" * 12, runs=5)
    assert res["engine"] == "fuzzilli"
    assert res["crashed"] == "5/5"
    assert any("fuzzilli" in c[0] and "--fuzzing" in c[1] for c in calls)


def test_score_fuzzilli_output_khong_bi_tinh_harness() -> None:
    """Output của fuzzilli d8 ('Fuzzer output channel...') không phải harness-frame → không −3."""
    from chromly.triage import score

    s = score.score(
        {"class": "type-confusion-dcheck", "access": None},
        "abort: CSA_DCHECK failed: ... accessor-assembler.cc\nFuzzer output channel not available",
    )
    assert s["score"] == 3, s
    assert "harness-related −3" not in s["reasons"]

    s2 = score.score({"class": "other", "access": None}, "... test/fuzzer/fuzzer.cc ...")
    assert "harness-related −3" in s2["reasons"]


def test_repro_run_output_prefers_crash(monkeypatch) -> None:
    """Flaky: output trả về phải là lượt crash, không phải lượt sạch đầu tiên."""
    import types

    from chromly.triage import repro as R

    seq = [
        ("clean run\n", 0),
        ("# Fatal error in ../../src/x.cc, line 1\nCheck failed: x\n", 133),
        ("clean again\n", 0),
    ]
    calls = {"i": 0}

    def fake_run(cmd, capture_output=True, text=True, timeout=60, env=None):
        out, rc = seq[calls["i"]]
        calls["i"] += 1

        class P:
            stdout = out
            stderr = ""
            returncode = rc

        return P()

    monkeypatch.setattr(R, "subprocess", types.SimpleNamespace(run=fake_run))
    res = R.repro_run(Path("/bin/true"), Path("x.js"), runs=3)
    assert res["crashed"] == 1
    assert "Check failed" in res["output"]
