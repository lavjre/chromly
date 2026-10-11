"""Budget governor — M4-03 (§11): caps + tier quyết định model.

Caps v0 (đo lại sau M4): case $2 · ngày $2.5 · tháng $55; rolling 5h $12 / tuần $30.
Nguồn: bảng `runs` (cost_est). v0: cost có thể thiếu (None→0) — wall vẫn đếm.
"""

from __future__ import annotations

import json

from chromly.store import db

CAPS = {
    "case": 2.0,
    "day": 2.5,
    "month": 55.0,
    "window5h": 12.0,
    "week": 30.0,
}

FLASH_MODEL = "opencode-go/deepseek-v4.1-flash"
FREE_CHAIN = ["opencode-go/longcat-2.5-preview-free", "opencode-go/space-bunny-free"]
PLAN_B_CHAIN = ["opencode-go/glm-5.3-flash", "opencode-go/mimo-v2.6-flash"]


def _usage(con, expr: str) -> float:
    row = con.execute(
        f"SELECT COALESCE(SUM(cost_est), 0) AS c FROM runs WHERE created >= {expr}"
    ).fetchone()
    return float(row["c"])


def usage() -> dict:
    con = db.ensure_db()
    try:
        return {
            "window5h": _usage(con, "datetime('now', '-5 hours')"),
            "day": _usage(con, "date('now')"),
            "week": _usage(con, "datetime('now', '-7 days')"),
            "month": _usage(con, "date('now', 'start of month')"),
        }
    finally:
        con.close()


def cost_per_case(days: int = 7) -> dict:
    """Chi phí / case trong N ngày: tổng cost_est ÷ số case tạo mới (kể cả case no-bug)."""
    con = db.ensure_db()
    try:
        cost = _usage(con, f"datetime('now', '-{int(days)} days')")
        row = con.execute(
            "SELECT COUNT(*) AS n FROM cases WHERE created >= datetime('now', ?)",
            (f"-{int(days)} days",),
        ).fetchone()
        n = int(row["n"] or 0)
        return {"days": days, "cost": cost, "cases": n, "per_case": (cost / n) if n else 0.0}
    finally:
        con.close()


def tier() -> str:
    """Ưu tiên: window nhà cung cấp (tháng → tuần/5h) là hard limit; cap ngày là policy mềm."""
    u = usage()
    if u["month"] >= CAPS["month"]:
        return "exhausted"
    if u["week"] >= CAPS["week"] or u["window5h"] >= CAPS["window5h"]:
        return "window-cap"
    if u["day"] >= CAPS["day"]:
        return "day-cap"
    return "flash"


def pick_model(high_score: bool = False) -> dict:
    """Quyết định model cho run kế tiếp. high_score: case score ≥ ngưỡng cao."""
    t = tier()
    if t == "flash":
        return {"tier": t, "model": FLASH_MODEL, "note": "bình thường"}
    if t == "window-cap":
        return {"tier": t, "model": FREE_CHAIN[0], "note": "chạm cửa sổ 5h/tuần → free"}
    if t == "day-cap":
        if high_score:
            return {
                "tier": t,
                "model": FREE_CHAIN[-1],
                "note": "chạm cap ngày → free, chỉ case score cao",
            }
        return {
            "tier": t,
            "model": FREE_CHAIN[-1],
            "note": "chạm cap ngày — case score thấp nên hoãn",
        }
    return {"tier": t, "model": PLAN_B_CHAIN[0], "note": "hết cap tháng → plan B"}


def check_case(est_cost: float = 2.0, high_score: bool = True) -> dict:
    """Cho phép/hoãn mở case mới theo cap case + ngày."""
    if est_cost > CAPS["case"]:
        return {"allow": False, "reason": f"est ${est_cost} > cap case ${CAPS['case']}"}
    u = usage()
    if u["day"] + est_cost > CAPS["day"] and not high_score:
        return {"allow": False, "reason": "cap ngày — chỉ nhận case score cao"}
    return {"allow": True, "model": pick_model(high_score)["model"]}


def run_budget_cmd(args) -> int:
    sub = getattr(args, "budget_cmd", None)
    if sub == "status" or sub is None:
        u = usage()
        t = tier()
        print(f"tier: {t}")
        for k, cap in CAPS.items():
            if k in u:
                print(f"  {k:<8} ${u[k]:.2f} / ${cap}")
        print(f"model kế tiếp: {pick_model()['model']}")
        return 0
    if sub == "check":
        res = check_case(est_cost=getattr(args, "est_cost", 2.0), high_score=True)
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print("usage: chromly budget {status|check}")
    return 2
