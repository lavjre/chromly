#!/usr/bin/env bash
# acceptance/M3-classify.sh — M3-02: classify 10 fixture + FP filter ≥90% + score ordering
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

if "$VENV_BIN/python" - <<'PY'
from chromly.triage import classify, score

CASES = [
    ("ERROR: AddressSanitizer: heap-buffer-overflow\nWRITE of size 8", "heap-buffer-overflow", False),
    ("ERROR: AddressSanitizer: heap-buffer-overflow\nREAD of size 4", "heap-buffer-overflow", False),
    ("ERROR: AddressSanitizer: heap-use-after-free\nREAD of size 4", "use-after-free", False),
    ("ERROR: AddressSanitizer: stack-buffer-overflow\n", "stack-buffer-overflow", False),
    ("Fatal error ...\nCheck failed: x.IsMap()", "type-confusion-dcheck", False),
    ("Fatal error ...\nCheck failed: a == b", "dcheck-fail", False),
    ("(timeout)", "timeout", True),
    ("Fatal process out of memory: heap allocation failed", "oom", True),
    ("", "other", True),
    ("Uncaught Error: fixture", "other", True),
]

correct_class = 0
correct_fp = 0
for text, expected_cls, expected_fp in CASES:
    got = classify.classify_text(text)
    if got["class"] == expected_cls:
        correct_class += 1
    if classify.is_false_positive(got["class"]) == expected_fp:
        correct_fp += 1

fp_acc = correct_fp / len(CASES)
print(f"classify đúng: {correct_class}/{len(CASES)}")
print(f"FP filter accuracy: {fp_acc:.0%}")
assert correct_class == len(CASES), "classify sai"
assert fp_acc >= 0.9, "FP filter <90%"

w = score.score({"class": "heap-buffer-overflow", "access": {"kind": "write"}}, "")
r = score.score({"class": "heap-buffer-overflow", "access": {"kind": "read"}}, "")
d = score.score({"class": "dcheck-fail", "access": None}, "")
print(f"score write={w['score']} read={r['score']} dcheck={d['score']}")
assert w["score"] > r["score"]
j = score.score({"class": "use-after-free", "access": None}, "in F src/jit/x.cc:1")
print(f"score jit={j['score']}")
assert j["score"] >= 5
PY
then
    pass "classify 10/10 + FP ≥90% + score ordering"
else
    fail "classify/score sai"
fi

ac_summary
