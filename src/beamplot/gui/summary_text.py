from __future__ import annotations

from beamplot.core.formatting import fmt_num
from beamplot.domain import BeamplotResult
from models.i18n import I18n


def format_beamplot_summary(
    *,
    result: BeamplotResult | None = None,
    summary: dict | None = None,
    i18n: I18n | None = None,
    plot_weighted: bool | None = None,
) -> str:
    """Format Beamplot statistical summary text for display or history."""
    i18n = i18n or I18n.instance()
    if result is not None:
        weighted = plot_weighted if plot_weighted is not None else result.weighted
        record_count = len(result.records)
        year_range = (
            f"{min(result.years)} - {max(result.years)}"
            if result.years
            else "-"
        )
        yearly_stats = [
            {
                "year": stats.year,
                "publication_count": stats.publication_count,
                "minimum": stats.minimum,
                "median": stats.median,
                "maximum": stats.maximum,
            }
            for stats in result.yearly_stats
        ]
        global_median = result.global_median
        publication_count_median = result.publication_count_median
        publication_scale_factor = result.publication_scale_factor
    elif summary:
        weighted = bool(
            summary.get("plot_weighted")
            if summary.get("plot_weighted") is not None
            else summary.get("weighted")
        )
        record_count = int(summary.get("records") or 0)
        year_range_value = summary.get("year_range") or []
        years = summary.get("years") or []
        if isinstance(year_range_value, list) and len(year_range_value) == 2:
            year_range = f"{year_range_value[0]} - {year_range_value[1]}"
        elif years:
            year_range = f"{min(years)} - {max(years)}"
        else:
            year_range = "-"
        yearly_stats = list(summary.get("yearly_stats") or [])
        global_median = summary.get("global_median", 0)
        publication_count_median = summary.get("publication_count_median", 0)
        publication_scale_factor = summary.get("publication_scale_factor", 0)
    else:
        return ""

    yes_no = i18n.t("beamplot_yes") if weighted else i18n.t("beamplot_no")
    lines = [
        i18n.t("beamplot_summary_title"),
        "",
        f"{i18n.t('beamplot_summary_paper_count')}: {record_count}",
        f"{i18n.t('beamplot_summary_year_range')}: {year_range}",
        f"{i18n.t('beamplot_summary_weighted')}: {yes_no}",
        (
            f"{i18n.t('beamplot_summary_global_median')}: "
            f"{fmt_num(global_median)}"
        ),
        (
            f"{i18n.t('beamplot_summary_pub_median')}: "
            f"{fmt_num(publication_count_median)}"
        ),
        (
            f"{i18n.t('beamplot_summary_pub_scale')}: "
            f"{fmt_num(publication_scale_factor)}"
        ),
        "",
        i18n.t("beamplot_summary_yearly_title"),
    ]
    for item in yearly_stats:
        lines.append(
            i18n.t(
                "beamplot_summary_yearly_line",
                year=item.get("year", "?"),
                count=item.get("publication_count", "?"),
                min=fmt_num(item.get("minimum", 0)),
                median=fmt_num(item.get("median", 0)),
                max=fmt_num(item.get("maximum", 0)),
            )
        )
    return "\n".join(lines)


def history_summary_text(record: dict, i18n: I18n | None = None) -> str:
    """Return Beamplots summary text for a history record in the current language."""
    i18n = i18n or I18n.instance()
    summary = record.get("summary") or {}
    if summary.get("records") or summary.get("yearly_stats"):
        return format_beamplot_summary(summary=summary, i18n=i18n)
    return record.get("beamplot_text", "") or str(summary)
