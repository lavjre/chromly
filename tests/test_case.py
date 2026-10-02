import json
import os
from pathlib import Path

from chromly import paths
from chromly.case import pipeline, runner
from chromly.fuzz import farm
from chromly.orchestrator import budget
from chromly.store import db


def _setup(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(paths, "DB_PATH", tmp_path / "store" / "chromly.db")
    monkeypatch.setattr(paths, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(runner, "CASE_SCRATCH", tmp_path / "scratch")


def test_new_case_layout(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state) VALUES (?, ?, ?, 'triaged')",
            ("a" * 64, "heap-buffer-overflow", 5),
        )
    con.close()
    tri = paths.STORE_DIR / "triage" / ("a" * 64)
    tri.mkdir(parents=True)
    (tri / "repro.js").write_text("print(1)")
    (tri / "asan.txt").write_text("asan report")

    meta = pipeline.new_case("a" * 12)
    assert meta["id"] == "CASE-0001"
    assert meta["state"] == "BUNDLED"
    d = pipeline.case_dir("CASE-0001")
    for f in ("meta.json", "brief.md", "triage.md", "notes.md", "repro.js", "asan.txt"):
        assert (d / f).is_file(), f
    assert str(paths.V8_ROOT) in (d / "brief.md").read_text()


def test_parse_verdict() -> None:
    assert runner.parse_verdict("verdict: needs-human\nrest") == "needs-human"
    assert runner.parse_verdict("verdict: validated-crash") == "validated-crash"
    assert runner.parse_verdict("không có gì") is None


def test_run_case_budget_deny(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    monkeypatch.setattr(
        budget,
        "check_case",
        lambda est_cost=2.0, high_score=True: {"allow": False, "reason": "test"},
    )
    res = runner.run_case(meta["id"], max_wall=1)
    assert res["status"] == "budget-deny"


def test_set_state_and_list(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "RUNNING")
    got = pipeline.load_case(meta["id"])
    assert got["state"] == "RUNNING"
    assert [c["id"] for c in pipeline.list_cases()] == [meta["id"]]


def test_auto_case_tick(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state, source) "
            "VALUES (?, 'x', 5, 'triaged', 'fuzzilli')",
            ("b" * 64,),
        )
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state, source) "
            "VALUES (?, 'x', 9, 'triaged', 'fixture')",
            ("c" * 64,),
        )
    con.close()
    monkeypatch.setattr(
        runner, "run_case", lambda cid, **kw: {"status": "verdict", "verdict": "validated-crash"}
    )
    cid = runner.auto_case_tick()
    assert cid == "CASE-0001"
    # lần 2: đã có case (bỏ qua cả crash nguồn fixture) → None
    assert runner.auto_case_tick() is None


def test_next_id_max_plus_one_with_gap(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    (paths.CASES_DIR / "CASE-0001").mkdir(parents=True)
    (paths.CASES_DIR / "CASE-0003").mkdir()
    assert pipeline._next_id() == "CASE-0004"


def test_case_high_score_from_severity(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state) VALUES (?, ?, ?, 'triaged')",
            ("b" * 64, "x", 7),
        )
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state) VALUES (?, ?, ?, 'triaged')",
            ("c" * 64, "x", 2),
        )
    con.close()
    hi = pipeline.new_case("b" * 12)
    lo = pipeline.new_case("c" * 12)
    assert runner._case_high_score(hi["id"]) is True
    assert runner._case_high_score(lo["id"]) is False

    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state) VALUES (?, ?, ?, 'triaged')",
            ("d" * 64, "variant-crash", 5),
        )
    con.close()
    mid = pipeline.new_case("d" * 12)
    assert runner._case_high_score(mid["id"]) is True  # ngưỡng 5 = variant-crash thật


