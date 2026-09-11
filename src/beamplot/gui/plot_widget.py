from __future__ import annotations

import html as html_lib
import json
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, Qt, QPoint, QUrl
from PyQt5.QtGui import QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QStackedWidget, QLabel

from beamplot.domain import BeamplotResult
from beamplot.core.formatting import fmt_num
from beamplot.viz import BeamplotRenderer
from models.i18n import I18n
from models.theme_manager import ThemeManager

if TYPE_CHECKING:
    from beamplot.domain import YearBeamStats


class SelectionBridge(QObject):
    """Bridge object for JavaScript to Python communication."""
    
    point_clicked = pyqtSignal(dict)
    region_selected = pyqtSignal(dict)
    publication_hovered = pyqtSignal(dict)
    publication_unhovered = pyqtSignal()
    reset_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    @pyqtSlot(str)
    def onPointClicked(self, data: str) -> None:
        """Called from JavaScript when a point is clicked."""
        try:
            info = json.loads(data)
            self.point_clicked.emit(info)
        except json.JSONDecodeError:
            pass
    
    @pyqtSlot(str)
    def onRegionSelected(self, data: str) -> None:
        """Called from JavaScript when a region is selected."""
        try:
            info = json.loads(data)
            self.region_selected.emit(info)
        except json.JSONDecodeError:
            pass

    @pyqtSlot(str)
    def onPublicationHovered(self, data: str) -> None:
        try:
            info = json.loads(data)
            self.publication_hovered.emit(info)
        except json.JSONDecodeError:
            pass

    @pyqtSlot()
    def onPublicationUnhovered(self) -> None:
        self.publication_unhovered.emit()

    @pyqtSlot()
    def onResetRequested(self) -> None:
        self.reset_requested.emit()


class InteractivePlotPage(QWebEnginePage):
    """Custom page to handle JavaScript console messages."""

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        pass


