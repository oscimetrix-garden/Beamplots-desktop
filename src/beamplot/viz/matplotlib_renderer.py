from __future__ import annotations

from collections import defaultdict

from matplotlib.axes import Axes
from matplotlib.figure import Figure

from beamplot.domain import BeamplotResult, YearBeamStats

ThemeColors = dict[str, str] | None

_DEFAULT_DIAMOND = "#1f77b4"
_DEFAULT_BEAM = "black"
_DEFAULT_MEDIAN_MARKER = "black"


class BeamplotRenderer:
    """Render a Beamplot equivalent to the WoS path in BibPlots."""

    def render(
        self,
        result: BeamplotResult,
        ax: Axes | None = None,
        theme_colors: ThemeColors = None,
    ) -> Figure:
        if ax is None:
            from matplotlib import pyplot as plt

            figure, ax = plt.subplots(figsize=(10, 6))
        else:
            figure = ax.figure

        ax.clear()

        if theme_colors:
            bg = theme_colors.get("bg", "#ffffff")
            figure.set_facecolor(bg)
            ax.set_facecolor(bg)

        diamond_color = (theme_colors or {}).get("diamond", _DEFAULT_DIAMOND)
        beam_color = (theme_colors or {}).get("beam", _DEFAULT_BEAM)
        median_color = (theme_colors or {}).get("median_marker", _DEFAULT_MEDIAN_MARKER)
        publication_color = (theme_colors or {}).get("publication", "red")
        mark_alpha = (theme_colors or {}).get("mark_alpha", 1.0)
        beam_alpha = (theme_colors or {}).get("beam_alpha", mark_alpha)

        self._draw_stripchart_points(ax, result.yearly_stats, diamond_color, mark_alpha)
        self._draw_year_beams(ax, result.yearly_stats, beam_color, median_color, beam_alpha, mark_alpha)
        self._draw_publication_axis(ax, result, beam_color, publication_color, theme_colors, mark_alpha)
        self._style_axes(ax, result, theme_colors)
        figure.tight_layout()
        return figure

    def _draw_stripchart_points(
        self,
        ax: Axes,
        yearly_stats: tuple[YearBeamStats, ...],
        diamond_color: str = _DEFAULT_DIAMOND,
        mark_alpha: float = 1.0,
    ) -> None:
        for stats in yearly_stats:
            x_values, y_values = _stacked_positions(stats)
            ax.scatter(
                x_values,
                y_values,
                marker="D",
                color=diamond_color,
                alpha=mark_alpha,
                s=32,
                zorder=3,
            )

    def _draw_year_beams(
        self,
        ax: Axes,
        yearly_stats: tuple[YearBeamStats, ...],
        beam_color: str = _DEFAULT_BEAM,
        median_color: str = _DEFAULT_MEDIAN_MARKER,
        beam_alpha: float = 1.0,
        mark_alpha: float = 1.0,
    ) -> None:
        for stats in yearly_stats:
            ax.hlines(
                y=stats.y_position,
                xmin=stats.minimum,
                xmax=stats.maximum,
                colors=beam_color,
                alpha=beam_alpha,
                linewidth=1.2,
                zorder=2,
            )
            ax.scatter(
                [stats.median],
                [stats.y_position - 0.2],
                marker="^",
                color=median_color,
                alpha=mark_alpha,
                s=52,
                zorder=4,
            )

    def _draw_publication_axis(
        self,
        ax: Axes,
        result: BeamplotResult,
        beam_color: str = _DEFAULT_BEAM,
        publication_color: str = "red",
        theme_colors: ThemeColors = None,
        mark_alpha: float = 1.0,
    ) -> None:
        for stats in result.yearly_stats:
            ax.scatter(
                [stats.publication_axis_value],
                [stats.y_position + 0.2],
                marker="o",
                color=publication_color,
                alpha=mark_alpha,
                s=42,
                zorder=4,
            )

        ax.axvline(
            result.global_median,
            linestyle=(0, (6, 6)),
            color=beam_color,
            alpha=mark_alpha,
            linewidth=1.0,
        )
        ax.axvline(
            result.publication_scale_factor * result.publication_count_median,
            linestyle=(0, (6, 6)),
            color=publication_color,
            alpha=mark_alpha,
            linewidth=1.0,
        )

        top_axis = ax.secondary_xaxis(
            "top",
            functions=(
                lambda value: value / result.publication_scale_factor
                if result.publication_scale_factor
                else value,
                lambda value: value * result.publication_scale_factor,
            ),
        )
        max_publications = max(stats.publication_count for stats in result.yearly_stats)
        top_axis.set_xticks(range(0, max_publications + 1))
        top_axis.tick_params(axis="x", colors=publication_color)
        top_axis.spines["top"].set_color(publication_color)
        top_axis.set_xlabel("Number of publications", color=publication_color, labelpad=12)

        if theme_colors:
            bg = theme_colors.get("bg", "#ffffff")
            text_color = theme_colors.get("text", "black")
            top_axis.set_facecolor(bg)
            top_axis.spines["bottom"].set_color(text_color)

    def _style_axes(
        self,
        ax: Axes,
        result: BeamplotResult,
        theme_colors: ThemeColors = None,
    ) -> None:
        y_positions = [stats.y_position for stats in result.yearly_stats]
        y_labels = [str(stats.year) for stats in result.yearly_stats]
        ax.set_yticks(y_positions)
        ax.set_yticklabels(y_labels)
        ax.set_ylim(min(y_positions) - 0.7, max(y_positions) + 0.7)
        ax.set_xlabel(result.x_label)
        ax.set_ylabel("Publication Year")

        if theme_colors:
            text_color = theme_colors.get("text", "black")
            grid_color = theme_colors.get("grid", "#cccccc")

            ax.xaxis.label.set_color(text_color)
            ax.yaxis.label.set_color(text_color)
            ax.tick_params(axis="both", colors=text_color)
            for spine in ax.spines.values():
                spine.set_color(text_color)
            ax.grid(axis="x", linestyle=":", alpha=0.25, color=grid_color)
        else:
            ax.grid(axis="x", linestyle=":", alpha=0.25)


def _stacked_positions(stats: YearBeamStats, offset: float = 0.2) -> tuple[list[float], list[float]]:
    """Deterministic approximation of R stripchart(method='stack')."""

    seen: dict[float, int] = defaultdict(int)
    x_values: list[float] = []
    y_values: list[float] = []
    for citation in stats.citations:
        stack_index = seen[citation]
        seen[citation] += 1
        x_values.append(citation)
        y_values.append(stats.y_position + stack_index * offset)
    return x_values, y_values