def test_run_case_no_opencode_not_stuck(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    from chromly.orchestrator import agents as agents_mod

    monkeypatch.setattr(agents_mod, "find_opencode", lambda: None)
    monkeypatch.setattr(
        budget, "check_case", lambda est_cost=2.0, high_score=True: {"allow": True, "model": "m"}
    )
    res = runner.run_case(meta["id"], max_wall=1)
    assert res["status"] == "no-opencode"
    assert pipeline.load_case(meta["id"])["state"] == "BUNDLED"


def test_run_case_exception_marks_error(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    from chromly.orchestrator import agents as agents_mod

    monkeypatch.setattr(agents_mod, "find_opencode", lambda: str(tmp_path / "khong-ton-tai"))
    monkeypatch.setattr(
        budget, "check_case", lambda est_cost=2.0, high_score=True: {"allow": True, "model": "m"}
    )
    res = runner.run_case(meta["id"], max_wall=1)
    assert res["status"] == "error"
    assert pipeline.load_case(meta["id"])["state"] == "ERROR"


def test_run_case_help_propagates(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    fake = tmp_path / "opencode"
    fake.write_text('#!/bin/bash\necho "can nguoi" > HELP.md\nexit 0\n')
    fake.chmod(0o755)
    from chromly.orchestrator import agents as agents_mod

    monkeypatch.setattr(agents_mod, "find_opencode", lambda: str(fake))
    monkeypatch.setattr(
        budget, "check_case", lambda est_cost=2.0, high_score=True: {"allow": True, "model": "m"}
    )
    res = runner.run_case(meta["id"], max_wall=10)
    assert res["status"] == "help"
    assert (pipeline.case_dir(meta["id"]) / "HELP.md").is_file()


def test_resume_cap_enforced(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    m = pipeline.load_case(meta["id"])
    m["resumes"] = runner.MAX_RESUME
    (pipeline.case_dir(meta["id"]) / "meta.json").write_text(json.dumps(m))
    res = runner.run_case(meta["id"], resume_session="ses_dummy", max_wall=1)
    assert res["status"] == "resume-cap"
    assert pipeline.load_case(meta["id"])["state"] != "RUNNING"


def test_prompt_hash_written_to_runs(monkeypatch, tmp_path: Path) -> None:
    import hashlib

    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path)
    (tmp_path / "runtime").mkdir()
    persona = tmp_path / "runtime" / "persona.txt"
    persona.write_bytes(b"persona-test")
    meta = pipeline.new_case(None)

    fake = tmp_path / "opencode"
    fake.write_text("#!/bin/bash\nexit 0\n")
    fake.chmod(0o755)
    from chromly.orchestrator import agents as agents_mod

    monkeypatch.setattr(agents_mod, "find_opencode", lambda: str(fake))
    monkeypatch.setattr(
        budget, "check_case", lambda est_cost=2.0, high_score=True: {"allow": True, "model": "m"}
    )
    runner.run_case(meta["id"], max_wall=10)
    con = db.ensure_db()
    row = con.execute(
        "SELECT prompt_hash FROM runs WHERE case_id = ? ORDER BY id DESC LIMIT 1", (meta["id"],)
    ).fetchone()
    con.close()
    assert row is not None
    assert row["prompt_hash"] == hashlib.sha256(b"persona-test").hexdigest()


def test_archive_case(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    d = pipeline.case_dir(meta["id"])
    (d / "poc").mkdir(exist_ok=True)
    (d / "poc" / "poc.js").write_text("x")
    (d / "agent-output.log").write_text("to" * 100)
    pipeline.set_state(meta["id"], "VERDICT", verdict="no-bug")
    res = pipeline.archive_case(meta["id"])
    assert res["status"] == "archived"
    assert Path(res["tarball"]).is_file()
    assert pipeline.load_case(meta["id"])["state"] == "ARCHIVED"
    assert not (d / "poc").exists()  # phần nặng đã nén
    assert (d / "meta.json").is_file()  # file nhẹ giữ lại
    assert pipeline.archive_case(meta["id"])["status"] == "already"


def test_archive_rejects_non_terminal(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    assert pipeline.archive_case(meta["id"])["status"] == "not-terminal"


def test_case_help_alert(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(farm, "FUZZ_DIR", tmp_path / "store" / "fuzz")
    monkeypatch.setattr(farm, "STATE_PATH", tmp_path / "store" / "fuzz" / "state.json")
    monkeypatch.setattr(farm, "LOGS_DIR", tmp_path / "store" / "fuzz" / "logs")
    from chromly.telemetry import alerts as alerts_mod

    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "HELP")
    new = alerts_mod.evaluate()
    assert any(a["rule"] == "case_help" for a in new)


def test_auto_candidate_stack_dedup(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, stack_norm, state) "
            "VALUES (?, 'oob', 5, 'STACK-1', 'triaged')",
            ("e" * 64,),
        )
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, stack_norm, state) "
            "VALUES (?, 'oob', 5, 'STACK-1', 'triaged')",
            ("f" * 64,),
        )
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, stack_norm, state) "
            "VALUES (?, 'oob', 4, 'STACK-2', 'triaged')",
            ("9" * 64,),
        )
    con.close()
    # cùng sev 5 → id DESC thắng ("f"); chưa case → là candidate
    first = runner._auto_candidate(threshold=4)
    assert first is not None and first["hash"].startswith("f" * 12)
    # gắn case cho nó → crash cùng stack ("e") phải bị loại, còn crash stack khác ("9")
    meta = pipeline.new_case(("f" * 64)[:12], source="auto")
    assert meta["id"]
    second = runner._auto_candidate(threshold=4)
    assert second is not None and second["hash"].startswith("9" * 12)