class PlotWebEngineView(QWebEngineView):
    """WebEngine view with context menu disabled for embedded plot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.NoContextMenu)

    def contextMenuEvent(self, event) -> None:
        event.accept()


class BeamplotCanvas(QWidget):
    """Widget that can display both static (Matplotlib) and interactive (Plotly) beamplots."""
    
    point_clicked = pyqtSignal(dict)
    region_selected = pyqtSignal(dict)
    publication_hovered = pyqtSignal(dict)
    publication_unhovered = pyqtSignal()
    reset_requested = pyqtSignal()
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = "interactive"
        self._current_result: BeamplotResult | None = None
        self._raw_result: BeamplotResult | None = None
        self._interactive_html_path: Path | None = None
        self._publication_rows: list[dict] = []
        self._static_dirty = True
        self._interactive_dirty = True
        self._rendered_modes: set[str] = set()
        self.i18n = I18n.instance()
        self._tm = ThemeManager.instance()

        is_dark = self._tm.is_dark
        bg = "#2a2a2a" if is_dark else "#ffffff"
        text = "#e8e8e8" if is_dark else "#1a1a1a"
        grid = "#363636" if is_dark else "#f0f0f0"
        self._theme_colors = {
            "plot_bg": bg,
            "paper_bg": bg,
            "text": text,
            "grid": grid,
            "hint_bg": "rgba(255,255,255,0.16)" if is_dark else "rgba(0,0,0,0.70)",
            "hint_text": text if is_dark else "#ffffff",
        }
        
        self.stack = QStackedWidget(self)

        # -- static (matplotlib) --
        self.static_widget = QWidget(self)
        self.figure = Figure(figsize=(9, 6))
        self.figure.set_facecolor(bg)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setStyleSheet(f"background-color: {bg};")
        self.renderer = BeamplotRenderer()
        static_layout = QVBoxLayout(self.static_widget)
        static_layout.setContentsMargins(0, 0, 0, 0)
        static_layout.addWidget(self.canvas)

        # -- interactive (plotly WebView) --
        self.interactive_widget = QWidget(self)
        self.interactive_widget.setAutoFillBackground(True)
        self.interactive_widget.setStyleSheet(f"background-color: {bg};")
        self.web_view = PlotWebEngineView(self)
        self.web_page = InteractivePlotPage(self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_page.setBackgroundColor(QColor(bg))

        self.bridge = SelectionBridge(self)
        self.channel = QWebChannel(self.web_page)
        self.channel.registerObject("bridge", self.bridge)
        self.web_page.setWebChannel(self.channel)

        self.bridge.point_clicked.connect(self.point_clicked.emit)
        self.bridge.region_selected.connect(self.region_selected.emit)
        self.bridge.publication_hovered.connect(self.publication_hovered.emit)
        self.bridge.publication_unhovered.connect(self.publication_unhovered.emit)
        self.bridge.reset_requested.connect(self.reset_requested.emit)

        interactive_layout = QVBoxLayout(self.interactive_widget)
        interactive_layout.setContentsMargins(0, 0, 0, 0)
        interactive_layout.addWidget(self.web_view)

        # -- placeholder (native QWidget, no WebView) --
        self.hint_widget = QWidget(self)
        self.hint_widget.setAutoFillBackground(True)
        self.hint_line1 = QLabel(self.hint_widget)
        self.hint_line2 = QLabel(self.hint_widget)
        self.hint_line1.setAlignment(Qt.AlignCenter)
        self.hint_line2.setAlignment(Qt.AlignCenter)
        hint_layout = QVBoxLayout(self.hint_widget)
        hint_layout.setContentsMargins(24, 0, 24, 0)
        hint_layout.setSpacing(6)
        hint_layout.addStretch(1)
        hint_layout.addWidget(self.hint_line1)
        hint_layout.addWidget(self.hint_line2)
        hint_layout.addStretch(1)
        self._style_hint_widget()

        self.stack.addWidget(self.static_widget)     # 0
        self.stack.addWidget(self.interactive_widget) # 1
        self.stack.addWidget(self.hint_widget)        # 2

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.i18n.language_changed.connect(self.refresh_language)
        self.set_mode("interactive")
    
    def _style_hint_widget(self) -> None:
        bg = self._theme_colors.get("paper_bg", "#ffffff")
        secondary = self._tm.text_secondary
        ff = self._tm.font_family
        self.hint_widget.setStyleSheet(f"background-color: {bg};")
        hint_style = (
            f"color: {secondary}; font-size: 14px; font-family: '{ff}'; "
            f"background: transparent;"
        )
        self.hint_line1.setText(self.i18n.t("beamplot_plot_hint_line1"))
        self.hint_line2.setText(self.i18n.t("beamplot_plot_hint_line2"))
        self.hint_line1.setStyleSheet(hint_style)
        self.hint_line2.setStyleSheet(hint_style)

    def set_mode(self, mode: str, auto_render: bool = False) -> None:
        """Set display mode: 'static' or 'interactive'.

        When auto_render is False (default), switching mode does NOT
        trigger a render – the user must click 'Beamplots Viz.' explicitly.
        """
        if mode == self._mode and self._current_result is not None and not auto_render:
            self._render_if_previously_drawn(mode)
            return
        self._mode = mode
        if mode == "static":
            self.stack.setCurrentWidget(self.static_widget)
        else:
            if self._current_result is not None and "interactive" in self._rendered_modes:
                self.stack.setCurrentWidget(self.interactive_widget)
            else:
                self.stack.setCurrentWidget(self.hint_widget)

        if not auto_render:
            if self._render_if_previously_drawn(mode):
                return
            return

        if self._current_result is not None:
            if mode == "static" and self._static_dirty:
                self._render_static(self._current_result)
            elif mode == "interactive" and self._interactive_dirty:
                self._render_interactive(self._current_result)
    
    def get_mode(self) -> str:
        return self._mode

    def set_pending_mode(self, mode: str) -> None:
        """Record the target mode before a new result is rendered."""
        self._mode = mode

    def refresh_language(self) -> None:
        self._interactive_dirty = True
        self._style_hint_widget()
        if self._current_result is not None and "interactive" in self._rendered_modes:
            self._render_interactive(self._current_result)

    def set_theme_colors(self, colors: dict[str, str]) -> None:
        self._theme_colors.update(colors)
        self._apply_active_theme_surfaces()
        self._interactive_dirty = True
        if self._current_result is not None and "interactive" in self._rendered_modes:
            self._render_interactive(self._current_result)

    def _apply_active_theme_surfaces(self) -> None:
        bg = self._theme_colors.get("paper_bg", "#ffffff")
        bg_color = QColor(bg)
        self.web_page.setBackgroundColor(bg_color)
        self.interactive_widget.setStyleSheet(f"background-color: {bg};")
        self.static_widget.setStyleSheet(f"background-color: {bg};")
        self.canvas.setStyleSheet(f"background-color: {bg};")
        self.figure.set_facecolor(bg)
        self.setStyleSheet(f"background-color: {bg};")
        self._style_hint_widget()

    def set_static_theme_colors(self, colors: dict[str, str]) -> None:
        self._static_theme_colors = colors
        self._static_dirty = True
        bg = colors.get("bg", self._theme_colors["paper_bg"])
        self.static_widget.setStyleSheet(f"background-color: {bg};")
        self.canvas.setStyleSheet(f"background-color: {bg};")
        self.figure.set_facecolor(bg)
        if self._current_result is not None and "static" in self._rendered_modes:
            self._render_static(self._current_result)
        elif self._mode == "static":
            self.canvas.draw_idle()

    def _render_if_previously_drawn(self, mode: str) -> bool:
        if self._current_result is None or mode not in self._rendered_modes:
            return False
        if mode == "static" and self._static_dirty:
            self._render_static(self._current_result)
            return True
        if mode == "interactive" and self._interactive_dirty:
            self._render_interactive(self._current_result)
            return True
        return False

    def render_result(
        self,
        result: BeamplotResult,
        *,
        raw_result: BeamplotResult | None = None,
    ) -> None:
        self._current_result = result
        self._raw_result = raw_result or result
        self._render_static(result)
        self._render_interactive(result)
        self.stack.setCurrentWidget(
            self.static_widget if self._mode == "static" else self.interactive_widget
        )

    def set_publication_rows(self, rows: object) -> None:
        self._publication_rows = [dict(row) for row in (rows or [])]
        self._interactive_dirty = True
    
    def _render_static(self, result: BeamplotResult) -> None:
        self.figure.clear()
        ax = self.figure.subplots()
        colors = getattr(self, "_static_theme_colors", None)
        self.renderer.render(result, ax=ax, theme_colors=colors)
        self.canvas.draw_idle()
        self._static_dirty = False
        self._rendered_modes.add("static")
    
    def _render_interactive(self, result: BeamplotResult) -> None:
        html_content = self._generate_interactive_html(result, raw_result=self._raw_result)
        # QWebEnginePage.setHtml is capped at ~2 MB; large/multi-file datasets
        # exceed it and render a blank page. Load from a temp file instead
        # (no size limit) so the plot always shows up.
        try:
            tmp_dir = Path(tempfile.gettempdir()) / "beamplot_interactive"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            if getattr(self, "_interactive_html_path", None):
                try:
                    Path(self._interactive_html_path).unlink()
                except OSError:
                    pass
            tmp_path = tmp_dir / f"plot_{uuid.uuid4().hex}.html"
            tmp_path.write_text(html_content, encoding="utf-8")
            self._interactive_html_path = tmp_path
            self.web_view.load(QUrl.fromLocalFile(str(tmp_path)))
        except OSError:
            # Fallback to setHtml if the temp file cannot be written.
            self.web_view.setHtml(html_content)
        self._interactive_dirty = False
        self._rendered_modes.add("interactive")
    
    def _generate_interactive_html(
        self,
        result: BeamplotResult,
        colors: dict[str, str] | None = None,
        *,
        raw_result: BeamplotResult | None = None,
    ) -> str:
        """Generate interactive Plotly HTML with click and selection support."""
        raw_result = raw_result or result
        raw_stats_by_year = {stats.year: stats for stats in raw_result.yearly_stats}
        traces = []
        t = self.i18n.t
        colors = colors or self._theme_colors
        diamond_color = colors.get("diamond", "#1f77b4")
        beam_color = colors.get("beam", colors["text"])
        median_color = colors.get("median_marker", colors["text"])
        publication_color = colors.get("publication", "#ff2d55")
        mark_alpha = colors.get("mark_alpha", 0.8)
        beam_alpha = colors.get("beam_alpha", 0.6)
        hover_bg = colors.get("paper_bg", "#ffffff")
        hover_text = colors.get("text", "#1a1a1a")
        hover_border = colors.get("grid", "#e8e8e8")
        hover_indicator_color = "#ffffff" if self._tm.is_dark else colors["text"]
        hidden_hoverlabel = {
            "bgcolor": "rgba(0,0,0,0)",
            "bordercolor": hover_indicator_color,
            "font": {"size": 1, "color": "rgba(0,0,0,0)"},
        }
        badge_bg = colors.get("plot_bg", "#2a2a2a") if self._tm.is_dark else "#f5f5f5"
        accent_color = self._tm.primary

        def _esc(value: object) -> str:
            return html_lib.escape(str(value or ""))

        def _keywords_tags(keywords_str: str) -> str:
            kws = [k.strip() for k in keywords_str.replace(";", ",").split(",") if k.strip()]
            if not kws:
                return ""
            return "".join(
                f"<span class='hover-kw-tag'>{_esc(k)}</span>" for k in kws[:8]
            )

        weighted = result.weighted

        def _fmt(value: object) -> str:
            return fmt_num(value)

        def _raw_citation(rec: dict, plot_value: float) -> float:
            if "citations" in rec:
                return float(rec.get("citations", plot_value))
            return float(plot_value)

        rows_by_year: dict[int, list[dict]] = {}
        weighted_records = list(result.records)
        for row_idx, row in enumerate(self._publication_rows):
            try:
                year = int(str(row.get("PY", row.get("year", ""))).strip())
                citations = float(str(row.get("TC", row.get("citations", "0")) or 0))
            except (TypeError, ValueError):
                continue
            plot_citations = (
                float(weighted_records[row_idx].citations)
                if row_idx < len(weighted_records)
                else citations
            )
            summary = {
                "pos": row_idx + 1,
                "authors": str(row.get("AU", row.get("Authors", "")) or ""),
                "title": str(row.get("TI", row.get("Title", "")) or ""),
                "source": str(row.get("SO", row.get("Source", "")) or ""),
                "keywords": str(row.get("DE", row.get("ID", "")) or ""),
                "lcs": str(row.get("LCS", "")),
                "gcs": str(row.get("GCS", row.get("TC", ""))),
                "doi": str(row.get("DI", row.get("DOI", "")) or ""),
                "year": year,
                "citations": citations,
                "plot_citations": plot_citations,
            }
            rows_by_year.setdefault(year, []).append(summary)
        
        for stats in result.yearly_stats:
            citations_list = list(stats.citations)
            # Stack duplicate citation values vertically, matching the static
            # matplotlib renderer (stripchart method="stack") so both views align.
            _seen: dict[float, int] = {}
            stacked_y: list[float] = []
            for c in citations_list:
                k = _seen.get(c, 0)
                _seen[c] = k + 1
                stacked_y.append(stats.y_position + k * 0.2)
            year_rows = rows_by_year.get(stats.year, [])
            citation_customdata = []
            for idx, c in enumerate(citations_list):
                first = year_rows[idx] if idx < len(year_rows) else {}
                records = [first] if first else []
                pos = first.get("pos", "")
                raw_year_stats = raw_stats_by_year.get(stats.year)
                if first:
                    raw_c = _raw_citation(first, c)
                elif raw_year_stats and idx < len(raw_year_stats.citations):
                    raw_c = float(raw_year_stats.citations[idx])
                else:
                    raw_c = float(c)
                kw_html = _keywords_tags(first.get("keywords", ""))
                hover = (
                    f"<div class='hover-head'>"
                    f"<span class='hover-p'>P{pos}</span>"
                    f"<span class='hover-badges'>"
                    f"<span class='hover-badge badge-year'>{stats.year}</span>"
                    f"<span class='hover-badge badge-lcs'>LCS {_esc(first.get('lcs',''))}</span>"
                    f"<span class='hover-badge badge-gcs'>GCS {_esc(first.get('gcs',''))}</span>"
                    f"<button type='button' class='hover-close' "
                    f"onclick='closeCitationHover(); event.stopPropagation();' aria-label='Close'>"
                    f"<svg width='14' height='14' viewBox='0 0 24 24' fill='none' "
                    f"stroke='{hover_text}' stroke-width='2' stroke-linecap='round'>"
                    f"<path d='M18 6L6 18M6 6l12 12'/></svg></button>"
                    f"</span></div>"
                    f"<div class='hover-sep'></div>"
                    f"<div class='hover-row'><b>Title:</b><span>{_esc(first.get('title',''))}</span></div>"
                    f"<div class='hover-row'><b>Journal:</b><span>{_esc(first.get('source',''))}</span></div>"
                    f"<div class='hover-row'><b>Authors:</b><span>{_esc(first.get('authors',''))}</span></div>"
                    f"<div class='hover-row hover-kw-row'><b>Keywords:</b><span class='hover-kw-wrap'>{kw_html}</span></div>"
                    if first else f"<div class='hover-title'>P?</div><div>{t('beamplot_year')}={stats.year}</div><div>{t('beamplot_citations')}={_fmt(raw_c)}</div>"
                )
                citation_customdata.append({
                    "type": "citation",
                    "year": stats.year,
                    "citations": raw_c,
                    "raw_citations": raw_c,
                    "records": records,
                    "hover": hover,
                })
            traces.append({
                "x": citations_list,
                "y": stacked_y,
                "mode": "markers",
                "type": "scatter",
                "marker": {"symbol": "diamond", "size": 10, "color": diamond_color, "opacity": mark_alpha},
                "name": f"{stats.year} citations",
                "hovertemplate": " <extra></extra>",
                "hoverlabel": hidden_hoverlabel,
                "showlegend": False,
                "customdata": citation_customdata,
            })
            
            traces.append({
                "x": [stats.minimum, stats.maximum],
                "y": [stats.y_position, stats.y_position],
                "mode": "lines",
                "type": "scatter",
                "line": {"color": beam_color, "width": 2},
                "opacity": beam_alpha,
                "hoverinfo": "skip",
                "showlegend": False,
            })
            
            raw_year_stats = raw_stats_by_year.get(stats.year, stats)
            traces.append({
                "x": [stats.median],
                "y": [stats.y_position - 0.2],
                "mode": "markers",
                "type": "scatter",
                "marker": {"symbol": "triangle-up", "size": 12, "color": median_color, "opacity": mark_alpha},
                "name": "median",
                "hovertemplate": f"{t('beamplot_year')}={stats.year}<br>{t('beamplot_median')}={_fmt(raw_year_stats.median)}<extra></extra>",
                "showlegend": False,
                "customdata": [{"type": "median", "year": stats.year, "median": raw_year_stats.median}],
            })
            
            traces.append({
                "x": [stats.publication_axis_value],
                "y": [stats.y_position + 0.2],
                "mode": "markers",
                "type": "scatter",
                "marker": {"symbol": "circle", "size": 11, "color": publication_color, "opacity": mark_alpha},
                "name": "publications",
                "hovertemplate": " <extra></extra>",
                "hoverlabel": hidden_hoverlabel,
                "showlegend": False,
                "customdata": [{
                    "type": "publication",
                    "year": stats.year,
                    "count": stats.publication_count,
                    "records": rows_by_year.get(stats.year, []),
                }],
            })
        
        x_tickformat = ".2f" if weighted else ""
        traces_json = json.dumps(traces)
        y_tickvals = [stats.y_position for stats in result.yearly_stats]
        y_ticktext = [str(stats.year) for stats in result.yearly_stats]
        y_tickvals_json = json.dumps(y_tickvals)
        y_ticktext_json = json.dumps(y_ticktext)
        y_axis_min = (min(y_tickvals) - 0.7) if y_tickvals else 0
        y_axis_max = (max(y_tickvals) + 0.7) if y_tickvals else 1
        global_median = result.global_median
        pub_median_line = result.publication_scale_factor * result.publication_count_median
        x_label = result.x_label if self.i18n.language == "en_US" else t("beamplot_x_axis_citations")
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; }}
        html, body {{ background: {colors["paper_bg"]}; }}
        #plot {{ width: 100%; height: 100vh; }}
        .modebar-btn[data-title]:hover::after {{
            background: {colors["hint_bg"]} !important;
            color: {colors["hint_text"]} !important;
            border: 1px solid {colors["grid"]} !important;
            border-radius: 6px !important;
            font-family: '{self._tm.font_family}' !important;
            font-size: 12px !important;
        }}
        .modebar-btn[data-title]:hover::before {{
            border-bottom-color: {colors["hint_bg"]} !important;
        }}
        .js-plotly-plot .plotly .hoverlayer .spikeline {{
            display: none !important;
        }}
        .js-plotly-plot .plotly .hoverlayer .hovertext .bg {{
            fill: transparent !important;
            stroke: {hover_indicator_color} !important;
            stroke-width: 1.5px !important;
        }}
        #custom-hover {{
            position: absolute;
            display: none;
            width: 560px;
            max-width: calc(100vw - 48px);
            z-index: 1000;
            background: {hover_bg};
            color: {hover_text};
            border: 1px solid {hover_border};
            border-radius: 10px;
            box-shadow: 0 8px 26px rgba(0, 0, 0, 0.18);
            padding: 14px 16px;
            font-family: '{self._tm.font_family}';
            font-size: 13px;
            line-height: 1.4;
            pointer-events: none;
            white-space: normal;
            word-break: break-word;
        }}
        #custom-hover .hover-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            font-weight: 700;
            font-size: 14px;
            color: {hover_text};
        }}
        #custom-hover .hover-p {{ font-size: 14px; font-weight: 700; }}
        #custom-hover .hover-badges {{
            display: flex;
            font-size: 12px;
            align-items: center;
        }}
        #custom-hover .hover-badge {{
            display: inline-block;
            background: {badge_bg};
            border: 1px solid {hover_border};
            border-radius: 5px;
            padding: 3px 8px;
            color: {accent_color};
            margin-right: 12px;
        }}
        #custom-hover .hover-close {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            margin-left: 4px;
            margin-right: 0;
            padding: 0;
            border: none;
            background: transparent;
            border-radius: 50%;
            cursor: pointer;
            pointer-events: auto;
            flex-shrink: 0;
        }}
        #custom-hover .hover-close:hover,
        #custom-hover .hover-close:active {{
            background: {'rgba(255,255,255,0.08)' if self._tm.is_dark else 'rgba(0,0,0,0.06)'};
            border-radius: 50%;
        }}
        #custom-hover .hover-sep {{
            height: 1px;
            background: {hover_border};
            margin: 8px 0 10px 0;
        }}
        #custom-hover .hover-row {{
            display: grid;
            grid-template-columns: 82px 1fr;
            gap: 6px;
            margin: 3px 0;
            align-items: start;
        }}
        #custom-hover .hover-row b {{
            font-weight: 600;
            color: {'#9e9e9e' if self._tm.is_dark else '#666'};
        }}
        #custom-hover .hover-kw-row {{ align-items: center; }}
        #custom-hover .hover-kw-wrap {{ display: flex; flex-wrap: wrap; gap: 5px; }}
        #custom-hover .hover-kw-tag {{
            display: inline-block;
            background: {badge_bg};
            border: 1px solid {hover_border};
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 12px;
        }}
        #custom-hover .hover-title {{
            font-weight: 700; font-size: 14px; margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <div id="plot"></div>
    <div id="custom-hover"></div>
    <script>
        var bridge = null;
        
        new QWebChannel(qt.webChannelTransport, function(channel) {{
            bridge = channel.objects.bridge;
        }});
        
        var traces = {traces_json};
        
        var layout = {{
            paper_bgcolor: "{colors["paper_bg"]}",
            plot_bgcolor: "{colors["plot_bg"]}",
            font: {{ color: "{colors["text"]}", family: "{self._tm.font_family}" }},
            title: {{
                text: "{t('beamplot_interactive_title')}",
                font: {{ size: 16, color: "{colors["text"]}" }}
            }},
            xaxis: {{
                title: "{x_label}",
                gridcolor: "{colors["grid"]}",
                color: "{colors["text"]}",
                zeroline: false,
                showspikes: false,
                {f'tickformat: "{x_tickformat}",' if x_tickformat else ''}
            }},
            yaxis: {{
                title: "{t('beamplot_y_axis')}",
                gridcolor: "{colors["grid"]}",
                color: "{colors["text"]}",
                zeroline: false,
                showspikes: false,
                tickmode: "array",
                tickvals: {y_tickvals_json},
                ticktext: {y_ticktext_json},
                range: [{y_axis_min}, {y_axis_max}]
            }},
            hovermode: "closest",
            hoverlabel: {{
                bgcolor: "{hover_bg}",
                bordercolor: "{hover_indicator_color}",
                font: {{ color: "{hover_text}", family: "{self._tm.font_family}", size: 12 }},
                align: "left"
            }},
            dragmode: "select",
            margin: {{ l: 70, r: 40, t: 60, b: 60 }},
            shapes: [
                {{
                    type: "line",
                    x0: {global_median},
                    x1: {global_median},
                    y0: 0,
                    y1: 1,
                    yref: "paper",
                    line: {{ color: "{beam_color}", width: 1, dash: "dash" }},
                    opacity: {mark_alpha}
                }},
                {{
                    type: "line",
                    x0: {pub_median_line},
                    x1: {pub_median_line},
                    y0: 0,
                    y1: 1,
                    yref: "paper",
                    line: {{ color: "{publication_color}", width: 1, dash: "dash" }},
                    opacity: {mark_alpha}
                }}
            ],
            annotations: [
                {{
                    x: {global_median},
                    y: 1.02,
                    yref: "paper",
                    text: "{t('beamplot_citation_median')}",
                    showarrow: false,
                    font: {{ size: 10, color: "{beam_color}" }}
                }},
                {{
                    x: {pub_median_line},
                    y: 1.02,
                    yref: "paper",
                    text: "{t('beamplot_pub_median')}",
                    showarrow: false,
                    font: {{ size: 10, color: "{publication_color}" }}
                }}
            ]
        }};
        
        var _hasSelection = false;

        function clearSelection(gd) {{
            _hasSelection = false;
            // Clear highlighted points
            var restyleUpdate = {{}};
            for (var i = 0; i < gd.data.length; i++) {{
                restyleUpdate["selectedpoints"] = null;
            }}
            Plotly.restyle(gd, {{selectedpoints: [null]}});
            // Remove visual selection rectangle / lasso outline
            Plotly.relayout(gd, {{selections: []}});
        }}

        function setDragMode(gd, mode) {{
            Plotly.relayout(gd, {{dragmode: mode}});
            var dragLayer = gd.querySelector(".nsewdrag");
            if (dragLayer) {{
                dragLayer.style.cursor = mode ? "crosshair" : "default";
            }}
        }}

        var boxSelectTool = {{
            name: "Box Select",
            title: "Box Select",
            icon: Plotly.Icons.selectbox,
            click: function(gd) {{
                clearSelection(gd);
                setDragMode(gd, "select");
            }}
        }};

        var lassoSelectTool = {{
            name: "Lasso Select",
            title: "Lasso Select",
            icon: Plotly.Icons.lasso,
            click: function(gd) {{
                clearSelection(gd);
                setDragMode(gd, "lasso");
            }}
        }};

        var resetTool = {{
            name: "Reset",
            title: "Reset",
            icon: {{
                width: 24,
                height: 24,
                path: "M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z",
                transform: "matrix(1 0 0 1 0 0)"
            }},
            click: function(gd) {{
                clearSelection(gd);
                closeCitationHover();
                if (bridge) {{ bridge.onResetRequested(); }}
            }}
        }};

        var config = {{
            responsive: true,
            displayModeBar: true,
            modeBarButtons: [
                ["toImage", "zoom2d", "pan2d"],
                [boxSelectTool, lassoSelectTool],
                ["zoomIn2d", "zoomOut2d", resetTool]
            ],
            modeBarButtonsToRemove: ["autoScale2d", "resetScale2d"],
            displaylogo: false
        }};
        
        Plotly.newPlot("plot", traces, layout, config);
        
        var plotDiv = document.getElementById("plot");
        var hoverBox = document.getElementById("custom-hover");
        var _pinnedHover = null;

        function hideCitationHover() {{
            hoverBox.style.display = "none";
        }}

        function unpinPointHover() {{
            _pinnedHover = null;
            if (plotDiv) {{
                Plotly.Fx.unhover(plotDiv);
            }}
        }}

        function closeCitationHover() {{
            hideCitationHover();
            unpinPointHover();
        }}

        function pinPointHover(point) {{
            if (!plotDiv || !point) return;
            _pinnedHover = {{
                curveNumber: point.curveNumber,
                pointNumber: point.pointIndex
            }};
            Plotly.Fx.hover(plotDiv, [_pinnedHover]);
        }}

        plotDiv.on("plotly_unhover", function() {{
            if (_pinnedHover) {{
                Plotly.Fx.hover(plotDiv, [_pinnedHover]);
            }}
        }});

        function showCitationHover(html, clientX, clientY) {{
            hoverBox.innerHTML = html;
            hoverBox.style.display = "block";
            var x = clientX + 16;
            var y = clientY + 16;
            var rect = hoverBox.getBoundingClientRect();
            if (x + rect.width > window.innerWidth - 12) x = window.innerWidth - rect.width - 12;
            if (y + rect.height > window.innerHeight - 12) y = window.innerHeight - rect.height - 12;
            hoverBox.style.left = Math.max(12, x) + "px";
            hoverBox.style.top = Math.max(12, y) + "px";
        }}

        plotDiv.on("plotly_click", function(data) {{
            if (!data.points || data.points.length === 0) {{
                closeCitationHover();
                return;
            }}
            var point = data.points[0];
            var custom = point.customdata || {{}};
            var evt = (data.event || {{}});
            var cx = evt.clientX || 0;
            var cy = evt.clientY || 0;

            pinPointHover(point);

            if (custom.type === "citation" && custom.hover) {{
                showCitationHover(custom.hover, cx, cy);
            }} else {{
                hideCitationHover();
            }}

            if (bridge) {{
                var info = {{
                    x: point.x,
                    y: point.y,
                    curveNumber: point.curveNumber,
                    pointIndex: point.pointIndex,
                    customdata: custom
                }};
                bridge.onPointClicked(JSON.stringify(info));
            }}
        }});
        
        plotDiv.on("plotly_selected", function(data) {{
            if (bridge && data && data.points && data.points.length > 0) {{
                _hasSelection = true;
                var selectedPoints = data.points.map(function(p) {{
                    return {{
                        x: p.x,
                        y: p.y,
                        customdata: p.customdata || null
                    }};
                }});
                
                var range = data.range || {{}};
                var info = {{
                    points: selectedPoints,
                    count: selectedPoints.length,
                    xRange: range.x || null,
                    yRange: range.y || null
                }};
                bridge.onRegionSelected(JSON.stringify(info));
            }}
        }});
        
        plotDiv.on("plotly_deselect", function() {{
            clearSelection(plotDiv);
        }});
        
        plotDiv.on("plotly_doubleclick", function() {{
            closeCitationHover();
            if (_hasSelection) {{
                clearSelection(plotDiv);
            }}
        }});
        
    </script>
</body>
</html>'''
        return html

    def hide_plot_indicator(self) -> None:
        self.web_view.page().runJavaScript(
            "if (typeof closeCitationHover === 'function') closeCitationHover();"
        )

    def hide_citation_hover(self) -> None:
        self.hide_plot_indicator()

    def save_figure(self, path: str) -> None:
        if self._mode == "static":
            self.figure.savefig(path, dpi=180, bbox_inches="tight")
        else:
            if self._current_result is not None:
                from beamplot.viz.plotly_renderer import PlotlyBeamplotRenderer
                renderer = PlotlyBeamplotRenderer()
                html_path = Path(path).with_suffix(".html")
                renderer.render_to_html(
                    self._current_result, html_path, colors=self._theme_colors
                )
            else:
                raise RuntimeError("No beamplot result available for export")
    
    def get_current_result(self) -> BeamplotResult | None:
        return self._current_result
