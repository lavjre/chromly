"""Prompt registry — M3-05: hash persona/skills/agent-config → prompt_registry (§7.1, §8).

Mọi thay đổi prompt (persona/skill/plugin/agent config) = hash mới; từ M4 Prompt CI gate
dựa trên bảng này. v0: chỉ ghi nhận + liệt kê.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from chromly import paths
from chromly.store import db


def _tracked_files() -> list[tuple[str, Path]]:
    runtime = paths.REPO_ROOT / "runtime"
    files: list[tuple[str, Path]] = [
        ("persona", runtime / "persona.txt"),
        ("agent", runtime / "opencode.json"),
    ]
    skills_dir = runtime / "skills"
    if skills_dir.is_dir():
        for d in sorted(skills_dir.iterdir()):
            f = d / "SKILL.md"
            if f.is_file():
                files.append((f"skill:{d.name}", f))
    return [(kind, f) for kind, f in files if f.is_file()]


def persona_hash() -> str:
    """sha256 của persona.txt hiện tại — ghi vào runs.prompt_hash (§8: truy vết run ↔ prompt)."""
    f = paths.REPO_ROOT / "runtime" / "persona.txt"
    try:
        return hashlib.sha256(f.read_bytes()).hexdigest()
    except OSError:
        return ""


def sync() -> list[dict]:
    """Hash các file prompt hiện tại, ghi hash mới vào registry. Trả các entry MỚI."""
    con = db.ensure_db()
    new_entries: list[dict] = []
    try:
        for kind, f in _tracked_files():
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            row = con.execute(
                "SELECT 1 FROM prompt_registry WHERE hash = ? AND kind = ?", (h, kind)
            ).fetchone()
            if row is not None:
                continue
            version = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y%m%d-%H%M")
            with con:
                con.execute(
                    "INSERT OR IGNORE INTO prompt_registry (hash, kind, version, diff_note) "
                    "VALUES (?, ?, ?, '')",
                    (h, kind, version),
                )
            new_entries.append({"hash": h[:12], "kind": kind, "version": version})
        return new_entries
    finally:
        con.close()


def list_registry() -> list[dict]:
    con = db.ensure_db()
    try:
        rows = con.execute(
            "SELECT hash, kind, version, created FROM prompt_registry ORDER BY created DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()
