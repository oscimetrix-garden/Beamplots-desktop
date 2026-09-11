from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from beamplot.domain import BeamplotResult, CitationRecord
from beamplot.core.formatting import fmt_num
from beamplot.gui.cache_paths import active_dataset_cache_dir, dataset_cache_dir, set_active_dataset


ASSETS_DIR = Path(__file__).parents[2] / "assets"
LEGACY_MEMORY_DIR = ASSETS_DIR / ".memory"


def save_beamplot_memory(
    result: BeamplotResult,
    records: tuple[CitationRecord, ...],
    metrics: dict[str, str],
    *,
    source_path: str = "",
    full_rows: list[dict[str, Any]] | None = None,
    plot_weighted: bool = False,
) -> None:
    """Persist the current Beamplot dataset for later AI questions."""
    set_active_dataset(source_path)
    memory_dir = dataset_cache_dir(source_path) / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    records_csv = memory_dir / "beamplot_records.csv"
    full_df_csv = memory_dir / "beamplot_full_dataframe.csv"
    full_df_json = memory_dir / "beamplot_full_dataframe.json"
    memory_json = memory_dir / "beamplot_memory.json"

    with records_csv.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=["year", "citations"])
        writer.writeheader()
        for record in records:
            writer.writerow({"year": record.year, "citations": record.citations})

    full_rows = full_rows or []
    full_fields = _collect_fields(full_rows)
    if full_rows:
        try:
            import pandas as pd

            df = pd.DataFrame(full_rows)
            df.to_csv(full_df_csv, index=False, encoding="utf-8-sig")
            df.to_json(full_df_json, orient="records", force_ascii=False, indent=2)
        except Exception:
            with full_df_csv.open("w", newline="", encoding="utf-8-sig") as fp:
                writer = csv.DictWriter(fp, fieldnames=full_fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(full_rows)
            full_df_json.write_text(json.dumps(full_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    yearly = [
        {
            "year": stats.year,
            "publication_count": stats.publication_count,
            "min_citations": stats.minimum,
            "median_citations": stats.median,
            "max_citations": stats.maximum,
            "citations": list(stats.citations),
        }
        for stats in result.yearly_stats
    ]
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_path": source_path,
        "weighted": False,
        "plot_weighted": plot_weighted,
        "record_count": len(records),
        "year_range": [min(result.years), max(result.years)] if result.years else [],
        "global_median": result.global_median,
        "publication_count_median": result.publication_count_median,
        "publication_scale_factor": result.publication_scale_factor,
        "metrics": metrics,
        "yearly_stats": yearly,
        "records_csv": str(records_csv),
        "full_dataframe_csv": str(full_df_csv) if full_rows else "",
        "full_dataframe_json": str(full_df_json) if full_rows else "",
        "full_dataframe_fields": full_fields,
        "full_dataframe_rows": _compact_rows(full_rows),
    }
    memory_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_beamplot_memory() -> dict[str, Any] | None:
    memory_json = active_dataset_cache_dir() / "memory" / "beamplot_memory.json"
    if not memory_json.exists():
        memory_json = LEGACY_MEMORY_DIR / "beamplot_memory.json"
    if not memory_json.exists():
        return None
    try:
        return json.loads(memory_json.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_memory_context(user_message: str = "") -> str:
    """Build compact context that tells the model to use saved Beamplot data first."""
    memory = load_beamplot_memory()
    if not memory:
        return ""

    metrics = memory.get("metrics", {})
    yearly_stats = memory.get("yearly_stats", [])
    full_rows = memory.get("full_dataframe_rows", [])
    fields = memory.get("full_dataframe_fields", [])
    plot_weighted = bool(memory.get("plot_weighted", memory.get("weighted")))
    lines = [
        "【Beamplot Memory】以下数据来自当前已加载的 metaknowledge/WoS 数据转换结果，应优先用于回答用户问题，再结合模型能力分析。",
        f"- 数据更新时间: {memory.get('updated_at', '')}",
        f"- 原始文件: {memory.get('source_path', '')}",
        f"- 记录数: {memory.get('record_count', 0)}",
        f"- 年份范围: {_fmt_range(memory.get('year_range', []))}",
        f"- 图表年龄加权: {'是' if plot_weighted else '否'}",
        "- 指标与交互数据均使用原始未加权被引次数。",
        "- 9个指标(metrics): "
        f"TC={metrics.get('tc')}, Avg.Cit.={metrics.get('avg')}, h-index={metrics.get('h')}, "
        f"g-index={metrics.get('g')}, i10-index={metrics.get('i10')}, hg-index={metrics.get('hg')}, "
        f"pi-index={metrics.get('pi')}, w-index={metrics.get('w')}, m-index={metrics.get('m')}",
        f"- 全局引用中位数: {fmt_num(memory.get('global_median'))}",
        f"- 发文量中位数: {fmt_num(memory.get('publication_count_median'))}",
        f"- 精简记录CSV路径: {memory.get('records_csv', '')}",
        f"- 完整母表CSV路径: {memory.get('full_dataframe_csv', '')}",
        f"- 完整母表JSON路径: {memory.get('full_dataframe_json', '')}",
        f"- 完整母表字段: {', '.join(fields[:80])}",
        "- 回答格式要求: 先基于完整母表(DataFrame)筛选/统计，涉及 metrics、逐年数据或文献列表时优先使用 Markdown 表格展示关键字段，再用简短段落解释。",
    ]
    lines.append(
        "- 数值格式要求: 引用次数及相关统计数值，整数不带小数，有小数部分时统一保留两位小数。"
    )

    requested_years = _extract_years(user_message)
    if requested_years:
        matched_rows = [row for row in full_rows if _row_year(row) in requested_years]
        if matched_rows:
            lines.append("用户问题涉及的年份筛选结果（来自完整母表DataFrame）:")
            for row in matched_rows[:60]:
                lines.append("- " + _format_row(row))
            if len(matched_rows) > 60:
                lines.append(f"- ... 其余 {len(matched_rows) - 60} 行已省略。")
        else:
            matched = [item for item in yearly_stats if int(item.get("year", -1)) in requested_years]
            if matched:
                lines.append("用户问题涉及的年份筛选结果（来自逐年统计）:")
                for item in matched:
                    citations = item.get("citations", [])
                    shown = ", ".join(
                        fmt_num(float(v)) for v in citations[:30]
                    )
                    if len(citations) > 30:
                        shown += f", ...（共{len(citations)}篇）"
                    lines.append(
                        f"- {item.get('year')}: 发文量={item.get('publication_count')}, "
                        f"引用min/median/max="
                        f"{fmt_num(item.get('min_citations'))}/"
                        f"{fmt_num(item.get('median_citations'))}/"
                        f"{fmt_num(item.get('max_citations'))}; "
                        f"逐篇引用=[{shown}]"
                    )
    else:
        if full_rows:
            lines.append("完整母表样例行（用于识别字段和可查询信息）:")
            for row in full_rows[:12]:
                lines.append("- " + _format_row(row))
        lines.append("逐年统计概览（year/count/min/median/max）:")
        for item in yearly_stats[:80]:
            lines.append(
                f"- {item.get('year')}: {item.get('publication_count')} / "
                f"{fmt_num(item.get('min_citations'))} / "
                f"{fmt_num(item.get('median_citations'))} / "
                f"{fmt_num(item.get('max_citations'))}"
            )
        if len(yearly_stats) > 80:
            lines.append(f"- ... 其余 {len(yearly_stats) - 80} 年已省略，可根据用户指定年份再筛选。")

    return "\n".join(lines)


def _extract_years(text: str) -> set[int]:
    return {int(match) for match in re.findall(r"\b(?:19|20)\d{2}\b", text or "")}


def _fmt_range(value: Any) -> str:
    if isinstance(value, list) and len(value) == 2:
        return f"{value[0]} - {value[1]}"
    return ""


def _collect_fields(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    return fields


def _compact_rows(rows: list[dict[str, Any]], limit: int = 300) -> list[dict[str, Any]]:
    preferred = [
        "AU", "AF", "TI", "SO", "PY", "TC", "DI", "DT", "DE", "ID",
        "AB", "CR", "C1", "RP", "EM", "UT",
    ]
    compact: list[dict[str, Any]] = []
    for row in rows[:limit]:
        out: dict[str, Any] = {}
        for key in preferred:
            if key in row and row.get(key) not in ("", None):
                out[key] = _truncate(row.get(key), 600 if key in {"AB", "CR"} else 240)
        for key, value in row.items():
            if len(out) >= 18:
                break
            if key not in out and value not in ("", None):
                out[key] = _truncate(value, 160)
        compact.append(out)
    return compact


def _row_year(row: dict[str, Any]) -> int | None:
    for key in ("PY", "year", "Year"):
        if key in row:
            try:
                return int(float(str(row[key]).strip()))
            except (TypeError, ValueError):
                return None
    return None


def _format_row(row: dict[str, Any]) -> str:
    keys = ["PY", "TC", "AU", "AF", "TI", "SO", "DI", "DT", "UT"]
    parts = []
    for key in keys:
        value = row.get(key)
        if value not in ("", None):
            parts.append(f"{key}={_truncate(value, 180)}")
    if not parts:
        for key, value in list(row.items())[:8]:
            if value not in ("", None):
                parts.append(f"{key}={_truncate(value, 120)}")
    return "; ".join(parts)


def _truncate(value: Any, limit: int) -> str:
    text = str(value).replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
