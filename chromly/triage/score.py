"""Triage score — M3-02: §5.4 (WRITE=3 > READ=1 · offset +2 · JIT +2 · dcheck −2 · toy −3)."""

from __future__ import annotations

JIT_PATHS = ("jit/", "maglev/", "turboshaft/", "compiler/", "codegen/")


def score(fault: dict, stack_text: str) -> dict:
    total = 0
    reasons: list[str] = []

    cls = fault.get("class", "other")
    access = fault.get("access") or {}
    if access.get("kind") == "write":
        total += 3
        reasons.append("WRITE +3")
    elif access.get("kind") == "read":
        total += 1
        reasons.append("READ +1")
    elif cls in ("use-after-free", "type-confusion-dcheck"):
        total += 3
        reasons.append(f"{cls} (write-ish) +3")

    low = stack_text.lower()
    if any(p in low for p in JIT_PATHS):
        total += 2
        reasons.append("gần JIT tier +2")

    if cls.startswith("dcheck"):
        total -= 2
        reasons.append("dcheck-only −2")

    if "test/fuzzer" in low or "fuzzer.cc" in low:
        total -= 3
        reasons.append("harness-related −3")

    return {"score": total, "reasons": reasons}
