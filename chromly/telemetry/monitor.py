"""Monitor — M8-01: `chromly info` (snapshot) + `chromly trace` (feed sự kiện sống).

Nguồn event (thuần đọc, zero-dep):
- store/fuzz/events.jsonl          (watchdog/farm)            ts giây
- store/logs/plugin-events.jsonl   (shell/deny/plugin)        ts mili-giây
- cases/CASE-*/log.jsonl           (case state)               ts giây
- store/kg_log.jsonl · mcp-log.jsonl                          ts giây
- store/fuzz/logs/aux-*.log        (loop logs)                [HH:MM:SS] hoặc dòng cuối/mtime
- DB: crashes · runs · scheduler_decisions · alerts           created/ts
"""

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from chromly import paths
from chromly.store import db

SOURCE_COLORS = {
    "watchdog": "\x1b[31m",
    "farm": "\x1b[31m",
    "crash": "\x1b[33m",
    "case": "\x1b[35m",
    "run": "\x1b[35m",
    "intel": "\x1b[34m",
    "review": "\x1b[34m",
    "audit": "\x1b[36m",
    "diffopt": "\x1b[36m",
    "variant": "\x1b[36m",
    "build": "\x1b[32m",
    "shell": "\x1b[90m",
    "deny": "\x1b[31m",
    "kg": "\x1b[90m",
    "mcp": "\x1b[90m",
    "sched": "\x1b[32m",
    "alert": "\x1b[31m",
}
_RESET = "\x1b[0m"

_CORPUS_CACHE: dict = {}  # {key: FUZZ_DIR, ts, data} — cache 60s cho _corpus_counts

Event = dict  # {"ts": float, "source": str, "text": str}


def _color_enabled() -> bool:
    return os.environ.get("NO_COLOR") is None and os.isatty(1)


def _fmt_ts(ts: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts))


def _read_jsonl(path: Path) -> list[dict]:
    out: list[dict] = []
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return out


def _norm_ts(ts: float) -> float:
    """plugin-events dùng Date.now() (ms) — chuẩn hoá về giây."""
    return ts / 1000.0 if ts > 2e10 else float(ts)


def parse_fuzz_events(since: float) -> list[Event]:
    out = []
    for rec in _read_jsonl(paths.STORE_DIR / "fuzz" / "events.jsonl"):
        ts = rec.get("ts", 0)
        if ts < since:
            continue
        kind = rec.get("event", "?")
        unit = rec.get("unit", "?")
        extra = " ".join(f"{k}={v}" for k, v in rec.items() if k not in ("ts", "event", "unit"))
        out.append({"ts": ts, "source": "watchdog", "text": f"{kind} {unit} {extra}".strip()})
    return out


def parse_plugin_events(since: float) -> list[Event]:
    out = []
    for rec in _read_jsonl(paths.STORE_DIR / "logs" / "plugin-events.jsonl"):
        ts = _norm_ts(rec.get("ts", 0))
        if ts < since:
            continue
        kind = rec.get("event", "?")
        if kind == "plugin-loaded":
            continue  # bootstrap noise — không lên feed
        cmd = str(rec.get("cmd", "")).replace("\n", " ")
        if kind == "shell":
            text = f"{kind} ({rec.get('cwd', '?')}) {cmd[:90]}"
        elif kind == "deny":
            text = f"DENY {rec.get('scope', '?')} — {cmd[:90]}"
        else:
            text = f"{kind} {rec.get('directory', '')}"
        out.append({"ts": ts, "source": kind if kind != "deny" else "deny", "text": text})
    return out


def parse_case_logs(since: float) -> list[Event]:
    out = []
    cases = paths.CASES_DIR
    if not cases.is_dir():
        return out
    for d in sorted(cases.glob("CASE-*")):
        for rec in _read_jsonl(d / "log.jsonl"):
            ts = rec.get("ts", 0)
            if ts < since:
                continue
            kind = rec.get("event", "?")
            detail = rec.get("state") or rec.get("verdict") or rec.get("crash", "") or ""
            out.append({"ts": ts, "source": "case", "text": f"{d.name} {kind} {detail}".strip()})
    return out


def parse_simple_jsonl(path: Path, source: str, since: float, fmt) -> list[Event]:
    out = []
    for rec in _read_jsonl(path):
        ts = rec.get("ts", 0)
        if ts < since:
            continue
        out.append({"ts": ts, "source": source, "text": fmt(rec)})
    return out


