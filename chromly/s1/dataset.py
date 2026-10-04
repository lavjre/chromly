"""Dataset cho S1 fine-tune — thu từ crash store + calibration, nhãn CÓ NGUỒN.

Nguyên tắc:
- State KHÔNG chứa nhãn (không fault_label của pipeline — heuristic chính là thứ S1 cần vượt qua).
- Mỗi item ghi `note` (nguồn nhãn: case verdict / M5-03 / bugs.json) để audit được.
- v1 train trên 2 câu hỏi có phân bố thật: `kind` (7 lớp) + `impact` (none/dos).
  `ladder`/`exploitable`/`next` hiện toàn 0/close trong data → KHÔNG train (đợi có positives).
- 2 mục calibration bị loại: calib-wasm-2338fbb0 (arch-locked, không trigger trên x64),
  calib-539984773 (revert drift, no-crash) — tránh dạy nhãn sai.

Nguồn nhãn: cases/CASE-*/VERDICT.md (fp/no-bug/validated) · build/tasks/M5-03-l1-primitive.md
(đánh giá ladder từng bug) · calibration/bugs.json (bug_class) · store/chromly.db (state).
"""

from __future__ import annotations

import json
from pathlib import Path

from chromly import paths
from chromly.s1 import decide

# ── registry — 14 item defensible (2026-10-04) ───────────────────────────────

CRASH_ITEMS: list[dict] = [
    {
        "prefix": "a0589f52",
        "kind": "test-api-misuse",
        "impact": "none",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "CASE-0005 no-bug: %Optimize* thiếu %PrepareFunctionForOptimization",
    },
    {
        "prefix": "4a47d80b84",
        "kind": "false-positive",
        "impact": "none",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "fp-flag-conflict (variant test, cờ xung đột build)",
    },
    {
        "prefix": "4a0da5f5",
        "kind": "test-api-misuse",
        "impact": "none",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "CASE-0010 no-bug: unsafe flag --wasm-max-initial-code-space-reservation",
    },
    {
        "prefix": "94a4430f",
        "kind": "check-abort",
        "impact": "dos",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": (
            "CASE-0004 validated: wasm %NeverOptimizeFunction CHECK — test-API-only, fixed upstream"
        ),
    },
    {
        "prefix": "3963f3ad",
        "kind": "check-abort",
        "impact": "dos",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "turbolev escape-analysis DCHECK (upstream-regress, n-day)",
    },
    {
        "prefix": "71956b45",
        "kind": "check-abort",
        "impact": "dos",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "n-day dcheck-fail (upstream-regress)",
    },
    {
        "prefix": "216c15a2",
        "kind": "check-abort",
        "impact": "dos",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "n-day dcheck-fail (upstream-regress)",
    },
    {
        "prefix": "5ef4474e",
        "kind": "check-abort",
        "impact": "dos",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "n-day dcheck-fail (upstream-regress)",
    },
    {
        "prefix": "17eb58fdcb",
        "kind": "use-after-free",
        "impact": "dos",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "weakref scavenger stale read — crash-only (M5-03), n-day",
    },
]

CALIB_ITEMS: list[dict] = [
    {
        "id": "calib-567177599",
        "kind": "miscompile",
        "impact": "none",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "turbolev peeling phi type — representation-only, consumers checked (M5-03)",
    },
    {
        "id": "calib-c2001427",
        "kind": "check-abort",
        "impact": "dos",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "check-fail-parse (PreparseDataBuilder size), n-day",
    },
    {
        "id": "calib-be64fd6d",
        "kind": "miscompile",
        "impact": "none",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "maglev range analysis ×∞ — representation-only (M5-03)",
    },
    {
        "id": "calib-regexp-56786f2a",
        "kind": "wrong-result",
        "impact": "none",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "regexp lookbehind wrong capture — correctness, n-day",
    },
    {
        "id": "calib-567129324",
        "kind": "type-confusion",
        "impact": "dos",
        "next": "close",
        "exploitable": 0.0,
        "ladder": 0.0,
        "note": "maglev weaker-check oddball vào Smi-field — leak hằng, không đủ L1 (M5-03)",
    },
]

_EXCLUDED = {
    "calib-wasm-2338fbb0": "arch-locked (riscv64/loong64/mips64/ppc64/s390x), không trigger x64",
    "calib-539984773": "revert drift — không tái hiện (no-crash)",
}


def _calib_state(bug: dict) -> str:
    flags = " ".join(bug.get("repro_flags") or [])
    repro = bug.get("repro_js") or ""
    # head 30 dòng, bỏ dòng comment nguồn (có tên bug → rò manh mối nhãn)
    lines = [ln for ln in repro.splitlines() if not ln.strip().startswith("//")]
    state = "\n".join(
        [
            "# V8 calibration repro (d8, snapshot build)",
            f"repro_flags: {flags}",
            "## repro.js (head)",
            "\n".join(lines[:30]),
        ]
    )
    return state[: decide._STATE_MAX_CHARS]


def build_items() -> list[dict]:
    """Trả list item {id, state, labels{...}, note}. Ném lỗi nếu crash thiếu trong store."""
    out: list[dict] = []
    for it in CRASH_ITEMS:
        try:
            state, d = decide.build_crash_state(it["prefix"], include_pipeline_label=False)
        except FileNotFoundError:
            continue  # crash đã bị dọn — bỏ qua, không bịa
        out.append(
            {
                "id": f"crash:{d.name[:12]}",
                "state": state,
                "labels": {k: it[k] for k in ("kind", "impact", "next", "exploitable", "ladder")},
                "note": it["note"],
            }
        )
    bugs = {}
    bpath = paths.REPO_ROOT / "calibration" / "bugs.json"
    if bpath.is_file():
        bugs = {b["id"]: b for b in json.loads(bpath.read_text())}
    for it in CALIB_ITEMS:
        bug = bugs.get(it["id"])
        if bug is None:
            continue
        out.append(
            {
                "id": it["id"],
                "state": _calib_state(bug),
                "labels": {k: it[k] for k in ("kind", "impact", "next", "exploitable", "ladder")},
                "note": it["note"],
            }
        )
    return out


def dataset_path() -> Path:
    return paths.STORE_DIR / "s1" / "dataset.jsonl"


def write_dataset(items: list[dict] | None = None) -> Path:
    items = items if items is not None else build_items()
    p = dataset_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n")
    return p


def stats(items: list[dict] | None = None) -> dict:
    items = items if items is not None else build_items()
    counts: dict[str, dict] = {"kind": {}, "impact": {}}
    for i in items:
        for q in ("kind", "impact"):
            v = i["labels"][q]
            counts[q][v] = counts[q].get(v, 0) + 1
    return {"n": len(items), "counts": counts, "excluded": list(_EXCLUDED)}


# ── CLI ──────────────────────────────────────────────────────────────────────


def run_dataset_cmd(args) -> int:
    items = build_items()
    st = stats(items)
    print(f"s1 dataset: {st['n']} item (loại trừ: {', '.join(st['excluded'])})")
    for q in ("kind", "impact"):
        bits = " · ".join(f"{k}×{v}" for k, v in sorted(st["counts"][q].items()))
        print(f"  {q:<7}: {bits}")
    if getattr(args, "write", False):
        p = write_dataset(items)
        print(f"  → ghi {p}")
    for i in items[:3]:
        print(f"  ví dụ {i['id']}: kind={i['labels']['kind']} impact={i['labels']['impact']}")
    return 0
