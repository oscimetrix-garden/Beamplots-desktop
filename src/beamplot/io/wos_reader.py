from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

from beamplot.domain import CitationRecord

_WOS_SUFFIXES = {".txt", ".ciw", ".wos"}


def _looks_like_wos_file(path: Path) -> bool:
    """Lightweight header check to skip non-WoS text files inside folders."""
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(4096)
    except OSError:
        return False
    upper = head.upper()
    return (
        "FN CLARIVATE" in upper
        or "FN THOMSON" in upper
        or ("\nPT " in upper and "\nER" in upper)
        or upper.startswith("PT ")
    )


def discover_wos_files(paths: Sequence[str | Path]) -> list[Path]:
    """Expand files/folders into a de-duplicated list of WoS plain-text files."""
    found: list[Path] = []
    seen: set[str] = set()

    def _add(file_path: Path, *, require_wos_header: bool) -> None:
        if require_wos_header and not _looks_like_wos_file(file_path):
            return
        key = str(file_path.resolve())
        if key in seen:
            return
        seen.add(key)
        found.append(file_path)

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(f"WoS path does not exist: {path}")
        if path.is_file():
            if path.suffix.lower() in _WOS_SUFFIXES or path.suffix == "":
                # Explicitly selected files are accepted; metaknowledge validates later.
                _add(path, require_wos_header=False)
            continue
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in _WOS_SUFFIXES:
                    _add(child, require_wos_header=True)
    return found


def read_wos_records(path: str | Path) -> tuple[CitationRecord, ...]:
    """Read WoS records using metaknowledge only."""
    records, _rows = read_wos_records_and_rows(path)
    return records


def read_wos_dataframe_rows(path: str | Path) -> list[dict[str, Any]]:
    """Read the full WoS/metaknowledge table as row dictionaries."""
    _records, rows = read_wos_records_and_rows(path)
    return rows


def read_wos_records_and_rows(
    path: str | Path | Sequence[str | Path],
) -> tuple[tuple[CitationRecord, ...], list[dict[str, Any]]]:
    """Read one or more WoS files/folders and merge all records."""
    if isinstance(path, (str, Path)):
        sources: list[Path] = [Path(path)]
    else:
        sources = [Path(p) for p in path]
    if not sources:
        raise FileNotFoundError("No WoS file or folder was provided")

    files = discover_wos_files(sources)
    if not files:
        raise FileNotFoundError("No WoS text files found in the selected path(s)")

    import metaknowledge as mk
    import pandas as pd

    all_rows: list[dict[str, Any]] = []
    for file_path in files:
        collection = mk.RecordCollection(str(file_path))
        if hasattr(collection, "make_dicts"):
            data = collection.make_dicts()
        else:
            data = collection.makeDict()
        df = pd.DataFrame(data)
        all_rows.extend(_normalize_row(row) for row in df.to_dict(orient="records"))

    records = records_from_rows(all_rows)
    return records, all_rows


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (list, tuple, set)):
            normalized[str(key)] = "; ".join(str(item) for item in value)
        elif value is None:
            normalized[str(key)] = ""
        else:
            normalized[str(key)] = value
    return normalized


def _first_available(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    raise KeyError(f"Record is missing required keys: {', '.join(keys)}")


def _parse_year(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid WoS publication year: {value!r}") from exc


def _parse_citations(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid WoS citation count: {value!r}") from exc


def records_from_rows(rows: Iterable[dict[str, Any]]) -> tuple[CitationRecord, ...]:
    """Test helper for building records from row dictionaries."""

    return tuple(
        CitationRecord(
            year=_parse_year(_first_available(row, "PY", "year", "Year")),
            citations=_parse_citations(_first_available(row, "TC", "timesCited", "Times Cited")),
        )
        for row in rows
    )