def db_events(since: float) -> list[Event]:
    out: list[Event] = []
    con = db.ensure_db()
    try:

        def _parse_utc(s: str | None) -> float:
            if not s:
                return 0.0
            try:
                return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
            except ValueError:
                return 0.0

        for r in con.execute(
            "SELECT hash, fault_type, severity, source, state, created FROM crashes "
            "ORDER BY id DESC LIMIT 200"
        ):
            ts = _parse_utc(r["created"])
            if ts < since:
                continue
            out.append(
                {
                    "ts": ts,
                    "source": "crash",
                    "text": f"{r['hash'][:12]} {r['fault_type']} score={r['severity']} "
                    f"({r['source']}/{r['state']})",
                }
            )
        for r in con.execute(
            "SELECT case_id, model, wall_s, cost_est, outcome, created FROM runs "
            "ORDER BY id DESC LIMIT 100"
        ):
            ts = _parse_utc(r["created"])
            if ts < since:
                continue
            out.append(
                {
                    "ts": ts,
                    "source": "run",
                    "text": f"{r['case_id']} {r['outcome']} wall={r['wall_s']}s "
                    f"${(r['cost_est'] or 0):.3f}",
                }
            )
        for r in con.execute(
            "SELECT ts, from_mode, to_mode, reason FROM scheduler_decisions "
            "ORDER BY rowid DESC LIMIT 50"
        ):
            raw = r["ts"]
            try:
                ts = float(raw)
            except (TypeError, ValueError):
                ts = _parse_utc(raw)
            if ts < since:
                continue
            out.append(
                {
                    "ts": ts,
                    "source": "sched",
                    "text": f"{r['from_mode']} → {r['to_mode']} ({r['reason']})",
                }
            )
        for r in con.execute("SELECT rule, severity, ts FROM alerts ORDER BY id DESC LIMIT 50"):
            raw = r["ts"]
            try:
                ts = float(raw)
            except (TypeError, ValueError):
                ts = _parse_utc(raw)
            if ts < since:
                continue
            out.append({"ts": ts, "source": "alert", "text": f"{r['severity']} {r['rule']}"})
    finally:
        con.close()
    return out


_TS_RE = None


def parse_aux_logs(since: float) -> list[Event]:
    """aux-*.log: '[HH:MM:SS]' → parse giờ hôm nay; JSON line → gọn; dòng cuối theo mtime."""
    out: list[Event] = []
    logs = paths.STORE_DIR / "fuzz" / "logs"
    if not logs.is_dir():
        return out
    today = time.strftime("%Y-%m-%d")
    for f in sorted(logs.glob("aux-*.log")):
        name = f.stem.replace("aux-", "")
        try:
            lines = f.read_text(errors="replace").splitlines()
            mtime = f.stat().st_mtime
        except OSError:
            continue
        for i, line in enumerate(lines[-200:]):
            line = line.strip()
            if not line:
                continue
            ts = None
            text = line
            if line.startswith("["):
                close = line.find("]")
                hhmmss = line[1:close]
                try:
                    dt = datetime.strptime(f"{today} {hhmmss}", "%Y-%m-%d %H:%M:%S")
                    ts = dt.timestamp()
                    if ts > time.time() + 60:
                        ts = None  # log nhiều ngày: giờ này thuộc ngày trước → bỏ khi backfill
                    text = line[close + 1 :].strip()
                except ValueError:
                    ts = None
            elif line.startswith("{"):
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "sha" in rec:
                    text = (
                        f"{rec['sha'][:12]} {rec.get('status')} wall={rec.get('wall_s')}s "
                        f"variants={rec.get('variants')}"
                    )
                elif "variants_run" in rec:
                    text = (
                        f"variants_run {rec['variants_run'][:12]} generated={rec['generated']} "
                        f"crashes={rec['crashes']}"
                    )
                else:
                    continue
                ts = None
            if ts is None:
                if i < len(lines[-200:]) - 1:
                    continue  # dòng cũ không có mốc thời gian → bỏ khi backfill
                ts = mtime  # dòng cuối: dùng mtime xấp xỉ
            if ts < since:
                continue
            out.append({"ts": ts, "source": name, "text": text})
    return out


def collect(since: float, include_aux: bool = True, sources: set[str] | None = None) -> list[Event]:
    events: list[Event] = []
    events += parse_fuzz_events(since)
    events += parse_plugin_events(since)
    events += parse_case_logs(since)
    events += db_events(since)
    events += parse_simple_jsonl(
        paths.STORE_DIR / "kg_log.jsonl", "kg", since, lambda r: f"{r.get('kind')} {r.get('type')}"
    )
    events += parse_simple_jsonl(
        paths.STORE_DIR / "mcp-log.jsonl",
        "mcp",
        since,
        lambda r: f"{r.get('tool')} ok={r.get('ok')} {r.get('ms')}ms",
    )
    if include_aux:
        events += parse_aux_logs(since)
    if sources:
        events = [e for e in events if e["source"] in sources]
    events.sort(key=lambda e: e["ts"])
    return events


