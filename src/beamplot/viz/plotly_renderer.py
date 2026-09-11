from __future__ import annotations

from pathlib import Path

from beamplot.domain import BeamplotResult


class PlotlyBeamplotRenderer:
    """Render an interactive Beamplot as a standalone Plotly HTML file."""

    def render_to_html(
        self,
        result: BeamplotResult,
        path: str | Path,
        *,
        colors: dict[str, str] | None = None,
    ) -> Path:
        import plotly.graph_objects as go

        html_path = Path(path)

        diamond_color = (colors or {}).get("diamond", "#1f77b4")
        beam_color = (colors or {}).get("beam", "#1a1a1a")
        median_color = (colors or {}).get("median_marker", "#1a1a1a")
        publication_color = (colors or {}).get("publication", "#ff2d55")
        bg_color = (colors or {}).get("paper_bg", "#ffffff")
        text_color = (colors or {}).get("text", "#1a1a1a")
        grid_color = (colors or {}).get("grid", "#f0f0f0")
        mark_alpha = float((colors or {}).get("mark_alpha", 0.8))
        beam_alpha = float((colors or {}).get("beam_alpha", 0.6))
        is_dark = bg_color.lower() not in ("#ffffff", "#fff", "white")

        fig = go.Figure()

        for stats in result.yearly_stats:
            fig.add_trace(
                go.Scatter(
                    x=list(stats.citations),
                    y=[stats.year] * len(stats.citations),
                    mode="markers",
                    marker=dict(symbol="diamond", size=10, color=diamond_color, opacity=mark_alpha),
                    name=f"{stats.year} citations",
                    hovertemplate="Year=%{y}<br>Citations=%{x}<extra></extra>",
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[stats.minimum, stats.maximum],
                    y=[stats.year, stats.year],
                    mode="lines",
                    line=dict(color=beam_color, width=2),
                    opacity=beam_alpha,
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[stats.median],
                    y=[stats.year],
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=12, color=median_color, opacity=mark_alpha),
                    name="median",
                    hovertemplate="Year=%{y}<br>Median=%{x}<extra></extra>",
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[stats.publication_axis_value],
                    y=[stats.year],
                    mode="markers",
                    marker=dict(symbol="circle", size=11, color=publication_color, opacity=mark_alpha),
                    name="publications",
                    hovertemplate=(
                        f"Year={stats.year}<br>"
                        f"Publications={stats.publication_count}<extra></extra>"
                    ),
                    showlegend=False,
                )
            )

        fig.add_vline(
            x=result.global_median,
            line_width=1,
            line_dash="dash",
            line_color=median_color,
        )
        fig.add_vline(
            x=result.publication_scale_factor * result.publication_count_median,
            line_width=1,
            line_dash="dash",
            line_color=publication_color,
            opacity=0.6,
        )

        template = "plotly_dark" if is_dark else "plotly_white"
        fig.update_layout(
            template=template,
            title="Interactive Beamplot",
            xaxis_title=result.x_label,
            yaxis_title="Publication Year",
            hovermode="closest",
            margin=dict(l=60, r=40, t=60, b=60),
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=dict(color=text_color),
            xaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color),
            yaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color),
        )
        fig.write_html(str(html_path), include_plotlyjs="cdn", full_html=True)
        return html_path
