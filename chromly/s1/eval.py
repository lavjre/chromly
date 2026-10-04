"""Eval S1 fine-tuned trên holdout — so với base (server HTTP).

Load checkpoint local bằng `laya.load(dir)` (laya hỗ trợ local checkpoint dir), chạy
`kind` + `impact` trên các item bị giữ khỏi train, so nhãn + độ chính xác, so base
nếu server đang chạy. Kết quả: store/s1/eval-<name>.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from chromly import paths
from chromly.s1 import dataset as ds
from chromly.s1 import decide

DEFAULT_HOLDOUT = frozenset({"crash:94a4430f5878", "crash:3963f3ad627b", "crash:4a0da5f5a321"})
EVAL_QUESTIONS = ("kind", "impact")


def ft_dir(name: str) -> Path:
    return paths.STORE_DIR / "s1" / "ft" / name


def load_ft(name: str = "chromly-ft-v1"):
    import laya

    d = ft_dir(name)
    if not (d / "model.safetensors").is_file():
        d2 = d / "checkpoint_latest"
        if (d2 / "model.safetensors").is_file():
            d = d2
        else:
            raise FileNotFoundError(f"chưa có checkpoint fine-tuned ({d}/model.safetensors)")
    return laya.load(str(d), device="cpu")


def _pred_agent(agent, state: str, qid: str) -> tuple[str | None, float | None]:
    q = decide.CRASH_QUESTIONS[qid]
    res = agent.system_one(state, {qid: q})
    ans = res["answers"][qid]
    if q["type"] == "choice":
        return ans.get("choice"), ans.get("answer_confidence")
    return None, None


def _pred_base(state: str, qid: str) -> tuple[str | None, float | None]:
    q = decide.CRASH_QUESTIONS[qid]
    res = decide.ask(state, {qid: q})
    ans = res["answers"][qid]
    if q["type"] == "choice":
        return ans.get("choice"), ans.get("answer_confidence")
    return None, None


def eval_holdout(
    name: str = "chromly-ft-v1",
    holdout: frozenset[str] | set[str] = DEFAULT_HOLDOUT,
    compare_base: bool = True,
) -> dict:
    items = [i for i in ds.build_items() if i["id"] in holdout]
    if not items:
        raise RuntimeError("holdout rỗng — không có item nào")
    agent = load_ft(name)
    rows: list[dict] = []
    for it in items:
        for qid in EVAL_QUESTIONS:
            gold = it["labels"][qid]
            ft_pred, ft_conf = _pred_agent(agent, it["state"], qid)
            row = {
                "id": it["id"],
                "q": qid,
                "gold": gold,
                "ft": ft_pred,
                "ft_conf": ft_conf,
                "ft_ok": ft_pred == gold,
            }
            if compare_base:
                try:
                    base_pred, base_conf = _pred_base(it["state"], qid)
                    row.update(
                        {"base": base_pred, "base_conf": base_conf, "base_ok": base_pred == gold}
                    )
                except Exception as exc:  # noqa: BLE001 — eval không được chết vì server
                    row["base"] = f"(lỗi: {type(exc).__name__})"
            rows.append(row)
            print(
                f"  {it['id']:<22} {qid:<7} gold={gold:<16} "
                f"ft={ft_pred} ({ft_conf}) " + (f"base={row.get('base')}" if compare_base else ""),
                flush=True,
            )
    ft_acc = sum(r["ft_ok"] for r in rows) / len(rows)
    out = {
        "name": name,
        "ts": time.time(),
        "n": len(rows),
        "ft_acc": round(ft_acc, 4),
        "rows": rows,
    }
    if compare_base and any("base_ok" in r for r in rows):
        base_rows = [r for r in rows if "base_ok" in r]
        out["base_acc"] = round(sum(r["base_ok"] for r in base_rows) / len(base_rows), 4)
    p = paths.STORE_DIR / "s1" / f"eval-{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(
        f"\neval {name}: ft_acc={out['ft_acc']} (n={out['n']})"
        + (f" · base_acc={out.get('base_acc')}" if out.get("base_acc") is not None else "")
    )
    return out


def run_eval_cmd(args) -> int:
    try:
        eval_holdout(
            name=getattr(args, "name", "chromly-ft-v1"),
            compare_base=not getattr(args, "no_base", False),
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"s1 eval: {exc}")
        return 1
    return 0
