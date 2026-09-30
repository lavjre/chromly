"""Recon & Surface strategy — khúc 1 pipeline (§2, §1.3).

- SURFACES: bản đồ attack surface — paths → surface → bug class kỳ vọng → harness có sẵn.
- archaeology(mirror, days): harvest fix "security mùi" từ git history (grep-based) →
  phân loại surface + bug class → store/recon/archaeology-<mirror>.json.
- surface_report(): join archaeology + intel DB (theo surface) + harness → report
  data-driven: hot / stale + đề xuất dồn nguồn lực (đúng §1.3 "tín hiệu → đường đi").

Nguồn bản đồ: PLAN §2 (V8) + Chromium surfaces (blink/mojo/sandbox/content).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from chromly import paths
from chromly.store import db

# (name, path prefixes, bug class kỳ vọng, harness) — thứ tự = ưu tiên classify
SURFACES: dict[str, list[tuple[str, tuple[str, ...], tuple[str, ...], str]]] = {
    "v8": [
        (
            "jit",
            ("src/compiler/", "src/maglev/", "src/turboshaft/", "src/jit/", "src/codegen/"),
            ("type confusion", "OOB", "miscompilation"),
            "fuzzilli",
        ),
        (
            "wasm",
            ("src/wasm/", "src/compiler/wasm"),
            ("OOB offset", "type confusion", "trap bypass"),
            "libfuzzer-wasm (replay)",
        ),
        ("regexp", ("src/regexp/",), ("OOB", "UAF", "wrong capture"), "fuzzilli"),
        (
            "parser",
            ("src/parsing/", "src/ast/"),
            ("OOB", "stack overflow", "state desync"),
            "libfuzzer-parser (replay)",
        ),
        (
            "gc-heap",
            ("src/heap/", "src/handles/", "include/cppgc/"),
            ("UAF", "race", "OOB"),
            "fuzzilli",
        ),
        (
            "objects-runtime",
            (
                "src/objects/",
                "src/runtime/",
                "src/execution/",
                "src/numbers/",
                "src/strings/",
                "src/json/",
                "src/bigint/",
                "src/date/",
                "src/math/",
            ),
            ("UAF", "bad cast", "check"),
            "fuzzilli",
        ),
        (
            "builtins-torque",
            ("src/builtins/", "src/torque/"),
            ("type confusion", "OOB", "check"),
            "fuzzilli",
        ),
        ("interpreter", ("src/interpreter/",), ("OOB", "check"), "libfuzzer-parser (replay)"),
        ("sandbox", ("src/sandbox/",), ("bypass", "layout", "cushion"), "—"),
        (
            "api-embed",
            ("src/api/", "src/d8/", "src/inspector/", "src/inspector/"),
            ("UAF", "bad cast"),
            "—",
        ),
    ],
    "chromium": [
        (
            "blink",
            ("third_party/blink/",),
            ("UAF", "type confusion", "OOB"),
            "chrome lab (M5+)",
        ),
        (
            "mojo-ipc",
            ("mojo/", "ipc/", "components/mojo/"),
            ("validation gap", "UAF", "confusion"),
            "chrome lab (M5+)",
        ),
        (
            "sandbox-browser",
            ("sandbox/", "content/browser/"),
            ("policy bypass", "handle leak", "confusion"),
            "—",
        ),
        ("gpu", ("gpu/", "components/viz/"), ("OOB", "UAF"), "—"),
        ("content-renderer", ("content/renderer/",), ("UAF", "type confusion"), "chrome lab (M5+)"),
        ("network", ("net/", "services/network/"), ("parser OOB", "smuggling"), "—"),
        ("other", (), (), "—"),
    ],
}

STRONG_KW = (
    "use-after-free",
    "use after free",
    " uaf",
    "out of bounds",
    "out-of-bounds",
    " oob",
    "type confusion",
    "sandbox escape",
    "cve-",
    "integer overflow",
    "buffer overflow",
    "memory corruption",
    "uninitialized",
    "uninit",
)
MEDIUM_KW = ("fix crash", "harden", "bounds check", "check failed", " oob")
CHROMIUM_TARGET = (
    "third_party/blink/",
    "mojo/",
    "ipc/",
    "sandbox/",
    "content/",
    "gpu/",
    "services/network",
    "net/",
)
CHROMIUM_EXCLUDE = (
    "ios/",
    "android_webview/",
    "components/",
    "build/",
    "docs/",
    "tools/",
    "infra/",
    "ash/",
    "ui/",
    "chrome/",
    "chromeos/",
)


def interesting_commit(mirror: str, subject: str, changed_paths: list[str]) -> bool:
    """Lọc 2 tầng: loại noise (rolls/docs/ios...), giữ commit 'security mùi' đúng surface."""
    s = subject.lower()
    if mirror == "v8":
        if s.startswith(("roll ", "update docs", "[version-auto-update]")):
            return False
        return any(p.startswith(("src/", "include/cppgc/")) for p in changed_paths)
    # chromium
    if s.startswith("roll ") or "roll v8 from" in s or "roll devtools" in s or "roll webrtc" in s:
        return False
    strong = any(k in s for k in STRONG_KW)
    medium = any(k in s for k in MEDIUM_KW)
    targeted = any(any(p.startswith(t) or t in p for t in CHROMIUM_TARGET) for p in changed_paths)
    excluded = (
        all(any(p.startswith(e) for e in CHROMIUM_EXCLUDE) for p in changed_paths)
        if changed_paths
        else True
    )
    if strong and not excluded:
        return True
    return bool(medium and targeted)


GREP_PATTERNS = [
    "security",
    "cve-",
    "out of bounds",
    "out-of-bounds",
    " oob",
    "overflow",
    "underflow",
    "use-after-free",
    "use after free",
    " uaf",
    "type confusion",
    "bounds check",
    "fix crash",
    "check failed",
    "sandbox escape",
    "harden",
]

BUG_CLASS_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("use-after-free", ("use-after-free", "use after free", " uaf", "lifetime")),
    ("type-confusion", ("type confusion", "type-confusion", "bad cast")),
    ("oob", ("out of bounds", "out-of-bounds", " oob", "bounds")),
    ("overflow", ("overflow", "underflow")),
    ("check-fail", ("check failed", "dcheck", "check failure", "assert")),
    ("sandbox", ("sandbox",)),
    ("uninit", ("uninitialized", "uninit")),
    ("crash-other", ("crash", "segv")),
]


def recon_dir() -> Path:
    return paths.STORE_DIR / "recon"


def classify_surface(mirror: str, changed_paths: list[str]) -> str:
    """Phân loại commit vào surface theo paths (first-match theo thứ tự SURFACES)."""
    for name, prefixes, _classes, _harness in SURFACES[mirror]:
        if not prefixes:
            continue
        for p in changed_paths:
            if any(p.startswith(pfx) for pfx in prefixes):
                return name
    if mirror == "chromium":
        v8_paths = [p[3:] for p in changed_paths if p.startswith("v8/")]
        if v8_paths:
            return "v8:" + classify_surface("v8", v8_paths)
    return "other"


def guess_bug_class(subject: str) -> str:
    s = subject.lower()
    for cls, patterns in BUG_CLASS_PATTERNS:
        if any(pat in s for pat in patterns):
            return cls
    return "other"


def archaeology(mirror: str = "v8", days: int = 90, max_commits: int = 600) -> dict:
    """Harvest fix 'security mùi' trong `days` ngày → phân loại surface/bug class."""
    from chromly.intel.watcher import _git, mirror_dir_for

    m = mirror_dir_for(mirror)
    if not (m / ".git").is_dir():
        raise FileNotFoundError(f"mirror chưa có: {m}")
    fmt = "--format=%H\x1f%cI\x1f%s"
    grep_args = [f"--grep={p}" for p in GREP_PATTERNS]
    rc, out = _git(
        [
            "log",
            fmt,
            f"--since={days} days ago",
            f"--max-count={max_commits}",
            "-i",
            *grep_args,
            "origin/main",
        ],
        m,
        timeout=600,
    )
    if rc != 0:
        raise RuntimeError(f"git log lỗi {mirror}: {out[-300:]}")

    commits = []
    for line in out.splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) != 3:
            continue
        subject = parts[2]
        # --grep quét cả body → roll log chứa keyword (oob/overflow) lọt vào; lọc như watcher
        if subject.lower().startswith("roll "):
            continue
        commits.append({"sha": parts[0], "date": parts[1], "subject": subject})

    records = []
    for c in commits:
        rc, pout = _git(["show", "--name-only", "--format=", c["sha"]], m, timeout=60)
        changed = [p for p in pout.splitlines() if p.strip()]
        surface = classify_surface(mirror, changed)
        records.append(
            {
                "sha": c["sha"],
                "date": c["date"][:10],
                "subject": c["subject"],
                "surface": surface,
                "bug_class": guess_bug_class(c["subject"]),
                "paths": changed[:20],
            }
        )

    counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    for r in records:
        counts[r["surface"]] = counts.get(r["surface"], 0) + 1
        class_counts[r["bug_class"]] = class_counts.get(r["bug_class"], 0) + 1

    result = {
        "mirror": mirror,
        "days": days,
        "generated": time.time(),
        "scanned": len(commits),
        "records": records,
        "counts": counts,
        "bug_class_counts": class_counts,
    }
    d = recon_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"archaeology-{mirror}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _load_archaeology(mirror: str) -> dict | None:
    p = recon_dir() / f"archaeology-{mirror}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def _intel_by_surface(mirror: str) -> dict[str, dict]:
    """Đếm intel DB theo surface (dùng cột source = mirror)."""
    con = db.ensure_db()
    try:
        rows = con.execute(
            "SELECT paths, review_status, variant_flag FROM intel WHERE source = ?", (mirror,)
        ).fetchall()
    finally:
        con.close()
    out: dict[str, dict] = {}
    for r in rows:
        try:
            chpaths = json.loads(r["paths"] or "[]")
        except json.JSONDecodeError:
            chpaths = []
        surface = classify_surface(mirror, chpaths)
        e = out.setdefault(surface, {"pending": 0, "reviewed": 0, "variants": 0})
        if r["review_status"] == "pending":
            e["pending"] += 1
        elif r["review_status"] == "reviewed":
            e["reviewed"] += 1
        if r["variant_flag"]:
            e["variants"] += 1
    return out


def surface_report() -> Path:
    """Report surface: archaeology (fix/hot) + intel (đã review) + harness → markdown."""
    reports = paths.STORE_DIR / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    day = datetime.now(UTC).astimezone().strftime("%Y-%m-%d")
    path = reports / f"surface-{day}.md"

    lines = [f"# Surface report — {day}", ""]
    for mirror in ("v8", "chromium"):
        arch = _load_archaeology(mirror)
        intel = _intel_by_surface(mirror)
        harness_by_surface = {s[0]: s[3] for s in SURFACES[mirror]}
        lines.append(
            f"## {mirror.upper()}" + (f" — {arch['days']} ngày" if arch else " (chưa archaeology)")
        )
        if arch:
            lines.append("")
            lines.append(
                "| surface | fixes | bug class mix | intel pending/reviewed | variants | harness |"
            )
            lines.append("|---|---|---|---|---|---|")
            order = [s[0] for s in SURFACES[mirror]]
            order += [x for x in sorted(set(arch["counts"]) | set(intel)) if x not in order]
            seen: set[str] = set()
            for sname in order:
                if sname in seen:
                    continue
                seen.add(sname)
                n = arch["counts"].get(sname, 0)
                if sname == "other" and n == 0 and sname not in intel:
                    continue
                classes = [r["bug_class"] for r in arch["records"] if r["surface"] == sname]
                mix = ", ".join(sorted(set(classes))) or "—"
                i = intel.get(sname, {})
                harness = harness_by_surface.get(sname, "—")
                if sname.startswith("v8:"):
                    harness = "fuzzilli/libfuzzer (xuyên mirror)"
                lines.append(
                    f"| {sname} | {n} | {mix} | {i.get('pending', 0)}/{i.get('reviewed', 0)} "
                    f"| {i.get('variants', 0)} | {harness} |"
                )
        lines.append("")

    lines.append("## Đề xuất (data-driven §1.3)")
    for mirror in ("v8", "chromium"):
        arch = _load_archaeology(mirror)
        if not arch:
            continue
        hot = sorted(arch["counts"].items(), key=lambda kv: -kv[1])[:3]
        hot_s = ", ".join(f"{k} ({v})" for k, v in hot if k != "other")
        lines.append(f"- **{mirror} hot**: {hot_s or '—'} → dồn review/variant + corpus")
    lines.append("- surface 'other' nhiều → xem lại path map (bổ sung prefix)")
    lines.append("")

    path.write_text("\n".join(lines) + "\n")
    return path


def run_recon_cmd(args) -> int:
    sub = getattr(args, "recon_cmd", None)
    if sub == "archaeology":
        res = archaeology(
            mirror=getattr(args, "mirror", "v8"),
            days=getattr(args, "days", 90),
            max_commits=getattr(args, "max", 600),
        )
        print(
            f"archaeology {res['mirror']}: scanned={res['scanned']} "
            f"classified={len(res['records'])}"
        )
        for k, v in sorted(res["counts"].items(), key=lambda kv: -kv[1]):
            print(f"  {k}: {v}")
        return 0
    if sub in (None, "report"):
        p = surface_report()
        print(p)
        return 0
    print("usage: chromly recon {archaeology|report}")
    return 2
