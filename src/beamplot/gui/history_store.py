from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from beamplot.domain import BeamplotResult
from beamplot.gui.cache_paths import (
    active_dataset_cache_dir,
    dataset_cache_dir,
    relative_to_assets,
    set_active_dataset,
)


ASSETS_DIR = Path(__file__).parents[2] / "assets"
LEGACY_HISTORY_JSON = ASSETS_DIR / "history" / "beamplot_history.json"


def add_history_record(
    *,
    title: str,
    result: BeamplotResult | None,
    stats_result: BeamplotResult | None = None,
    plot_weighted: bool = False,
    image_path: str | Path | None = None,
    qa: list[dict[str, str]] | None = None,
    beamplot_text: str = "",
    ai_text: str = "",
    source_path: str | Path | None = None,
) -> dict:
    set_active_dataset(source_path)
    history_dir = dataset_cache_dir(source_path) / "history"
    records_dir = history_dir / "records"
    images_dir = history_dir / "images"
    records_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    history_json = records_dir / "beamplot_history.json"
    records = load_history_records(source_path)
    record_id = str(uuid.uuid4())[:8]
    stored_image = ""
    if image_path:
        src = Path(image_path)
        if src.exists():
            suffix = src.suffix or ".png"
            digest = _sha256_file(src)
            dst = images_dir / f"{digest}{suffix}"
            if not dst.exists():
                shutil.copyfile(src, dst)
            stored_image = relative_to_assets(dst)

    record = {
        "id": record_id,
        "title": title or "Beamplot Result",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "image": stored_image,
        "qa": qa or [],
        "beamplot_text": beamplot_text,
        "ai_text": ai_text,
        "summary": _result_summary(
            stats_result or result,
            plot_weighted=plot_weighted if stats_result else None,
        ) if (stats_result or result) else {},
    }
    records.append(record)
    history_json.write_text(json.dumps(records[-200:], ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def load_history_records(source_path: str | Path | None = None) -> list[dict]:
    base = dataset_cache_dir(source_path) if source_path else active_dataset_cache_dir()
    path = base / "history" / "records" / "beamplot_history.json"
    if not path.exists():
        path = LEGACY_HISTORY_JSON
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def delete_history_record(record_id: str, source_path: str | Path | None = None) -> None:
    base = dataset_cache_dir(source_path) if source_path else active_dataset_cache_dir()
    path = base / "history" / "records" / "beamplot_history.json"
    if not path.exists():
        return
    records = load_history_records(source_path)
    records = [record for record in records if str(record.get("id", "")) != str(record_id)]
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_history_records(source_path: str | Path | None = None) -> None:
    base = dataset_cache_dir(source_path) if source_path else active_dataset_cache_dir()
    path = base / "history" / "records" / "beamplot_history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[]", encoding="utf-8")


def resolve_asset_path(relative_path: str) -> Path:
    return ASSETS_DIR / relative_path if relative_path else Path()


def _result_summary(result: BeamplotResult, *, plot_weighted: bool | None = None) -> dict:
    return {
        "records": len(result.records),
        "years": list(result.years),
        "year_range": [min(result.years), max(result.years)] if result.years else [],
        "global_median": result.global_median,
        "publication_count_median": result.publication_count_median,
        "publication_scale_factor": result.publication_scale_factor,
        "weighted": plot_weighted if plot_weighted is not None else result.weighted,
        "plot_weighted": plot_weighted if plot_weighted is not None else result.weighted,
        "yearly_stats": [
            {
                "year": stats.year,
                "publication_count": stats.publication_count,
                "minimum": stats.minimum,
                "median": stats.median,
                "maximum": stats.maximum,
            }
            for stats in result.yearly_stats
        ],
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:24]