def test_pick_resume_case(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    cid = meta["id"]
    pipeline.set_state(cid, "TIMEOUT")
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO runs (case_id, session_id, model, outcome) "
            "VALUES (?, ?, 'm', 'case:TIMEOUT:none')",
            (cid, "ses_abc123"),
        )
    con.close()
    assert runner.pick_resume_case() == (cid, "ses_abc123")
    # hết lượt resume → không nhặt nữa
    m = pipeline.load_case(cid)
    m["resumes"] = runner.MAX_RESUME
    (pipeline.case_dir(cid) / "meta.json").write_text(json.dumps(m))
    assert runner.pick_resume_case() is None


# ── reclaim case kẹt RUNNING (runner chết giữa case — bài học CASE-0004) ──


def test_stale_running_case_dead_runner(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "RUNNING")
    (pipeline.case_dir(meta["id"]) / "runner.json").write_text(
        json.dumps({"pid": 999999999, "started": 0})
    )
    assert runner.stale_running_case() == meta["id"]


def test_stale_running_case_alive_runner_kept(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "RUNNING")
    (pipeline.case_dir(meta["id"]) / "runner.json").write_text(
        json.dumps({"pid": os.getpid(), "started": 0})
    )
    monkeypatch.setattr(runner, "_runner_alive", lambda pid: True)
    assert runner.stale_running_case() is None


def test_stale_running_case_legacy_old_meta(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "RUNNING")
    mp = pipeline.case_dir(meta["id"]) / "meta.json"
    old = 1_000_000.0
    os.utime(mp, (old, old))
    assert runner.stale_running_case(now=old + runner.RUNNER_STALE_S + 1) == meta["id"]


def test_stale_running_case_legacy_fresh_kept(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "RUNNING")
    # không runner.json nhưng meta mới (case vừa start) → chưa được đụng
    assert runner.stale_running_case() is None


def test_reclaim_stale_running_sets_timeout(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    from chromly.fuzz import watchdog

    monkeypatch.setattr(watchdog, "append_event", lambda *a, **k: None)
    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "RUNNING")
    (pipeline.case_dir(meta["id"]) / "runner.json").write_text(json.dumps({"pid": 999999999}))
    cid = runner.reclaim_stale_running()
    assert cid == meta["id"]
    assert pipeline.load_case(meta["id"])["state"] == "TIMEOUT"


def test_pick_resume_case_no_session(monkeypatch, tmp_path: Path) -> None:
    # runner chết trước khi có runs row → resume mới hoàn toàn (session None)
    _setup(monkeypatch, tmp_path)
    meta = pipeline.new_case(None)
    pipeline.set_state(meta["id"], "TIMEOUT")
    assert runner.pick_resume_case() == (meta["id"], None)


def test_acquire_auto_lock_exclusive(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    lock1 = runner._acquire_auto_lock()
    assert lock1 is not None
    # instance thứ 2 (process khác) không lấy được; trong cùng process flock theo open-file
    # description nên mở lại cũng fail
    lock2 = runner._acquire_auto_lock()
    assert lock2 is None
    lock1.close()


def test_mark_crash_fp(monkeypatch, tmp_path: Path) -> None:
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state) VALUES (?, 'x', 5, 'triaged')",
            ("b" * 64,),
        )
    con.close()
    meta = pipeline.new_case(("b" * 64)[:12], source="auto")
    runner._mark_crash_fp(meta["id"])
    con = db.ensure_db()
    st = con.execute("SELECT state FROM crashes WHERE hash = ?", ("b" * 64,)).fetchone()["state"]
    con.close()
    assert st == "fp"


def test_auto_case_budget_deny_archives(monkeypatch, tmp_path: Path) -> None:
    """budget-deny → DENIED (terminal) + vào _archive, không để husk BUNDLED."""
    _setup(monkeypatch, tmp_path)
    con = db.ensure_db()
    with con:
        con.execute(
            "INSERT INTO crashes (hash, fault_type, severity, state) VALUES (?, 'x', 5, 'triaged')",
            ("c" * 64,),
        )
    con.close()
    monkeypatch.setattr(runner, "run_case", lambda cid, **kw: {"status": "budget-deny"})
    cid = runner.auto_case_tick()
    assert cid
    assert pipeline.load_case(cid)["state"] == "ARCHIVED"
    assert (pipeline.cases_dir() / "_archive" / f"{cid}.tar.gz").is_file()
