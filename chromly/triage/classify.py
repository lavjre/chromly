"""Triage classify + FP filter — M3-02 (§5.4)."""

from __future__ import annotations

import re


def classify_text(text: str) -> dict:
    """Phân loại từ output ASAN/dcheck. Trả {"class", "access", "signal"}."""
    cls = "other"
    access = None
    signal = None

    if "ERROR: AddressSanitizer: heap-buffer-overflow" in text:
        cls = "heap-buffer-overflow"
    elif "ERROR: AddressSanitizer: heap-use-after-free" in text:
        cls = "use-after-free"
    elif "ERROR: AddressSanitizer: stack-buffer-overflow" in text:
        cls = "stack-buffer-overflow"
    elif "ERROR: AddressSanitizer" in text:
        m = re.search(r"ERROR: AddressSanitizer: ([\w-]+)", text)
        cls = m.group(1) if m else "asan-other"
    elif "check failed" in text.lower():
        low = text.lower()
        if any(k in low for k in ("map", "instance type", "type check", "is_", "jsreceiver")):
            cls = "type-confusion-dcheck"
        else:
            cls = "dcheck-fail"
    elif "out of memory" in text.lower() or "oom" in text.lower():
        cls = "oom"

    if "(timeout)" in text or text.lower().startswith("timeout"):
        cls = "timeout"

    m = re.search(r"(READ|WRITE) of size (\d+)", text)
    if m:
        access = {"kind": m.group(1).lower(), "size": int(m.group(2))}

    m = re.search(r"(SIG[A-Z]+)", text)
    if m:
        signal = m.group(1)

    return {"class": cls, "access": access, "signal": signal}


def is_false_positive(cls: str) -> bool:
    return cls in ("timeout", "oom", "asan-other", "other")
