"""chromly CLI (§14.5 cli/).

M0-02: `check` thật; `doctor`/`build` chờ task tương ứng; còn lại stub theo milestone.
"""

from __future__ import annotations

import argparse
import sys

from chromly import __version__
from chromly.builds.args import CONFIG_NAMES

STUBS: dict[str, str] = {
    "override": "M4",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chromly", description="chromly supervisor (PLAN.md)")
    parser.add_argument("--version", action="version", version=f"chromly {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("check", help="G0: import sanity + ruff + pytest")

    p_doc = sub.add_parser("doctor", help="kiểm tra môi trường VM (§13 M0)")
    p_doc.add_argument("--json", action="store_true", help="output cho máy đọc")

    p_build = sub.add_parser("build", help="V8 build rig (§5.1)")
    p_build.add_argument("--config", choices=list(CONFIG_NAMES), default="release")
    p_build.add_argument("--rev", default=None, help="V8 revision (hash); mặc định rev hiện tại")
    p_build.add_argument("--fetch-only", action="store_true", help="chỉ gclient sync, không build")
    p_build.add_argument("--status", action="store_true", help="liệt kê build gần đây")

    p_fuzz = sub.add_parser("fuzz", help="fuzz farm — worker up/down/status (§5.2)")
    fuzz_sub = p_fuzz.add_subparsers(dest="fuzz_cmd")
    fuzz_sub.add_parser("up", help="start workers")
    fuzz_sub.add_parser("down", help="stop workers")
    fuzz_sub.add_parser("status", help="trạng thái workers + execs/s")
    p_wd = fuzz_sub.add_parser("watchdog", help="loop giám sát hang/dead (M1-04)")
    p_wd.add_argument("--once", action="store_true", help="một tick rồi thoát")
    p_wd.add_argument("--interval", type=float, default=60.0, help="giây giữa các tick")
    p_ing = fuzz_sub.add_parser("ingest", help="crash store — quét incoming → DB (M1-05)")
    p_ing.add_argument("--once", action="store_true", help="một lượt quét rồi thoát")
    p_ing.add_argument("--interval", type=float, default=15.0, help="giây giữa các lượt")
    p_met = fuzz_sub.add_parser("metrics", help="sampler metrics 60s (M1-07)")
    p_met.add_argument("--once", action="store_true", help="một mẫu rồi thoát")
    p_met.add_argument("--interval", type=float, default=60.0, help="giây giữa các mẫu")
    p_cor = fuzz_sub.add_parser("corpus", help="corpus pipeline — sync/import/trim (M1-06)")
    cor_sub = p_cor.add_subparsers(dest="corpus_cmd")
    p_csync = cor_sub.add_parser("sync", help="mjsunit → .fzil seeds")
    p_csync.add_argument("--limit", type=int, default=120, help="số file mjsunit tối đa")
    cor_sub.add_parser("import", help="import seeds vào fuzzilli storage (one-shot)")
    p_ctrim = cor_sub.add_parser("trim", help="cull seed theo tuổi (dry-run mặc định)")
    p_ctrim.add_argument("--days", type=int, default=30)
    p_ctrim.add_argument("--apply", action="store_true", help="xoá thật")
    fuzz_sub.add_parser("seed", help="top-up corpus từ test delta (M2-08)")
    p_do = fuzz_sub.add_parser("diffopt", help="differential opt/no-opt (M2-10)")
    p_do.add_argument("--limit", type=int, default=100)
    p_do.add_argument("--build", default="release", choices=["release", "asan", "calib"])
    p_do.add_argument("--timeout", type=int, default=20)
    p_do.add_argument("--loop", action="store_true", help="chạy mãi (aux supervisor)")
    p_do.add_argument("--interval", type=float, default=86400.0, help="giây giữa các lượt")
    p_lf = fuzz_sub.add_parser("lfreplay", help="replay loop cho V8 simple-fuzzer (M1-03 v0)")
    p_lf.add_argument("--unit", required=True, choices=["libfuzzer-parser", "libfuzzer-wasm"])
    p_lf.add_argument("--interval", type=float, default=60.0)
    p_lf.add_argument("--once", action="store_true")

    p_intel = sub.add_parser("intel", help="intel track — watcher (§5.3, M2)")
    intel_sub = p_intel.add_subparsers(dest="intel_cmd")
    p_watch = intel_sub.add_parser("watch", help="poll mirror + filter commits")
    p_watch.add_argument("--once", action="store_true", help="một lượt rồi thoát")
    p_watch.add_argument("--since-days", type=int, default=7, help="lần đầu: nhìn lại N ngày")
    p_watch.add_argument("--max", type=int, default=200, help="số commit tối đa mỗi lượt")
    p_rev = intel_sub.add_parser("review", help="agent review commit pending (M2-02)")
    p_rev.add_argument("--limit", type=int, default=5, help="số commit tối đa")
    p_rev.add_argument("--sha", default=None, help="review đúng 1 commit")
    p_rev.add_argument("--loop", action="store_true", help="chạy mãi (aux supervisor)")
    p_rev.add_argument("--interval", type=float, default=7200.0, help="giây giữa các lượt (loop)")
    p_rev.add_argument("--dry-run", action="store_true", help="in thứ tự ưu tiên, không review")
    p_var = intel_sub.add_parser("variants", help="sinh + chạy variant test (M2-03)")
    p_var.add_argument("--sha", default=None, help="mặc định: commit reviewed mới nhất")
    p_aud = intel_sub.add_parser("audit", help="upstream-regress delta audit (M2-06)")
    p_aud.add_argument("--max", type=int, default=40, help="số test tối đa")
    p_aud.add_argument("--dry-run", action="store_true", help="chỉ liệt kê, không chạy")
    p_aud.add_argument("--loop", action="store_true", help="chạy mãi (aux supervisor)")
    p_aud.add_argument("--interval", type=float, default=86400.0, help="giây giữa các lượt")
    intel_sub.add_parser("status", help="trạng thái intel (M2-05)")

    p_recon = sub.add_parser("recon", help="recon & surface — archaeology/report (§2, M4-08)")
    recon_sub = p_recon.add_subparsers(dest="recon_cmd")
    p_arch = recon_sub.add_parser("archaeology", help="harvest fix security từ mirror")
    p_arch.add_argument("--mirror", default="v8", choices=["v8", "chromium"])
    p_arch.add_argument("--days", type=int, default=90)
    p_arch.add_argument("--max", type=int, default=600)
    recon_sub.add_parser("report", help="surface report data-driven")

    p_kg = sub.add_parser("kg", help="knowledge graph — ingest/query/neighbors (§7.3, M2)")
    kg_sub = p_kg.add_subparsers(dest="kg_cmd")
    p_kgi = kg_sub.add_parser("ingest", help="ingest intel review theo sha")
    p_kgi.add_argument("sha")
    p_kgq = kg_sub.add_parser("query", help="tìm nodes theo type/ref")
    p_kgq.add_argument("--type", default=None)
    p_kgq.add_argument("--ref", default=None, help="substring của ref")
    p_kgn = kg_sub.add_parser("neighbors", help="liệt kê edges từ node id")
    p_kgn.add_argument("id", type=int)

    p_tel = sub.add_parser("telemetry", help="telemetry — rollup/alerts/digest (§7.2, M3)")
    tel_sub = p_tel.add_subparsers(dest="tel_cmd")
    p_tr = tel_sub.add_parser("rollup", help="tổng hợp metrics → rollup")
    p_tr.add_argument("--days", type=int, default=7)
    p_ta = tel_sub.add_parser("alerts", help="liệt kê / ack alert")
    p_ta.add_argument("--ack", type=int, default=None, help="ack alert id")
    tel_sub.add_parser("digest", help="digest 7 ngày")

    p_pr = sub.add_parser("prompts", help="prompt registry — sync/list (§8, M3)")
    pr_sub = p_pr.add_subparsers(dest="prompts_cmd")
    pr_sub.add_parser("sync", help="hash persona/skills/agent config")
    pr_sub.add_parser("list", help="liệt kê hash đã đăng ký")

    sub.add_parser("status", help="dashboard v1 (§7.2)")

    p_tri = sub.add_parser("triage", help="triage crash — repro/classify/score (§5.4, M3)")
    p_tri.add_argument("--hash", default=None, help="hash crash (mặc định: raw mới nhất)")
    p_tri.add_argument("--runs", type=int, default=5, help="số lần repro")
    tri_sub = p_tri.add_subparsers(dest="triage_cmd")
    tri_sub.add_parser("list", help="liệt kê crashes + trạng thái")

    p_cal = sub.add_parser(
        "calibrate", help="calibration harness — revert-fix ground truth (§5.5, M3)"
    )
    p_cal.add_argument("--bug", default=None, help="bug id (mặc định: bug đầu tiên)")
    p_cal.add_argument("--list", action="store_true", help="liệt kê bộ bug")

    p_bud = sub.add_parser("budget", help="budget governor — caps/tier (§11, M4)")
    bud_sub = p_bud.add_subparsers(dest="budget_cmd")
    bud_sub.add_parser("status", help="usage + tier")
    p_bc = bud_sub.add_parser("check", help="quyết định cho case mới")
    p_bc.add_argument("--est-cost", type=float, default=2.0)

    p_sched = sub.add_parser("sched", help="dynamic scheduler — modes/override (§6.5, M4)")
    sched_sub = p_sched.add_subparsers(dest="sched_cmd")
    sched_sub.add_parser("status", help="mode hiện tại + snapshot")
    sched_sub.add_parser("eval", help="một lượt đánh giá (tick)")
    p_so = sched_sub.add_parser("override", help="override mode có thời hạn")
    p_so.add_argument("mode", help="NORMAL|FUZZ_LEAN|BUILD_WINDOW|CASE_PRIORITY|RED")
    p_so.add_argument("--minutes", type=float, default=30.0)
    p_so.add_argument("--reason", default=None)
    p_sl = sched_sub.add_parser("loop", help="tick loop cho supervisor")
    p_sl.add_argument("--interval", type=float, default=60.0)

    p_bench = sub.add_parser("bench", help="bench suite T1–T4 + Prompt CI gate (§8, M4)")
    p_bench.add_argument("--suite", default="ci", choices=["ci", "t1", "t2", "t3", "t4"])
    p_bench.add_argument("--run", action="store_true", help="chạy LLM run cho T1 (mặc định queue)")

    p_rep = sub.add_parser("report", help="report generator — weekly digest (§7.2, M8)")
    rep_sub = p_rep.add_subparsers(dest="report_cmd")
    rep_sub.add_parser("weekly", help="sinh store/reports/weekly-YYYY-WW.md")

    sub.add_parser("up", help="supervisor: farm + aux loops (M4-07)")
    sub.add_parser("down", help="dừng farm + aux")

    p_exp = sub.add_parser("exploit", help="exploit lab — verifier/lab (§5.9, M5)")
    exp_sub = p_exp.add_subparsers(dest="exploit_cmd")
    p_ev = exp_sub.add_parser("verify", help="chạy PoC ×N đo success rate")
    p_ev.add_argument("--poc", required=True, help="đường dẫn PoC js")
    p_ev.add_argument("--build", default="asan", choices=["asan", "calib", "release", "fuzzilli"])
    p_ev.add_argument("--runs", type=int, default=200)
    p_ev.add_argument("--marker", default=None, help="token bắt buộc trong output")
    p_er = exp_sub.add_parser("run", help="chạy PoC ×N (runner lặp nhanh M5-02)")
    p_er.add_argument("--poc", required=True, help="đường dẫn PoC js")
    p_er.add_argument("--build", default="calib", choices=["asan", "calib", "release", "fuzzilli"])
    p_er.add_argument("--flags", default=None, help="flags thêm cho d8 (một string)")
    p_er.add_argument("--runs", type=int, default=1)
    p_er.add_argument("--timeout", type=int, default=60)
    p_er.add_argument("--expect", default="any", choices=["any", "ok", "crash"])
    p_el = exp_sub.add_parser("lab", help="dựng out/calib theo bug (M5-02)")
    p_el.add_argument("--bug", default=None, help="calib id (vd calib-567177599)")
    p_el.add_argument("--no-build", action="store_true", help="chỉ ghi state")
    p_el.add_argument("--status", action="store_true", help="in state hiện tại")
    p_el.add_argument("--json", action="store_true", help="state dạng json")

    p_mcp = sub.add_parser("mcp", help="MCP bridge chromly-tools (§5.7, M4)")
    mcp_sub = p_mcp.add_subparsers(dest="mcp_cmd")
    mcp_sub.add_parser("serve", help="stdio JSON-RPC server")

    p_case = sub.add_parser("case", help="case pipeline — new/run/list/show (§5.6, M4)")
    case_sub = p_case.add_subparsers(dest="case_cmd")
    p_cn = case_sub.add_parser("new", help="tạo case từ crash")
    p_cn.add_argument("--crash", default=None, help="hash prefix của crash")
    p_cn.add_argument("--source", default="manual")
    p_cr = case_sub.add_parser("run", help="chạy agent cho case")
    p_cr.add_argument("case_id")
    p_cr.add_argument("--wall", type=float, default=480.0, help="wall tối đa (phút)")
    p_cr.add_argument("--resume", default=None, help="session id để resume")
    case_sub.add_parser("list", help="liệt kê cases")
    p_cs = case_sub.add_parser("show", help="chi tiết case")
    p_cs.add_argument("case_id")
    p_ca = case_sub.add_parser("auto", help="loop tự tạo + chạy case cho candidate (M4)")
    p_ca.add_argument("--interval", type=float, default=900.0)

    for name, ms in STUBS.items():
        sub.add_parser(name, help=f"scheduled {ms}")

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 0
    if args.cmd == "check":
        from chromly.check import run_check

        return run_check()
    if args.cmd == "doctor":
        from chromly.doctor import run_doctor

        return run_doctor(as_json=args.json)
    if args.cmd == "build":
        from chromly.builds.v8 import run_build_cmd

        return run_build_cmd(args)
    if args.cmd == "fuzz":
        from chromly.fuzz.farm import run_fuzz_cmd

        return run_fuzz_cmd(args)
    if args.cmd == "intel":
        if getattr(args, "intel_cmd", None) == "audit":
            from chromly.intel.regress_audit import run_audit_cmd

            return run_audit_cmd(args)
        from chromly.intel.watcher import run_intel_cmd

        return run_intel_cmd(args)
    if args.cmd == "recon":
        from chromly.intel.recon import run_recon_cmd

        return run_recon_cmd(args)
    if args.cmd == "kg":
        from chromly.knowledge.kg import run_kg_cmd

        return run_kg_cmd(args)
    if args.cmd == "status":
        from chromly.telemetry.dashboard import render_status

        print(render_status())
        return 0
    if args.cmd == "triage":
        from chromly.triage.cli import run_triage_cmd

        return run_triage_cmd(args)
    if args.cmd == "calibrate":
        from chromly.triage.calibration import run_calibrate_cmd

        return run_calibrate_cmd(args)
    if args.cmd == "budget":
        from chromly.orchestrator.budget import run_budget_cmd

        return run_budget_cmd(args)
    if args.cmd == "sched":
        from chromly.orchestrator.scheduler import run_sched_cmd

        return run_sched_cmd(args)
    if args.cmd == "bench":
        from chromly.bench.suite import run_bench_cmd

        return run_bench_cmd(args)
    if args.cmd == "report":
        from chromly.orchestrator.report import run_report_cmd

        return run_report_cmd(args)
    if args.cmd in ("up", "down"):
        from chromly.orchestrator.supervisor import run_supervisor_cmd

        return run_supervisor_cmd(args)
    if args.cmd == "exploit":
        from chromly.exploit.verifier import run_exploit_cmd

        return run_exploit_cmd(args)
    if args.cmd == "mcp":
        from chromly.mcp.server import run_mcp_cmd

        return run_mcp_cmd(args)
    if args.cmd == "case":
        from chromly.case.runner import run_case_cmd

        return run_case_cmd(args)
    if args.cmd == "telemetry":
        sub = getattr(args, "tel_cmd", None)
        if sub == "rollup":
            from chromly.telemetry.rollup import rollup

            print(rollup(days=getattr(args, "days", 7)))
            return 0
        if sub == "alerts":
            from chromly.telemetry import alerts as A

            if getattr(args, "ack", None) is not None:
                print("acked" if A.ack(args.ack) else f"không thấy alert {args.ack}")
                return 0
            for a in A.evaluate():
                print(f"new: [{a['severity']}] {a['rule']} {a['payload']}")
            for a in A.list_alerts():
                print(f"[{a['id']}] [{a['severity']}] {a['rule']} {a['payload']}")
            return 0
        if sub == "digest":
            from chromly.telemetry.alerts import digest

            print(digest())
            return 0
        print("usage: chromly telemetry {rollup|alerts|digest}")
        return 2
    if args.cmd == "prompts":
        sub = getattr(args, "prompts_cmd", None)
        if sub == "sync":
            from chromly.telemetry.registry import sync

            for e in sync():
                print(f"new: {e['hash']} {e['kind']} {e['version']}")
            return 0
        if sub == "list":
            from chromly.telemetry.registry import list_registry

            for e in list_registry():
                print(f"{e['hash'][:12]}  {e['kind']:<16} {e['version']:<14} {e['created']}")
            return 0
        print("usage: chromly prompts {sync|list}")
        return 2
    if args.cmd in STUBS:
        print(f"`chromly {args.cmd}` scheduled {STUBS[args.cmd]} — chưa có", file=sys.stderr)
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
