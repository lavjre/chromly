"""Source-review lane — đọc source snapshot tìm bug cũ còn sống.

Khác audit (chạy test từ commit fix) và review (đọc diff): lane này đọc **source hiện tại**
của vùng nóng — file bị nhiều fix commit chạm nhất (bug magnet, từ archaeology) — và để agent
tự tìm bug còn sống + viết test chứng minh, rồi chạy trên asan/release/calib/tot.

- hotspots: xếp hạng từ store/recon/archaeology-v8.json (records: commit fix + paths).
- review: agent `intel` đọc file (absolute path, read-only) → review.md + variants.json
  (schema như commit review) → chạy tests → crash store (source='srcreview').
- scan: top hotspot chưa review → chạy lần lượt (aux loop `srcrev`).
- index: store/intel/srcreview-index.json — path → {slug, ts, generated, crashes}.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from chromly import paths
from chromly.intel import variants as V
from chromly.intel.watcher import intel_dir
from chromly.store import db

MODEL = "opencode-go/deepseek-v4.1-flash"
SCRATCH_ROOT = Path("/tmp/opencode/chromly-srcreview")

CODE_SUFFIXES = (".cc", ".h", ".tq", ".py")
# d8 = test shell (không reachable từ Chrome), flags = parsing của embedder
EXCLUDE_PREFIXES = ("src/d8/", "src/flags/")
# Arch-specific: builds của ta là x64 — bug arch khác không repro được (và tốn budget)
_ARCH_RE = re.compile(r"(^|/)(arm64|riscv|s390|ppc|loong64|mips|ia32)(/|[-_.])")

SRC_PROMPT = """\
Bạn là source-review lane của chromly — săn bug V8 còn sống trong source hiện tại.
WORKDIR TUYỆT ĐỐI: {workdir} — chỉ đọc/ghi trong workdir bằng đường dẫn tuyệt đối.
Đây là source-review, KHÔNG có diff: bỏ qua skill patch-diff-review.

1. Đọc `{workdir}/meta.json` (file + lý do chọn). File cần review (read-only, snapshot hiện tại):
   `{v8root}/{path}` — đọc bằng grep + read theo vùng (file có thể lớn, đừng đọc 1 lượt).
2. Săn **bug cũ còn sống** trong file này — ưu tiên theo thứ tự:
   a. Memory safety: OOB read/write, use-after-free, type confusion, integer overflow/underflow
      trong size/offset arithmetic, thiếu bounds check, cast ép kiểu không kiểm tra.
   b. Logic: giả định sai về state, version gate thiếu, error path không cleanup.
   c. CHECK/DCHECK: điều kiện debug-only mà release sẽ đi tiếp sai.
   Gợi ý: grep các pattern nghi vấn (`CHECK`, `DCHECK`, `static_cast`, `reinterpret_cast`,
   `->length()`, `+ 1`, `<<`, `size_t`, `ToObject`, `TrustedCast`) rồi đọc kỹ quanh đó;
   trace đường đi từ entry point reachable từ JS (parser/wasm/jit/builtins/runtime).
   File này là bug magnet (nhiều fix commit chạm) — bug sibling rất có thể còn sống.
3. Viết `{workdir}/review.md` (tiếng Việt) đúng 3 phần:
   **Nghi vấn** (mỗi nghi vấn: vị trí file:line, cơ chế, vì sao reachable) ·
   **Vì sao sống** (vì sao chưa bị fix/bắt) ·
   **Test đề xuất** (map sang variants.json).
   Tối đa {limit} nghi vấn mạnh nhất — chất hơn lượng, KHÔNG bịa.
