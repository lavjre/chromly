"""chromly CLI (§14.5 cli/).

M0-02: `check` thật; `doctor`/`build` chờ task tương ứng; còn lại stub theo milestone.
"""

from __future__ import annotations

import argparse
import sys

from chromly import __version__

STUBS: dict[str, str] = {
    "doctor": "M0-03",
    "build": "M0-04",
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
    for name, ms in STUBS.items():
        sub.add_parser(name, help=f"scheduled {ms}")

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 0
    if args.cmd == "check":
        from chromly.check import run_check

        return run_check()
    if args.cmd in STUBS:
        print(f"`chromly {args.cmd}` scheduled {STUBS[args.cmd]} — chưa có", file=sys.stderr)
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
