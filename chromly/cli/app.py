"""chromly CLI (§14.5 cli/).

M0-02: `check` thật; `doctor`/`build` chờ task tương ứng; còn lại stub theo milestone.
"""

from __future__ import annotations

import argparse
import sys

from chromly import __version__

STUBS: dict[str, str] = {
    "up": "M1",
    "intel": "M2",
    "status": "M3",
    "cases": "M4",
    "bench": "M4",
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
    p_build.add_argument("--config", choices=["release", "dcheck", "asan"], default="release")
    p_build.add_argument("--rev", default=None, help="V8 revision (hash); mặc định rev hiện tại")
    p_build.add_argument("--fetch-only", action="store_true", help="chỉ gclient sync, không build")
    p_build.add_argument("--status", action="store_true", help="liệt kê build gần đây")

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
    if args.cmd in STUBS:
        print(f"`chromly {args.cmd}` scheduled {STUBS[args.cmd]} — chưa có", file=sys.stderr)
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
