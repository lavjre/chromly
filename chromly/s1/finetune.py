"""Fine-tune laya trên dataset chromly (M5-05b) — script CPU vendored.

- `build_ft_items`: tokenize dataset (kind + impact) → items.pt đúng format script
  (`laya.common.build_sequence`, soft target 0.9/0.1).
- `run_finetune`: gọi `third_party/laya-finetune/finetune_cpu.py --device cpu`
  (2 epochs mặc định; CPU ~25–50' cho ~30 item; chạy nền bằng nohup khi cần).
- Eval sau train: `chromly s1 eval-ft` (xem eval.py).

Lưu ý: v1 train `kind` + `impact` (2 câu có phân bố thật); `ladder`/`exploitable`/`next`
toàn hằng số trong data hiện tại — đợi positives rồi bật (dataset.py có ghi lý do).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from chromly import paths
from chromly.s1 import dataset as ds
from chromly.s1 import decide

FT_SCRIPT = paths.REPO_ROOT / "third_party" / "laya-finetune" / "finetune_cpu.py"
FT_DIR = paths.STORE_DIR / "s1" / "ft"
TRAIN_QUESTIONS = ("kind", "impact")
HF_HUB = Path.home() / ".cache" / "huggingface" / "hub"


def hf_snapshot() -> Path:
    base = HF_HUB / "models--convaiinnovations--laya"
    snaps = sorted((base / "snapshots").glob("*")) if (base / "snapshots").is_dir() else []
    snaps = [s for s in snaps if (s / "model.safetensors").is_file()]
    if not snaps:
        raise RuntimeError(
            "chưa có checkpoint base trong HF cache — chạy `chromly s1 check` (tải model) trước"
        )
    return snaps[-1]


def build_ft_items(
    items: list[dict] | None = None,
    out_path: Path | None = None,
    holdout: set[str] | frozenset[str] = frozenset(),
    questions: tuple[str, ...] = TRAIN_QUESTIONS,
) -> dict:
    """Build `train_items.pt` cho script fine-tune. Trả {n_items, n_skipped, path, holdout}."""
    import torch
    from laya.common import build_sequence, render_options
    from transformers import AutoTokenizer

    items = items if items is not None else ds.build_items()
    out_path = out_path or (FT_DIR / "train_items.pt")
    snap = hf_snapshot()
    cfg = json.loads((snap / "rl_agent_config.json").read_text())
    tok = AutoTokenizer.from_pretrained(snap / "tokenizer")

    ft_items: list[dict] = []
    skipped = 0
    for it in items:
        if it["id"] in holdout:
            continue
        for qid in questions:
            q = decide.CRASH_QUESTIONS[qid]
            crit = q["criteria"]
            gold = it["labels"][qid]
            keys = list(crit.keys())
            if gold not in keys:
                skipped += 1
                continue
            target = [0.9 if k == gold else 0.1 / max(1, len(keys) - 1) for k in keys]
            seq, markers = build_sequence(
                tok,
                it["state"],
                {"t": "choice", "ins": q["instructions"], "crit": crit},
                cfg.get("max_len", 1024),
                cfg.get("head_max_len", 256),
            )
            if len(markers) != len(render_options({"t": "choice", "crit": crit})):
                skipped += 1
                continue
            ft_items.append(
                {
                    "ids": seq,
                    "markers": markers,
                    "qtype": 0,
                    "target": target,
                    "label": keys.index(gold),
                }
            )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(ft_items, out_path)
    return {
        "n_items": len(ft_items),
        "n_skipped": skipped,
        "path": str(out_path),
        "holdout": sorted(holdout),
    }


def run_finetune(
    epochs: int = 2,
    holdout: str = "",
    device: str = "cpu",
    out_name: str = "chromly-ft-v1",
) -> int:
    holdout_set = {h for h in holdout.split(",") if h}
    items = ds.build_items()
    info = build_ft_items(items, holdout=holdout_set)
    print(f"ft items: {info['n_items']} (skip {info['n_skipped']}) · holdout={info['holdout']}")
    out_dir = FT_DIR / out_name
    cmd = [
        sys.executable,
        str(FT_SCRIPT),
        "--model-dir",
        str(hf_snapshot()),
        "--items",
        info["path"],
        "--output-dir",
        str(out_dir),
        "--epochs",
        str(epochs),
        "--device",
        device,
        "--micro-batch",
        "1",
        "--grad-accum",
        "4",
        "--calib-max",
        "200",
    ]
    log = FT_DIR / f"{out_name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    print(f"train: {' '.join(cmd)}\nlog → {log}")
    with log.open("a") as fh:
        fh.write(f"\n$ {' '.join(cmd)}\n")
        fh.flush()
        return subprocess.call(cmd, stdout=fh, stderr=subprocess.STDOUT)


def run_finetune_cmd(args) -> int:
    return run_finetune(
        epochs=getattr(args, "epochs", 2),
        holdout=getattr(args, "holdout", "") or "",
        device=getattr(args, "device", "cpu"),
        out_name=getattr(args, "name", "chromly-ft-v1"),
    )