def render_event(e: Event, color: bool | None = None) -> str:
    color = _color_enabled() if color is None else color
    tag = f"{e['source']:<9}"
    text = str(e["text"]).replace("\n", " ")  # feed 1 dòng/event, không vỡ layout
    if color:
        c = SOURCE_COLORS.get(e["source"], "")
        return f"{_fmt_ts(e['ts'])} {c}[{tag}]{_RESET} {text}"
    return f"{_fmt_ts(e['ts'])} [{tag}] {text}"


def run_trace(
    follow: bool = False,
    limit: int = 40,
    since_min: float = 60.0,
    sources: set[str] | None = None,
) -> int:
    since = time.time() - since_min * 60
    events = collect(since, sources=sources)
    for e in events[-limit:]:
        print(render_event(e), flush=True)

    if not follow:
        return 0

    print(f"── theo dõi trực tiếp (Ctrl-C để thoát) ── {time.strftime('%H:%M:%S')}", flush=True)
    seen = {(e["ts"], e["source"], e["text"]) for e in events[-200:]}
    try:
        while True:
            time.sleep(1.0)
            for e in collect(since, sources=sources):
                key = (e["ts"], e["source"], e["text"])
                if key in seen:
                    continue
                seen.add(key)
                print(render_event(e), flush=True)
            if len(seen) > 5000:
                seen = {
                    (e["ts"], e["source"], e["text"])
                    for e in collect(since, sources=sources)[-500:]
                }
    except KeyboardInterrupt:
        print("── dừng theo dõi ──")
    return 0


# ── info ──────────────────────────────────────────────────────────────────────


def _last_aux_lines() -> list[tuple[str, str, float]]:
    out = []
    logs = paths.STORE_DIR / "fuzz" / "logs"
    for f in sorted(logs.glob("aux-*.log")):
        name = f.stem.replace("aux-", "")
        try:
            line = f.read_text(errors="replace").strip().splitlines()[-1]
            out.append((name, line[:80], f.stat().st_mtime))
        except (OSError, IndexError):
            out.append((name, "(trống)", 0.0))
    return out


def _intel_summary() -> dict:
    con = db.ensure_db()
    try:
        row = con.execute(
            "SELECT "
            "SUM(review_status='pending') AS pending, "
            "SUM(review_status='reviewed') AS reviewed, "
            "SUM(variant_flag=1) AS variants FROM intel"
        ).fetchone()
        kg_n = con.execute("SELECT COUNT(*) AS n FROM kg_nodes").fetchone()["n"]
        kg_e = con.execute("SELECT COUNT(*) AS n FROM kg_edges").fetchone()["n"]
    except Exception:  # noqa: BLE001 — bảng có thể chưa tồn tại ở môi trường lạ
        return {"pending": 0, "reviewed": 0, "variants": 0, "kg_n": 0, "kg_e": 0}
    finally:
        con.close()
    lag = None
    try:
        st = json.loads((paths.STORE_DIR / "intel" / "state.json").read_text())
        lags = [v.get("last_lag_hours") for v in st.values() if isinstance(v, dict)]
        lags = [x for x in lags if x is not None]
        lag = max(lags) if lags else None
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return {
        "pending": row["pending"] or 0,
        "reviewed": row["reviewed"] or 0,
        "variants": row["variants"] or 0,
        "kg_n": kg_n,
        "kg_e": kg_e,
        "lag": lag,
    }


def _corpus_counts() -> list[tuple[str, int]]:
    """Số file corpus mỗi lane (cache 60s theo FUZZ_DIR — tránh quét 40k+ file mỗi 5s)."""
    from chromly.fuzz import farm

    now = time.time()
    key = str(farm.FUZZ_DIR)
    if _CORPUS_CACHE.get("key") == key and now - _CORPUS_CACHE.get("ts", 0) < 60:
        return _CORPUS_CACHE["data"]
    rows: list[tuple[str, int]] = []
    for unit, sub, suffix in (
        ("lfuzz-parser", "lfuzz-parser/corpus", None),
        ("lfuzz-wasm", "lfuzz-wasm/corpus", None),
        ("fuzzilli", "fuzzilli/corpus", ".js"),  # đếm program (.fzil kèm theo không tính)
    ):
        n = 0
        try:
            with os.scandir(farm.FUZZ_DIR / sub) as it:
                n = sum(
                    1 for e in it if e.is_file() and (suffix is None or e.name.endswith(suffix))
                )
        except OSError:
            pass
        rows.append((unit, n))
    _CORPUS_CACHE.update({"key": key, "ts": now, "data": rows})
    return rows


