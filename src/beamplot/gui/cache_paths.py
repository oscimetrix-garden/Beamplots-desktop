from __future__ import annotations

import re
from pathlib import Path


ASSETS_DIR = Path(__file__).parents[2] / "assets"
CACHE_DIR = ASSETS_DIR / "cache"
ACTIVE_DATASET_FILE = CACHE_DIR / "active_dataset.txt"


def dataset_key(source_path: str | Path | None = None) -> str:
    name = Path(source_path).stem if source_path else "default"
    key = re.sub(r"[^0-9A-Za-z._-]+", "_", name).strip("._-")
    return key or "default"


def dataset_cache_dir(source_path: str | Path | None = None) -> Path:
    return CACHE_DIR / dataset_key(source_path)


def set_active_dataset(source_path: str | Path | None) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_DATASET_FILE.write_text(dataset_key(source_path), encoding="utf-8")


def active_dataset_cache_dir() -> Path:
    try:
        key = ACTIVE_DATASET_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        key = "default"
    return CACHE_DIR / (key or "default")


def relative_to_assets(path: Path) -> str:
    try:
        return path.relative_to(ASSETS_DIR).as_posix()
    except ValueError:
        return path.as_posix()
