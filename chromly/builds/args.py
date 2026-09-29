"""GN args theo config (§5.1). Nguồn: `args/*.gn` — verify tên arg trên checkout trước khi đổi.

Header `# target: <gn target>` trong file .gn quyết định target build (mặc định d8).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ARGS_DIR = Path(__file__).parent / "args"
DEFAULT_TARGET = "d8"
CONFIG_NAMES = ("release", "dcheck", "asan", "fuzzilli", "libfuzzer", "calib")


@dataclass(frozen=True)
class BuildConfig:
    name: str
    target: str
    gn_args: dict[str, str]

    def args_gn(self) -> str:
        return "".join(f"{k} = {v}\n" for k, v in self.gn_args.items())


def load_config(name: str) -> BuildConfig:
    if name not in CONFIG_NAMES:
        raise ValueError(f"config không hợp lệ: {name} (chọn: {', '.join(CONFIG_NAMES)})")
    target = DEFAULT_TARGET
    gn_args: dict[str, str] = {}
    for raw in (ARGS_DIR / f"{name}.gn").read_text().splitlines():
        line = raw.strip()
        if line.startswith("#"):
            if line.startswith("# target:"):
                target = line.split(":", 1)[1].strip()
            continue
        if not line:
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"dòng args.gn không hợp lệ trong {name}.gn: {raw!r}")
        gn_args[key.strip()] = value.strip()
    return BuildConfig(name=name, target=target, gn_args=gn_args)


def args_gn_text(name: str) -> str:
    return load_config(name).args_gn()