def _fmt_count(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def _bar(v: float, width: int = 10) -> str:
    """Thanh xác suất kiểu System-One: █ đầy / ░ trống."""
    try:
        x = max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return "░" * width
    n = round(x * width)
    return "█" * n + "░" * (width - n)


def _fmt_dur(sec: float | None) -> str:
    if not isinstance(sec, (int, float)) or sec < 0:
        return "—"
    t = int(sec)
    if t < 3600:
        return f"{t // 60}m"
    if t < 86400:
        return f"{t // 3600}h{(t % 3600) // 60:02d}"
    return f"{t // 86400}d"


def _s1_results(limit: int = 3) -> list[dict]:
    """Decision gần nhất từ store/s1/*.json (System One / JEV-style)."""
    d = paths.STORE_DIR / "s1"
    if not d.is_dir():
        return []
    files = sorted(d.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:limit]
    out: list[dict] = []
    for f in files:
        try:
            r = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(r, dict) and r.get("hash"):
            out.append(r)
    return out


def info_snapshot() -> dict:
    from chromly.fuzz import farm

    snap: dict = {"ts": time.time()}
    try:
        st = farm.status()
        snap["farm"] = {
            name: {
                "alive": info["alive"],
                "execs": info.get("execs_per_sec"),
                "uptime_s": info.get("uptime_s"),
                "rss_mb": info.get("rss_mb"),
                "type": info.get("type"),
            }
            for name, info in st.items()
        }
    except Exception:  # noqa: BLE001
        snap["farm"] = {}
    snap["corpus"] = _corpus_counts()
    snap["s1"] = _s1_results()
    state = farm._load_state()
    aux = state.get("aux", {})
    alive = sum(1 for rec in aux.values() if farm._alive(rec))
    snap["aux"] = {"alive": alive, "total": len(aux), "last": _last_aux_lines()}
    snap["intel"] = _intel_summary()

    running, last_done = [], None
    for d in sorted(paths.CASES_DIR.glob("CASE-*")) if paths.CASES_DIR.is_dir() else []:
        try:
            meta = json.loads((d / "meta.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get("state") == "RUNNING":
            running.append(d.name)
        elif meta.get("state") in ("VERDICT", "TIMEOUT", "HELP", "ERROR"):
            last_done = f"{d.name} {meta.get('verdict') or meta.get('state')}"
    snap["cases"] = {"running": running, "last": last_done}

    con = db.ensure_db()
    try:
        snap["crash_total"] = con.execute("SELECT COUNT(*) AS n FROM crashes").fetchone()["n"]
        snap["crash_last"] = [
            dict(r)
            for r in con.execute(
                "SELECT hash, fault_type, severity, source, state FROM crashes "
                "ORDER BY id DESC LIMIT 3"
            )
        ]
        snap["alerts"] = con.execute("SELECT COUNT(*) AS n FROM alerts WHERE ack = 0").fetchone()[
            "n"
        ]
    finally:
        con.close()

    builds = []
    bdir = paths.STORE_DIR / "builds"
    if bdir.is_dir():
        recs = sorted(bdir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
        for f in recs:
            try:
                b = json.loads(f.read_text())
                builds.append(f"{b.get('config')} {b.get('status')} {b.get('duration_s', 0):.0f}s")
            except (OSError, json.JSONDecodeError):
                continue
    snap["builds"] = builds

    # ToT verify (M5-04): trạng thái build upstream mới nhất
    try:
        from chromly.builds import tot as tot_mod

        st = tot_mod.load_state()
        if st:
            age_h = (time.time() - st.get("built_at", 0)) / 3600.0
            snap["tot"] = (
                f"{st.get('status')} {str(st.get('sha'))[:12]} age={age_h:.0f}h"
                f"{'' if tot_mod.d8_ready() else ' (d8 missing)'}"
            )
    except Exception:  # noqa: BLE001
        pass

    try:
        from chromly.orchestrator import budget

        u = budget.usage()
        snap["budget"] = {
            "day": u.get("day", 0),
            "tier": budget.tier(),
            "cpc": budget.cost_per_case(),
        }
    except Exception:  # noqa: BLE001
        snap["budget"] = {"day": 0, "tier": "?", "cpc": None}
    try:
        snap["disk_free_gb"] = shutil.disk_usage(str(paths.REPO_ROOT)).free // (1 << 30)
    except OSError:
        snap["disk_free_gb"] = None
    snap["events"] = collect(time.time() - 2 * 3600)[-10:]
    return snap


def render_info(color: bool | None = None) -> str:
    color = _color_enabled() if color is None else color
    s = info_snapshot()
    lines = [f"══ chromly info — {time.strftime('%Y-%m-%d %H:%M:%S')} ══"]

    farm = s.get("farm") or {}
    total = sum(x["execs"] for x in farm.values() if isinstance(x.get("execs"), float))
    lines.append(f"FARM    {len(farm)} unit · ~{total:.0f} exec/s tổng")
    for name, info in farm.items():
        mark = "●" if info["alive"] else "✗"
        execs = f"{info['execs']:.0f}/s" if isinstance(info.get("execs"), float) else "—"
        up = _fmt_dur(info.get("uptime_s"))
        rss = f"{info['rss_mb']}MB" if info.get("rss_mb") else "—"
        extra = (
            "  ⟨rotate⟩"
            if name.startswith("lfuzz-") and name not in ("lfuzz-parser", "lfuzz-wasm")
            else ""
        )
        lines.append(f"  {name:<18} {mark} {execs:>8}  ↑{up:<5} {rss:>6}{extra}")

    corp = s.get("corpus") or []
    corp_bits = " · ".join(f"{name} {_fmt_count(n)}" for name, n in corp)
    lines.append("CORPUS  " + (corp_bits + " file" if corp_bits else "—"))

    aux = s["aux"]
    lines.append(f"AUX     {aux['alive']}/{aux['total']} loop sống")
    for name, last, mtime in aux["last"]:
        age = int(time.time() - mtime) if mtime else -1
        lines.append(f"  {name:<8} {last}  ({age}s trước)" if age >= 0 else f"  {name:<8} {last}")

    i = s["intel"]
    lag = f"{i['lag']:.1f}h" if i.get("lag") is not None else "?"
    lines.append(
        f"INTEL   pending={i['pending']} reviewed={i['reviewed']} variants={i['variants']} "
        f"lag={lag} · KG {i['kg_n']}n/{i['kg_e']}e"
    )

    c = s["cases"]
    run = ", ".join(c["running"]) if c["running"] else "(không)"
    lines.append(f"CASES   running={run} · cuối: {c['last'] or '—'}")

    crash_bits = ", ".join(
        f"{r['hash'][:8]} {r['fault_type']} s{r['severity']} ({r['source']})"
        for r in s["crash_last"]
    )
    lines.append(f"CRASH   tổng={s['crash_total']} · mới: {crash_bits or '—'}")

    s1 = s.get("s1") or []
    if s1:
        lines.append("S1      System One (laya) — chấm crash gần nhất")
        for r in s1:
            h = str(r.get("hash", "?"))[:12]
            expl = r.get("exploitable")
            lad = r.get("ladder")
            e = f"{_bar(expl)} {expl:.2f}" if isinstance(expl, (int, float)) else "—"
            lad_s = f"{_bar(lad)} {lad:.2f}" if isinstance(lad, (int, float)) else "—"
            lines.append(f"  {h}  exploitable {e}   ladder {lad_s}")
            lines.append(
                f"                impact={r.get('impact') or '—'}"
                f" · reachable={r.get('reachable') or '—'}"
                f" · next={r.get('next') or '—'} · {r.get('elapsed_ms') or '?'}ms"
            )

    lines.append("BUILD   " + " · ".join(s["builds"] or ["—"]))
    if s.get("tot"):
        lines.append("TOT     " + s["tot"])
    cpc = (s.get("budget") or {}).get("cpc")
    cpc_txt = ""
    if cpc and cpc.get("cases"):
        cpc_txt = f" · 7d ${cpc['cost']:.2f}/{cpc['cases']} case = ${cpc['per_case']:.2f}/case"
    lines.append(f"BUDGET  day ${s['budget']['day']:.2f} · tier={s['budget']['tier']}{cpc_txt}")
    lines.append(f"DISK    {s['disk_free_gb']}G free · alerts(unacked)={s['alerts']}")
    lines.append("── event gần nhất ──")
    for e in s["events"]:
        lines.append("  " + render_event(e, color=color))
    return "\n".join(lines)


def run_info(watch: bool = False, interval: float = 5.0, as_json: bool = False) -> int:
    if as_json:
        print(json.dumps(info_snapshot(), ensure_ascii=False, indent=2, default=str))
        return 0
    if not watch:
        print(render_info())
        return 0
    try:
        while True:
            out = render_info()
            if os.isatty(1):
                print("\x1b[2J\x1b[H" + out, flush=True)
            else:
                print(out + "\n", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0