4. Ghi `{workdir}/variants.json` — mảng JSON, mỗi phần tử:
   {{"title": "...", "confidence": "high|med|low",
    "test_idea": "mô tả ngắn", "test_js": "<JS chạy standalone trên d8>"}}
   - `test_js`: code JS tối thiểu để kiểm chứng hypothesis, chạy được bằng
     `d8 --allow-natives-syntax file.js`. Nếu cần flags khác → dòng đầu của `test_js` ghi
     `// flags: --expose-gc ...` (để trống "" nếu chưa viết được).
   - Dùng intrinsic JIT (%OptimizeFunctionOnNextCall / %OptimizeMaglevOnNextCall /
     %OptimizeOsr): BẮT BUỘC có `%PrepareFunctionForOptimization(fn)` cho cùng hàm trước đó —
     thiếu là d8 abort CHECK giả (không phải bug V8) và đốt một case pipeline.
   - Không có nghi vấn đủ cơ sở thì ghi [].
5. Xong thì DỪNG. Không sửa file khác, không cài gì.
"""


def archaeology_path() -> Path:
    return paths.STORE_DIR / "recon" / "archaeology-v8.json"


def hotspots(top: int = 15) -> list[dict]:
    """Xếp hạng file src/ theo số fix commit chạm (archaeology) — bug magnet."""
    p = archaeology_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return []
    counts: dict[str, int] = {}
    surfaces: dict[str, set[str]] = {}
    for rec in data.get("records", []):
        for path in rec.get("paths", []):
            if not isinstance(path, str) or not path.startswith("src/"):
                continue
            if path.startswith(EXCLUDE_PREFIXES):
                continue
            if _ARCH_RE.search(path):
                continue
            if not path.endswith(CODE_SUFFIXES):
                continue
            counts[path] = counts.get(path, 0) + 1
            surfaces.setdefault(path, set()).add(str(rec.get("surface", "other")))
    rows = []
    for path, n in counts.items():
        f = paths.V8_ROOT / path
        if not f.is_file():
            continue
        rows.append(
            {
                "path": path,
                "count": n,
                "surfaces": sorted(surfaces[path]),
                "size_kb": round(f.stat().st_size / 1024),
            }
        )
    rows.sort(key=lambda r: (-r["count"], r["path"]))
    return rows[:top]


def slug_for(path: str) -> str:
    return "src-" + hashlib.sha1(path.encode()).hexdigest()[:12]


def index_path() -> Path:
    return intel_dir() / "srcreview-index.json"


def load_index() -> dict:
    p = index_path()
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_index(idx: dict) -> None:
    p = index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(idx, ensure_ascii=False, indent=2))


def run_src_tests(slug: str) -> dict:
    """Chạy variants của một source-review trên các build có sẵn; crash → store."""
    generated = V.generate_for(slug)
    builds = []
    for name in ("asan", "release", "calib", "tot"):
        d8 = paths.V8_ROOT / "out" / name / "d8"
        if d8.is_file():
            builds.append((name, d8))

    results = []
    for g in generated:
        test = V.tests_dir_for(slug) / g["file"]
        for build_name, d8 in builds:
            r = V.run_test(d8, test)
            results.append({"variant": g["file"], "title": g["title"], "build": build_name, **r})

    out_dir = intel_dir() / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "slug": slug,
        "generated": len(generated),
        "builds": [b[0] for b in builds],
        "ran": time.time(),
        "results": results,
    }
    (out_dir / "variant-results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    crashes = [r for r in results if r["outcome"] == "crash"]
    for r in crashes:
        V._file_variant_crash(slug, r, source="srcreview")
    return {"generated": len(generated), "crashes": len(crashes)}


def run_srcreview(path: str, limit: int = 3) -> dict:
    """Agent đọc file source → review.md + variants.json → chạy tests → crash store."""
    if not (paths.V8_ROOT / path).is_file():
        return {"path": path, "status": "no-source"}

    slug = slug_for(path)
    archive = intel_dir() / slug
    archive.mkdir(parents=True, exist_ok=True)
    meta = {"kind": "srcreview", "path": path, "created": time.time()}
    (archive / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    from chromly.orchestrator.agents import find_opencode

    opencode = find_opencode()
    if not opencode:
        return {"slug": slug, "path": path, "status": "no-opencode"}

    scratch = SCRATCH_ROOT / slug
    scratch.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive / "meta.json", scratch / "meta.json")
    prompt = SRC_PROMPT.format(workdir=scratch, path=path, v8root=paths.V8_ROOT, limit=limit)

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [
                opencode,
                "run",
                "--format",
                "json",
                "--auto",
                "--agent",
                "intel",
                "-m",
                MODEL,
                prompt,
            ],
            cwd=scratch,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        output = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired:
        output = "(timeout 3600s)"
    wall = round(time.monotonic() - t0, 1)
    (archive / "agent-output.log").write_text(output)

    for name in ("review.md", "variants.json"):
        src = scratch / name
        if src.is_file():
            shutil.copy2(src, archive / name)

    session = ""
    for line in output.splitlines():
        if "ses_" in line:
            idx = line.find("ses_")
            session = line[idx : idx + 40].split('"')[0].split("\\")[0].strip()
            break

    review = archive / "review.md"
    ok = review.is_file() and review.stat().st_size > 0
    status = "reviewed" if ok else "failed"

    con = db.ensure_db()
    try:
        with con:
            from chromly.orchestrator.agents import parse_session_usage

            usage = parse_session_usage(output)
            from chromly.telemetry import registry

            con.execute(
                "INSERT INTO runs (session_id, model, prompt_hash, cost_est, wall_s, outcome, "
                "tokens_in, tokens_out) VALUES (?,?,?,?,?,?,?,?)",
                (
                    session,
                    MODEL,
                    registry.persona_hash(),
                    usage["cost_est"],
                    wall,
                    f"srcreview:{status}",
                    usage["tokens_in"],
                    usage["tokens_out"],
                ),
            )
    finally:
        con.close()

    results = run_src_tests(slug)

    idx = load_index()
    prev = idx.get(path, {})
    idx[path] = {
        "slug": slug,
        "ts": time.time(),
        "status": status,
        "attempts": int(prev.get("attempts", 0)) + 1,
        "generated": results["generated"],
        "crashes": results["crashes"],
        "wall_s": wall,
    }
    save_index(idx)
    return {
        "slug": slug,
        "path": path,
        "status": status,
        "wall_s": wall,
        "session": session,
        **results,
    }


def _should_skip(idx: dict, path: str) -> bool:
    """Reviewed → skip; failed → retry tối đa 1 lần (bài học timeout 1800s 09/10)."""
    rec = idx.get(path)
    if rec is None:
        return False
    if rec.get("status") != "failed":
        return True
    return int(rec.get("attempts", 1)) >= 2


def run_scan(top: int = 2, limit: int = 3) -> list[dict]:
    """Chọn top hotspot chưa review (hoặc failed <2 lần) → chạy lần lượt (aux loop)."""
    idx = load_index()
    out = []
    for r in hotspots(top=100):
        if len(out) >= top:
            break
        if _should_skip(idx, r["path"]):
            continue
        out.append(run_srcreview(r["path"], limit=limit))
    return out


def run_srcreview_cmd(args) -> int:
    if getattr(args, "hotspots", False):
        rows = hotspots(top=getattr(args, "top", None) or 15)
        idx = load_index()
        for r in rows:
            done = "reviewed" if r["path"] in idx else "-"
            print(
                f"{r['count']:>3}  {done:<8} {r['size_kb']:>5}KB  {r['path']}"
                f"  ({', '.join(r['surfaces'])})"
            )
        return 0

    file = getattr(args, "file", None)
    if file:
        res = run_srcreview(file, limit=getattr(args, "limit", 3))
        print(
            f"srcreview {file}: status={res.get('status')} generated={res.get('generated')} "
            f"crashes={res.get('crashes')} wall={res.get('wall_s')}s"
        )
        return 0

    loop = getattr(args, "loop", False)
    interval = getattr(args, "interval", 14400.0)
    while True:
        res = run_scan(top=getattr(args, "top", None) or 2, limit=getattr(args, "limit", 3))
        for r in res:
            print(
                f"[srcreview] {r.get('path')}: status={r.get('status')} "
                f"generated={r.get('generated')} crashes={r.get('crashes')}",
                flush=True,
            )
        if not loop:
            return 0
        time.sleep(interval)
