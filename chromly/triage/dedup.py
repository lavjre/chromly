"""Triage dedup — M3-02: chuẩn hoá stack → hash (bỏ địa chỉ/line để ổn định)."""

from __future__ import annotations

import hashlib
import re

FRAME_RE = re.compile(r"in (\S+) (\S+):(\d+)")


def normalize_stack(text: str) -> str:
    frames = []
    for line in text.splitlines():
        m = FRAME_RE.search(line)
        if m:
            func, file, _line = m.groups()
            frames.append(f"{func} {file}")
    return "\n".join(frames[:30])


def stack_hash(text: str, fault_class: str) -> str:
    norm = normalize_stack(text)
    return hashlib.sha1(f"{fault_class}\n{norm}".encode()).hexdigest()
