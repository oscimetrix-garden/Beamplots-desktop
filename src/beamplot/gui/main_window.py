from __future__ import annotations

import html as html_lib
import re
import tempfile
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, QTimer, QUrl, pyqtSignal, QSize, QEvent
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QHeaderView,
    QSplitter,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    ComboBox,
    EditableComboBox,
    FluentIcon,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    NavigationItemPosition,
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget,
    ScrollArea,
    TableWidget,
    TextEdit,
)

from beamplot.core import build_beamplot_result
from beamplot.core.formatting import fmt_num
from beamplot.domain import BeamplotResult, CitationRecord
from beamplot.gui.beamplot_chat import BeamplotChatBar
from beamplot.gui.history_store import (
    add_history_record,
    clear_history_records,
    delete_history_record,
    load_history_records,
    resolve_asset_path,
)
from beamplot.gui.summary_text import format_beamplot_summary, history_summary_text
from beamplot.gui.memory_store import build_memory_context, save_beamplot_memory
from beamplot.gui.plot_widget import BeamplotCanvas
from beamplot.io import discover_wos_files, read_wos_records_and_rows, records_from_rows
from chat.components.svg_icon import svg_icon
from models.i18n import I18n
from models.settings_view import SettingsView
from models.theme_manager import ThemeManager


ASSETS_DIR = Path(__file__).parents[2] / "assets"
ICON_DIR = ASSETS_DIR / "icons"
DEFAULT_DATA = ASSETS_DIR / "Robin Haunschild" / "Robin Haunschild.txt"


def _fit_window_to_screen(
    window: QWidget,
    preferred_width: int,
    preferred_height: int,
    minimum_width: int,
    minimum_height: int,
    screen_ratio: float = 0.92,
) -> None:
    """Resize and center a top-level window inside the current screen."""
    screen = window.screen() or QApplication.primaryScreen()
    if screen is None:
        window.resize(preferred_width, preferred_height)
        return

    geo = screen.availableGeometry()
    max_width = max(320, int(geo.width() * screen_ratio))
    max_height = max(240, int(geo.height() * screen_ratio))
    width = min(preferred_width, max_width)
    height = min(preferred_height, max_height)
    if max_width >= minimum_width:
        width = max(width, minimum_width)
    if max_height >= minimum_height:
        height = max(height, minimum_height)

    window.resize(width, height)
    window.move(
        geo.x() + (geo.width() - width) // 2,
        geo.y() + (geo.height() - height) // 2,
    )


BEAMPLOT_HELP_TEXT = (
    "Beamplot图中下方的 x 轴表示论文的被引次数，y 轴则按发表年份分布这些论文。"
    "研究者的每一篇论文都以黑色菱形标记呈现。"
    "某一发表年份对应的线条（即 \"波束\"），可视化了该年发表论文的被引次数范围。"
    "线条下方的黑色三角形表示该年发表论文的被引次数中位数。"
    "黑色虚线是所有年份的被引次数中位数。"
    "上方的 x 轴显示每年的论文数量。"
    "红色圆圈表示某一年的发表论文数量，红色虚线则是每年发表论文数量的中位数。"
)


class MemorySaveWorker(QThread):
    failed = pyqtSignal(str)

    def __init__(
        self,
        result: BeamplotResult,
        records: tuple[CitationRecord, ...],
        metrics: dict[str, str],
        source_path: str,
        full_rows: list[dict],
        plot_weighted: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._result = result
        self._records = records
        self._metrics = metrics
        self._source_path = source_path
        self._full_rows = full_rows
        self._plot_weighted = plot_weighted

    def run(self) -> None:
        try:
            save_beamplot_memory(
                self._result,
                self._records,
                self._metrics,
                source_path=self._source_path,
                full_rows=self._full_rows,
                plot_weighted=self._plot_weighted,
            )
        except Exception as exc:
            self.failed.emit(str(exc))


def _beamplot_theme_colors(is_dark: bool) -> dict[str, str]:
    text = "#e8e8e8" if is_dark else "#1a1a1a"
    bg_card = "#2a2a2a" if is_dark else "#ffffff"
    grid = "#363636" if is_dark else "#f0f0f0"
    mark_alpha = 0.8
    return {
        "plot_bg": bg_card,
        "paper_bg": bg_card,
        "text": text,
        "grid": grid,
        "hint_bg": "rgba(255,255,255,0.16)" if is_dark else "rgba(0,0,0,0.70)",
        "hint_text": text if is_dark else "#ffffff",
        "beam": text,
        "diamond": "#1f77b4",
        "median_marker": text,
        "publication": "#ff2d55",
        "mark_alpha": mark_alpha,
        "beam_alpha": 0.6,
    }


def _beamplot_static_theme_colors(is_dark: bool) -> dict[str, str]:
    colors = _beamplot_theme_colors(is_dark)
    return {
        "bg": colors["paper_bg"],
        "text": colors["text"],
        "grid": colors["grid"],
        "beam": colors["beam"],
        "diamond": colors["diamond"],
        "median_marker": colors["median_marker"],
        "publication": colors["publication"],
        "mark_alpha": colors["mark_alpha"],
        "beam_alpha": colors["beam_alpha"],
    }


class MainWindow(FluentWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Beamplots")
        self.setMinimumSize(1400, 900)
        _fit_window_to_screen(self, 1400, 900, 1180, 800)
        self.theme = ThemeManager.instance()
        try:
            self.setMicaEffectEnabled(False)
        except Exception:
            pass
        try:
            self.setCustomBackgroundColor(QColor("#f3f3f3"), QColor("#1c1c1c"))
        except Exception:
            pass
        self._refresh_window_icon()
        self.theme.theme_changed.connect(self._refresh_window_icon)

        self.home_view = BeamplotView(self)
        self.history_view = HistoryView(self)
        self.publications_view = PublicationsView(self)
        self.settings_view = SettingsView(self)
        self.home_view.setObjectName("beamplotsView")
        self.history_view.setObjectName("historyView")
        self.publications_view.setObjectName("publicationsView")
        self.settings_view.setObjectName("settingsView")

        self.addSubInterface(self.home_view, FluentIcon.HOME, "Beamplots")
        self.addSubInterface(self.publications_view, FluentIcon.APPLICATION, "Publications")
        self.addSubInterface(self.history_view, FluentIcon.HISTORY, "History")
        self.navigationInterface.addSeparator(NavigationItemPosition.BOTTOM)
        self.addSubInterface(
            self.settings_view,
            FluentIcon.SETTING,
            "Settings",
            position=NavigationItemPosition.BOTTOM,
        )

        self.navigationInterface.addItem(
            routeKey="aboutAction",
            icon=FluentIcon.INFO,
            text="About",
            onClick=self._show_about_dialog,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        self.navigationInterface.setReturnButtonVisible(False)
        self.home_view.publications_ready.connect(self.publications_view.set_records)
        self.publications_view.records_changed.connect(self.home_view.on_publications_changed)
        self.home_view.history_saved.connect(self.history_view.refresh)
        self.settings_view.llm_settings_changed.connect(self._refresh_model_selectors)
        self.stackedWidget.currentChanged.connect(self._on_page_switched)

    def _on_page_switched(self, index: int) -> None:
        widget = self.stackedWidget.widget(index)
        if widget is self.home_view and self.home_view._publications_dirty:
            if self.home_view._current_result is not None:
                self.home_view._run_analysis(show_success=False)
                self.home_view._show_data_refreshed_tip()

    def _refresh_model_selectors(self) -> None:
        self.home_view.chat_bar._model_selector.refresh_models()
        self.home_view._welcome_chat_bar._model_selector.refresh_models()

    def _show_about_dialog(self) -> None:
        from beamplot.gui.about_view import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec_()

    def _refresh_window_icon(self) -> None:
        candidates = (
            ["IES dark.ico", "IES dark.png", "IES.ico", "IES.png"]
            if self.theme.is_dark
            else ["IES.ico", "IES.png", "IES dark.ico", "IES dark.png"]
        )
        for name in candidates:
            path = ICON_DIR / name
            if path.exists():
                self.setWindowIcon(QIcon(str(path)))
                return


class WoSUploadFrame(QFrame):
    """Upload area that supports click-to-select and drag-and-drop."""

    files_dropped = pyqtSignal(list)
    activated = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def register_drop_targets(self) -> None:
        for widget in self.findChildren(QWidget):
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.activated.emit()
        super().mousePressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.DragEnter:
            self._handle_drag_enter(event)
            return True
        if event.type() == QEvent.DragMove:
            self._handle_drag_move(event)
            return True
        if event.type() == QEvent.Drop:
            self._handle_drop(event)
            return True
        return super().eventFilter(obj, event)

    def dragEnterEvent(self, event) -> None:
        self._handle_drag_enter(event)

    def dragMoveEvent(self, event) -> None:
        self._handle_drag_move(event)

    def dropEvent(self, event) -> None:
        self._handle_drop(event)

    @staticmethod
    def _accept_file_drag(event) -> bool:
        if not event.mimeData().hasUrls():
            return False
        return any(
            url.isLocalFile()
            and (Path(url.toLocalFile()).is_file() or Path(url.toLocalFile()).is_dir())
            for url in event.mimeData().urls()
        )

    def _handle_drag_enter(self, event) -> None:
        if self._accept_file_drag(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _handle_drag_move(self, event) -> None:
        if self._accept_file_drag(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _handle_drop(self, event) -> None:
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        paths: list[str] = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if not path:
                continue
            p = Path(path)
            if p.is_file() or p.is_dir():
                paths.append(path)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        event.ignore()


class BeamplotView(QWidget):
    publications_ready = pyqtSignal(object)
    history_saved = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = ThemeManager.instance()
        self.i18n = I18n.instance()
        self.file_edit = LineEdit(self)
        self.file_edit.setPlaceholderText("Select WoS file")
        self.weight_checkbox = QCheckBox("Age weighted", self)
        self.weight_checkbox.setObjectName("weightedCheckBox")
        self.run_button = QPushButton("Beamplots Viz.", self)
        self.run_button.setObjectName("runButton")
        self.run_button.setCursor(Qt.PointingHandCursor)
        self.upload_file_button = PushButton("Upload File", self)
        self.upload_file_button.setObjectName("uploadButton")
        self.save_button = QPushButton("Save", self)
        self.save_button.setObjectName("exportButton")
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.canvas = BeamplotCanvas(self)
        self._current_result: BeamplotResult | None = None
        self._stats_result: BeamplotResult | None = None
        self._current_records: tuple[CitationRecord, ...] = ()
        self._current_full_rows: list[dict] = []
        self._publications_dirty = False
        self._qa_records: list[dict[str, str]] = []
        self._beamplot_text = ""
        self._ai_text = ""
        self._interaction_context = ""
        self._is_interactive = True
        self._pending_prompt = ""
        self._pending_context = ""
        self._pending_interaction_summary = ""
        self._current_ai_bubble = None
        self._data_loaded = False
        self._loaded_file_name = ""
        self._source_paths: list[str] = []
        self._memory_worker: MemorySaveWorker | None = None

        self._setup_layout()
        self._connect_signals()
        self._apply_language()
        self._apply_theme()
        self.theme.theme_changed.connect(self._apply_theme)
        self.i18n.language_changed.connect(self._apply_language)

    def _setup_layout(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 16, 16)
        root.setSpacing(12)

        sidebar = QFrame(self)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(340)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 14, 16, 14)
        side.setSpacing(8)

        self.logo = QLabel(self)
        self.logo.setObjectName("logoImage")
        self.logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        side.addWidget(self.logo)

        self._data_title = QLabel("Data", self)
        self._data_title.setObjectName("sectionTitle")
        side.addWidget(self._data_title)

        self.file_edit.setVisible(False)
        self.upload_frame = WoSUploadFrame(self)
        self.upload_frame.setObjectName("uploadFrame")
        self.upload_frame.setCursor(Qt.PointingHandCursor)
        self.upload_frame.setFixedHeight(112)
        upload_layout = QVBoxLayout(self.upload_frame)
        upload_layout.setContentsMargins(14, 14, 14, 10)
        upload_layout.setSpacing(6)
        self.upload_hint = QLabel("Click to upload WoS file", self)
        self.upload_hint.setObjectName("uploadHint")
        self.upload_hint.setAlignment(Qt.AlignCenter)
        self.upload_sub_hint = QLabel("or drag file here", self)
        self.upload_sub_hint.setObjectName("uploadHint")
        self.upload_sub_hint.setAlignment(Qt.AlignCenter)
        upload_layout.addWidget(self.upload_hint)
        upload_layout.addWidget(self.upload_sub_hint)
        upload_button_row = QHBoxLayout()
        upload_button_row.addStretch(1)
        self.demo_button = PushButton("Demo", self)
        self.demo_button.setObjectName("demoButton")
        self.demo_button.setFixedSize(72, 30)
        upload_button_row.addWidget(self.demo_button)
        self.upload_file_button.setFixedSize(108, 30)
        upload_button_row.addWidget(self.upload_file_button)
        upload_layout.addLayout(upload_button_row)
        self.upload_frame.register_drop_targets()
        side.addWidget(self.upload_frame)

        self._settings_title = QLabel("Settings", self)
        self._settings_title.setObjectName("sectionTitle")
        side.addWidget(self._settings_title)

        options_frame = QFrame(self)
        options_frame.setObjectName("optionsFrame")
        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(12, 8, 12, 8)
        options_layout.setSpacing(10)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self._mode_label = QLabel("Mode", self)
        self._mode_label.setObjectName("modeLabel")
        mode_row.addWidget(self._mode_label)
        mode_row.addStretch(1)

        self._mode_frame = QFrame(self)
        self._mode_frame.setObjectName("modeCapsule")
        self._mode_frame.setFixedHeight(32)
        mf = QHBoxLayout(self._mode_frame)
        mf.setContentsMargins(3, 3, 3, 3)
        mf.setSpacing(0)
        self._interactive_btn = QPushButton("Interactive", self)
        self._interactive_btn.setObjectName("modeCapsuleBtn")
        self._interactive_btn.setCheckable(True)
        self._interactive_btn.setChecked(True)
        self._interactive_btn.setCursor(Qt.PointingHandCursor)
        self._interactive_btn.setFixedHeight(26)
        self._interactive_btn.setMinimumWidth(90)
        self._static_btn = QPushButton("Static", self)
        self._static_btn.setObjectName("modeCapsuleBtn")
        self._static_btn.setCheckable(True)
        self._static_btn.setChecked(False)
        self._static_btn.setCursor(Qt.PointingHandCursor)
        self._static_btn.setFixedHeight(26)
        self._static_btn.setMinimumWidth(72)
        mf.addWidget(self._interactive_btn)
        mf.addWidget(self._static_btn)
        mode_row.addWidget(self._mode_frame)
        options_layout.addLayout(mode_row)

        viz_row = QHBoxLayout()
        viz_row.setContentsMargins(0, 3, 0, 0)
        self.weight_checkbox.setMinimumWidth(120)
        self.run_button.setFixedHeight(30)
        viz_row.addWidget(self.weight_checkbox)
        viz_row.addStretch(1)
        viz_row.addWidget(self.run_button)
        options_layout.addLayout(viz_row)

        side.addWidget(options_frame)
        side.addSpacing(8)

        metrics_title_row = QHBoxLayout()
        metrics_title_row.setContentsMargins(0, 0, 0, 0)
        self._metrics_title = QLabel("Metrics", self)
        self._metrics_title.setObjectName("metricsTitle")
        metrics_title_row.addWidget(self._metrics_title)
        metrics_title_row.addStretch(1)
        self._metrics_info_btn = QPushButton("i", self)
        self._metrics_info_btn.setObjectName("metricsInfoBtn")
        self._metrics_info_btn.setFixedSize(22, 22)
        self._metrics_info_btn.setCursor(Qt.PointingHandCursor)
        metrics_title_row.addWidget(self._metrics_info_btn)
        side.addLayout(metrics_title_row)
        metrics_grid = QGridLayout()
        metrics_grid.setContentsMargins(0, 0, 0, 0)
        metrics_grid.setSpacing(6)
        for col in range(3):
            metrics_grid.setColumnStretch(col, 1)
        self.metric_cards: dict[str, _MetricRow] = {}
        metric_color = self.theme.primary
        metric_defs = [
            ("tc", "Total Citation", metric_color),
            ("avg", "Average Citation", metric_color),
            ("h", "h-index", metric_color),
            ("g", "g-index", metric_color),
            ("i10", "i10-index", metric_color),
            ("hg", "hg-index", metric_color),
            ("pi", "π-index", metric_color),
            ("w", "w-index", metric_color),
            ("m", "m-index", metric_color),
        ]
        for idx, (key, label, color) in enumerate(metric_defs):
            card = _MetricRow("0", label, color, self)
            self.metric_cards[key] = card
            metrics_grid.addWidget(card, idx // 3, idx % 3)
        side.addLayout(metrics_grid)

        side.addSpacing(4)
        self._legend_title = QLabel("Legend", self)
        self._legend_title.setObjectName("metricsTitle")
        side.addWidget(self._legend_title)
        self._legend_frame = QFrame(self)
        self._legend_frame.setObjectName("legendFrame")
        legend_layout = QVBoxLayout(self._legend_frame)
        legend_layout.setContentsMargins(12, 10, 12, 10)
        legend_layout.setSpacing(8)
        self._legend_items: list[tuple[QLabel, QLabel]] = []
        legend_defs = [
            ("◆", "#1f77b4", "Single paper citation count"),
            ("━", "#1a1a1a", "Citation range per year"),
            ("▲", "#1a1a1a", "Yearly citation median"),
            ("●", "#ff2d55", "Publication count per year"),
            ("┅", "#ff2d55", "Publication count median"),
        ]
        for symbol, color, desc in legend_defs:
            row = QWidget(self._legend_frame)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            icon_label = QLabel(symbol, row)
            icon_label.setFixedWidth(26)
            icon_label.setAlignment(Qt.AlignCenter)
            text_label = QLabel(desc, row)
            text_label.setObjectName("legendItem")
            row_layout.addWidget(icon_label)
            row_layout.addWidget(text_label, 1)
            legend_layout.addWidget(row)
            self._legend_items.append((icon_label, text_label))
        side.addWidget(self._legend_frame)
        side.addStretch(1)

        center_content = QVBoxLayout()
        center_content.setContentsMargins(0, 0, 0, 0)
        center_content.setSpacing(10)

        top = QHBoxLayout()
        self.ai_toggle = QPushButton(self)
        self.ai_toggle.setObjectName("aiToggleBtn")
        self.ai_toggle.setFixedSize(34, 34)
        self.ai_toggle.setCursor(Qt.PointingHandCursor)
        self.ai_toggle.setCheckable(True)
        self.ai_toggle.setChecked(False)
        self.ai_toggle.setToolTip("AI Panel")
        top.addWidget(self.ai_toggle)
        top.addStretch(1)

        self.interaction_hint = QLabel("Click a point or drag to select a region for AI analysis", self)
        self.interaction_hint.setObjectName("interactionHint")
        self.interaction_hint.setFixedWidth(700)
        self.interaction_hint.setAlignment(Qt.AlignCenter)
        self._hint_opacity = QGraphicsOpacityEffect(self.interaction_hint)
        self._hint_opacity.setOpacity(0.0)
        self.interaction_hint.setGraphicsEffect(self._hint_opacity)
        top.addWidget(self.interaction_hint)

        self._help_btn = QPushButton(self)
        self._help_btn.setObjectName("helpBtn")
        self._help_btn.setFixedSize(30, 30)
        self._help_btn.setCursor(Qt.PointingHandCursor)
        self._help_btn.setToolTip("Beamplot Description")
        top.addWidget(self._help_btn)

        self.save_button.setText("Export")
        self.save_button.setFixedSize(76, 30)
        top.addWidget(self.save_button)
        center_content.addLayout(top)

        plot_card = QFrame(self)
        plot_card.setObjectName("plotCard")
        plot_layout = QVBoxLayout(plot_card)
        plot_layout.setContentsMargins(12, 12, 12, 12)
        plot_layout.addWidget(self.canvas)

        center_content.addWidget(plot_card, 1)

        self._build_ai_window()

        root.addWidget(sidebar, 0)
        root.addLayout(center_content, 1)
        self.save_button.setEnabled(False)
        self.setObjectName("beamplotView")

    def _build_ai_window(self) -> None:
        """Build the AI Analysis floating window.

        This follows the V1 structure: the welcome page and chat page each own
        their input bar. The welcome bar only submits the first text; the chat
        bar owns the AI worker and subsequent conversation state.
        """
        from PyQt5.QtWidgets import QStackedWidget

        self.ai_window = QDialog(self, Qt.Window)
        self.ai_window.setWindowTitle("AI Analysis")
        self.ai_window.setMinimumSize(480, 480)
        _fit_window_to_screen(self.ai_window, 800, 640, 480, 480, screen_ratio=0.86)
        self.ai_window.rejected.connect(self._on_ai_window_closed)

        root = QVBoxLayout(self.ai_window)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._ai_stack = QStackedWidget(self.ai_window)

        # ── Page 0: Welcome — centered logo + first input ──
        welcome_page = QWidget()
        welcome_outer = QVBoxLayout(welcome_page)
        welcome_outer.setContentsMargins(0, 0, 0, 0)
        welcome_outer.setSpacing(0)
        welcome_outer.addStretch(3)

        self._ai_logo = QLabel(welcome_page)
        self._ai_logo.setAlignment(Qt.AlignCenter)
        self._update_ai_logo()
        welcome_outer.addWidget(self._ai_logo, 0, Qt.AlignHCenter)
        welcome_outer.addSpacing(24)

        self._welcome_chat_bar = BeamplotChatBar(welcome_page)
        self._welcome_chat_bar.setFixedWidth(520)
        self._welcome_chat_bar.set_external_submit(True)
        welcome_outer.addWidget(self._welcome_chat_bar, 0, Qt.AlignHCenter)
        welcome_outer.addStretch(4)

        self._ai_stack.addWidget(welcome_page)

        # ── Page 1: Chat — messages + bottom input ──
        chat_page = QWidget()
        chat_layout_v = QVBoxLayout(chat_page)
        chat_layout_v.setContentsMargins(0, 0, 0, 0)
        chat_layout_v.setSpacing(0)

        self._chat_scroll = ScrollArea(chat_page)
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._chat_scroll.setObjectName("chatScroll")
        self._chat_container = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(20, 12, 20, 12)
        self._chat_layout.setSpacing(10)
        self._chat_layout.setAlignment(Qt.AlignTop)
        self._chat_scroll.setWidget(self._chat_container)
        chat_layout_v.addWidget(self._chat_scroll, 1)

        self.chat_bar = BeamplotChatBar(chat_page)
        chat_bar_wrap = QHBoxLayout()
        chat_bar_wrap.setContentsMargins(16, 4, 16, 12)
        chat_bar_wrap.addWidget(self.chat_bar)
        chat_layout_v.addLayout(chat_bar_wrap)

        self._ai_stack.addWidget(chat_page)
        self._ai_stack.setCurrentIndex(0)
        root.addWidget(self._ai_stack, 1)

        self._chat_messages: list[dict] = []
        self._ai_has_messages = False
        self._chat_session_id = 0
        self._active_session_id = 0
        self._suppress_new_chat_click = False

    def _connect_signals(self) -> None:
        self.demo_button.clicked.connect(self._use_default_data)
        self.upload_file_button.clicked.connect(self._select_files)
        self.upload_frame.activated.connect(self._select_files)
        self.upload_frame.files_dropped.connect(self._load_wos_sources)
        self.run_button.clicked.connect(lambda: self._run_analysis(show_success=True))
        self.save_button.clicked.connect(self._save_plot)
        self.ai_toggle.clicked.connect(self._on_ai_panel_clicked)
        self._static_btn.clicked.connect(lambda: self._on_mode_capsule("static"))
        self._interactive_btn.clicked.connect(lambda: self._on_mode_capsule("interactive"))
        self.canvas.point_clicked.connect(self._on_point_clicked)
        self.canvas.region_selected.connect(self._on_region_selected)
        self.canvas.publication_hovered.connect(self._on_publication_hovered)
        self.canvas.reset_requested.connect(lambda: self._run_analysis(show_success=False))
        self.chat_bar.response_ready.connect(self._on_ai_stream_chunk)
        self.chat_bar.user_message_sent.connect(self._on_user_message)
        self.chat_bar.exchange_finished.connect(self._record_qa)
        self.chat_bar._new_chat_btn.clicked.connect(self._on_new_chat)
        self._bind_welcome_submit_handlers()
        self._welcome_chat_bar._new_chat_btn.clicked.connect(self._on_new_chat)
        self._help_btn.clicked.connect(self._show_help)
        self._metrics_info_btn.clicked.connect(self._show_metrics_info)

    def _bind_welcome_submit_handlers(self) -> None:
        """Route welcome-page submit directly through BeamplotView's first-message flow."""
        for signal in (self._welcome_chat_bar._input.returnPressed, self._welcome_chat_bar._send_btn.clicked):
            try:
                signal.disconnect()
            except TypeError:
                pass
        self._welcome_chat_bar._input.returnPressed.connect(self._submit_welcome_input)
        self._welcome_chat_bar._send_btn.clicked.connect(self._submit_welcome_input)

    def _submit_welcome_input(self) -> None:
        text = self._welcome_chat_bar._input.text().strip()
        if not text:
            return
        self._welcome_chat_bar._input.clear()
        self._on_welcome_user_message(text)

    def on_publications_changed(self, rows: object) -> None:
        self._current_full_rows = list(rows or [])
        self._publications_dirty = True

    def _on_mode_capsule(self, mode: str) -> None:
        self._is_interactive = (mode == "interactive")
        self._static_btn.setChecked(mode == "static")
        self._interactive_btn.setChecked(mode == "interactive")
        self._update_capsule_styles()
        self.canvas.set_mode(mode)
        if mode != "interactive":
            self._hint_opacity.setOpacity(0.0)

    def _show_interaction_hint(self) -> None:
        self._hint_opacity.setOpacity(1.0)
        QTimer.singleShot(2000, lambda: self._hint_opacity.setOpacity(0.0))

    def _on_new_chat(self) -> None:
        """Save current chat, reset state, switch back to the welcome page."""
        if self._suppress_new_chat_click:
            return
        self.chat_bar.reset_for_new_chat()
        self._welcome_chat_bar.reset_for_new_chat()
        self._archive_current_chat_if_needed()
        self._chat_session_id += 1
        self._chat_messages.clear()
        self._qa_records.clear()
        self._ai_text = ""
        self._pending_stream_text = None
        self._stream_timer_active = False
        self._clear_chat_display()
        self._current_ai_bubble = None
        self._ai_has_messages = False
        self._active_session_id = self._chat_session_id
        self._welcome_chat_bar.set_external_submit(True)
        self._bind_welcome_submit_handlers()
        self._ai_stack.setCurrentIndex(0)
        self._welcome_chat_bar._input.setFocus()

    def _clear_chat_display(self) -> None:
        """Remove all rendered chat bubbles from the floating AI window."""
        while self._chat_layout.count():
            item = self._chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _archive_current_chat_if_needed(self) -> None:
        if self._current_result is None or not self._qa_records:
            return
        suffix = ".png" if not self._is_interactive else ".html"
        tmp_path = Path(tempfile.gettempdir()) / f"beamplot_current_history{suffix}"
        try:
            self.canvas.save_figure(str(tmp_path))
        except Exception:
            tmp_path = None
        add_history_record(
            title=Path(self.file_edit.text()).name or "Beamplot Result",
            result=self._current_result,
            stats_result=self._stats_result,
            plot_weighted=bool(self._current_result and self._current_result.weighted),
            image_path=tmp_path if tmp_path and tmp_path.exists() else None,
            qa=list(self._qa_records),
            beamplot_text=self._beamplot_text,
            ai_text=self._ai_text,
            source_path=self.file_edit.text().strip(),
        )
        self.history_saved.emit()

    def _switch_to_chat_page(self) -> None:
        """Switch from the welcome page to the chat messages page."""
        self._ai_has_messages = True
        self._ai_stack.setCurrentIndex(1)

    def _on_user_message(self, text: str) -> None:
        """Handle user-typed messages: switch to chat view, show bubble, prepare AI bubble."""
        self._active_session_id = self._chat_session_id
        self._switch_to_chat_page()
        self._add_chat_bubble(text, "user")
        self._current_ai_bubble = self._add_chat_bubble("...", "assistant")
        self._chat_messages.append({"role": "user", "content": text})

    def _on_welcome_user_message(self, text: str) -> None:
        """Handle the first message submitted from the welcome page."""
        self._suppress_new_chat_click = True
        QTimer.singleShot(250, self._release_new_chat_guard)
        self._active_session_id = self._chat_session_id
        self._switch_to_chat_page()
        self.chat_bar.set_context(self._welcome_chat_bar._context)
        self._add_chat_bubble(text, "user")
        self._current_ai_bubble = self._add_chat_bubble("...", "assistant")
        self._chat_messages.append({"role": "user", "content": text})
        QTimer.singleShot(0, lambda t=text, sid=self._chat_session_id: self._start_welcome_autosend(t, sid))

    def _release_new_chat_guard(self) -> None:
        self._suppress_new_chat_click = False

    def _start_welcome_autosend(self, text: str, session_id: int) -> None:
        if session_id != self._chat_session_id:
            return
        self.chat_bar.auto_send(text)

    def _make_avatar(self, role: str) -> QLabel:
        """Create a circular avatar label for user or assistant."""
        avatar = QLabel()
        avatar.setFixedSize(28, 28)
        avatar_name = "avatar_user.svg" if role == "user" else "avatar_assistant.svg"
        icon = svg_icon(avatar_name, self.theme.primary)
        pixmap = icon.pixmap(QSize(24, 24))
        avatar.setPixmap(pixmap)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                border-radius: 14px;
                padding: 2px;
            }}
        """)
        return avatar

    def _add_chat_bubble(self, text: str, role: str = "assistant") -> QLabel:
        """Add a styled chat bubble with avatar to the conversation area."""
        from PyQt5.QtGui import QFont, QFontMetrics
        from PyQt5.QtWidgets import QSizePolicy
        tm = self.theme
        bubble = QLabel(self)
        bubble.setWordWrap(True)
        bubble.setTextFormat(Qt.RichText)
        bubble.setOpenExternalLinks(True)
        bubble.setTextInteractionFlags(Qt.TextBrowserInteraction)
        bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        if role == "user":
            bg = tm.primary if not tm.is_dark else "#2563eb"
            text_color = "#ffffff"
            bubble.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    color: {text_color};
                    border-radius: 12px;
                    padding: 8px 14px;
                    font-size: 14px;
                    font-family: "{tm.font_family}";
                }}
            """)
        else:
            bg = tm.bg_surface if tm.is_dark else "#f9f9f9"
            text_color = tm.text_primary
            bubble.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg};
                    color: {text_color};
                    border-radius: 12px;
                    padding: 6px 14px;
                    font-size: 14px;
                    font-family: "{tm.font_family}";
                }}
            """)
            bubble.setMaximumWidth(max(420, self._chat_scroll.viewport().width() - 96))

        html = self._markdown_to_html(text) if role == "assistant" else html_lib.escape(text).replace("\n", "<br>")
        bubble.setText(html)
        if role == "user":
            font = QFont(tm.font_family)
            font.setPixelSize(14)
            fm = QFontMetrics(font)
            lines = str(text or "").splitlines() or [""]
            content_w = max(fm.horizontalAdvance(line) for line in lines)
            padding = 32
            w = max(72, min(420, content_w + padding))
            bubble.setFixedWidth(w)
            text_width = w - 28
            bound = fm.boundingRect(0, 0, text_width, 10000, Qt.TextWordWrap, text)
            bubble.setMinimumHeight(bound.height() + 20)

        avatar = self._make_avatar(role)

        icon_color = tm.text_secondary
        btn_ss = (
            "QPushButton { background: transparent; border: none;"
            " padding: 2px; border-radius: 4px; }"
            f"QPushButton:hover {{ background-color: {tm.bg_hover}; }}"
        )

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        col.addWidget(bubble)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        if role == "assistant":
            action_row.setContentsMargins(4, 0, 0, 0)

            copy_btn = QPushButton(self)
            copy_btn.setIcon(svg_icon("copy.svg", icon_color))
            copy_btn.setIconSize(QSize(14, 14))
            copy_btn.setFixedSize(22, 22)
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.setToolTip("Copy")
            copy_btn.setStyleSheet(btn_ss)
            copy_btn.clicked.connect(lambda _, b=bubble: self._copy_bubble_text(b))
            action_row.addWidget(copy_btn)

            retry_btn = QPushButton(self)
            retry_btn.setIcon(svg_icon("refresh.svg", icon_color))
            retry_btn.setIconSize(QSize(14, 14))
            retry_btn.setFixedSize(22, 22)
            retry_btn.setCursor(Qt.PointingHandCursor)
            retry_btn.setToolTip("Retry")
            retry_btn.setStyleSheet(btn_ss)
            retry_btn.clicked.connect(self._retry_last_message)
            action_row.addWidget(retry_btn)

            action_row.addStretch(1)
        else:
            action_row.setContentsMargins(0, 0, 4, 0)
            action_row.addStretch(1)

            edit_btn = QPushButton(self)
            edit_btn.setIcon(svg_icon("edit.svg", icon_color))
            edit_btn.setIconSize(QSize(14, 14))
            edit_btn.setFixedSize(22, 22)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setToolTip("Edit")
            edit_btn.setStyleSheet(btn_ss)
            raw_text = text
            edit_btn.clicked.connect(lambda _, t=raw_text: self._edit_user_message(t))
            action_row.addWidget(edit_btn)

            copy_btn = QPushButton(self)
            copy_btn.setIcon(svg_icon("copy.svg", icon_color))
            copy_btn.setIconSize(QSize(14, 14))
            copy_btn.setFixedSize(22, 22)
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.setToolTip("Copy")
            copy_btn.setStyleSheet(btn_ss)
            copy_btn.clicked.connect(lambda _, t=raw_text: QApplication.clipboard().setText(t))
            action_row.addWidget(copy_btn)

        col.addLayout(action_row)

        bubble_wrapper = QWidget()
        bubble_wrapper.setLayout(col)
        bubble_wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        row = QHBoxLayout()
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(6)

        if role == "user":
            row.addStretch(1)
            row.addWidget(bubble_wrapper, 0, Qt.AlignTop)
            row.addWidget(avatar, 0, Qt.AlignTop)
        else:
            row.addWidget(avatar, 0, Qt.AlignTop)
            row.addWidget(bubble_wrapper, 1)
            row.addStretch(0)

        container = QWidget()
        container.setLayout(row)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._chat_layout.addWidget(container)

        QTimer.singleShot(50, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))
        return bubble

    def _copy_bubble_text(self, bubble: QLabel) -> None:
        plain = bubble.text()
        try:
            import re
            plain = re.sub(r"<[^>]+>", "", plain)
            plain = html_lib.unescape(plain)
        except Exception:
            pass
        QApplication.clipboard().setText(plain)
        InfoBar.success(
            title="", content="Copied",
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP_RIGHT, duration=1500,
            parent=self.window(),
        )

    def _retry_last_message(self) -> None:
        if not self._chat_messages:
            return
        last_user_msg = ""
        for msg in reversed(self._chat_messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break
        if not last_user_msg:
            return
        if self._conversation_history_has_answer():
            self._chat_messages = self._chat_messages[:-1]
            if self._chat_messages and self._chat_messages[-1]["role"] == "assistant":
                self._chat_messages = self._chat_messages[:-1]
        self._current_ai_bubble = self._add_chat_bubble("...", "assistant")
        self.chat_bar.auto_send(last_user_msg)

    def _conversation_history_has_answer(self) -> bool:
        return bool(self._chat_messages) and self._chat_messages[-1]["role"] == "assistant"

    def _edit_user_message(self, original_text: str) -> None:
        self.chat_bar._input.setText(original_text)
        self.chat_bar._input.setFocus()
        self.chat_bar._input.selectAll()

    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown text to HTML for rendering in bubbles."""
        tm = self.theme
        try:
            import markdown
            html = markdown.markdown(text, extensions=["tables", "fenced_code", "nl2br"])
        except ImportError:
            html = text.replace("\n", "<br>")
        html = html.replace("<p>", "<div>").replace("</p>", "</div>")
        code_bg = "#1e1e1e" if tm.is_dark else "#f6f8fa"
        code_text = "#d4d4d4" if tm.is_dark else "#24292e"
        th_bg = "#3a3a3a" if tm.is_dark else "#f1f5f5"
        td_bg = "transparent" if tm.is_dark else "#f8f8f8"
        border_color = "#555" if tm.is_dark else "#d9d9d9"
        global_style = (
            "<style>"
            f"body{{font-family:'{tm.font_family}';font-size:14px;line-height:1.5;margin:0;padding:0;}}"
            "div{margin:0;padding:0;}"
            "ul,ol{margin:2px 0;padding-left:20px;}"
            "li{margin:2px 0;}"
            f"code{{background:{code_bg};color:{code_text};padding:1px 4px;border-radius:3px;font-size:13px;}}"
            f"pre{{background:{code_bg};color:{code_text};padding:8px 10px;border-radius:6px;"
            f"overflow-x:auto;font-size:13px;margin:4px 0;}}"
            "pre code{background:transparent;padding:0;}"
            f"table{{border-collapse:collapse;width:100%;margin:4px 0;font-size:13px;}}"
            f"th,td{{border:1px solid {border_color};padding:5px 8px;text-align:left;vertical-align:top;}}"
            f"th{{background:{th_bg};font-weight:600;}}"
            f"td{{background:{td_bg};}}"
            "h1,h2,h3,h4{margin:6px 0 3px 0;}"
            "blockquote{margin:4px 0;padding-left:10px;border-left:3px solid #ccc;color:#888;}"
            "</style>"
        )
        return global_style + html

    def _on_ai_stream_chunk(self, text: str) -> None:
        """Handle streaming AI response and update the latest assistant bubble."""
        if not self._ai_has_messages:
            return
        if text.startswith("User: ") and "\n\nAssistant: " in text:
            parts = text.split("\n\nAssistant: ", 1)
            assistant_text = parts[1] if len(parts) > 1 else ""
        else:
            assistant_text = text

        if self._current_ai_bubble is None:
            return
        self._pending_stream_text = assistant_text
        if not getattr(self, '_stream_timer_active', False):
            self._stream_timer_active = True
            QTimer.singleShot(60, self._flush_stream_text)

    def _flush_stream_text(self) -> None:
        """Throttled flush of streamed text to the bubble."""
        self._stream_timer_active = False
        if getattr(self, '_active_session_id', -1) != self._chat_session_id:
            return
        text = getattr(self, '_pending_stream_text', None)
        if text is None or self._current_ai_bubble is None:
            return
        plain_html = html_lib.escape(text).replace("\n", "<br>")
        self._current_ai_bubble.setText(plain_html)
        self._current_ai_bubble.adjustSize()
        self._chat_layout.invalidate()
        self._chat_container.adjustSize()
        sb = self._chat_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_ai_panel_clicked(self) -> None:
        if self._pending_prompt and self.ai_window.isVisible():
            self.ai_toggle.setChecked(True)
            self._send_pending_interaction()
            return
        self._toggle_ai_panel()

    def _toggle_ai_panel(self) -> None:
        visible = self.ai_toggle.isChecked()
        if visible:
            self._apply_ai_window_theme()
            _fit_window_to_screen(self.ai_window, 800, 640, 480, 480, screen_ratio=0.86)
            self.ai_window.show()
            self.ai_window.raise_()
            self.ai_window.activateWindow()
            ctx = self._build_current_ai_context()
            self.chat_bar.set_context(ctx)
            self._welcome_chat_bar.set_context(ctx)
            if self._pending_prompt:
                self._send_pending_interaction()
        else:
            self.ai_window.hide()
        self._update_ai_toggle_style()

    def _on_ai_window_closed(self) -> None:
        self.ai_toggle.setChecked(False)
        self._update_ai_toggle_style()

    def _update_ai_toggle_style(self) -> None:
        tm = self.theme
        if self.ai_toggle.isChecked():
            self.ai_toggle.setIcon(svg_icon("robot.svg", "#ffffff"))
            self.ai_toggle.setIconSize(QSize(20, 20))
            self.ai_toggle.setStyleSheet(f"""
                QPushButton#aiToggleBtn {{
                    background-color: {tm.primary};
                    border: none;
                    border-radius: 8px;
                    padding: 4px;
                }}
                QPushButton#aiToggleBtn:hover {{
                    background-color: {tm.primary_hover};
                }}
            """)
        else:
            self.ai_toggle.setIcon(svg_icon("robot.svg", tm.text_secondary))
            self.ai_toggle.setIconSize(QSize(20, 20))
            self.ai_toggle.setStyleSheet(f"""
                QPushButton#aiToggleBtn {{
                    background-color: transparent;
                    border: 1px solid {tm.border_light};
                    border-radius: 8px;
                    padding: 4px;
                }}
                QPushButton#aiToggleBtn:hover {{
                    background-color: {tm.bg_hover};
                }}
            """)

    def _show_help(self) -> None:
        dlg = QDialog(self)
        t = self.i18n.t
        dlg.setWindowTitle(t("beamplot_help_title"))
        dlg.setFixedSize(520, 380)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 24, 24, 24)
        tm = self.theme

        content = QFrame(dlg)
        content.setObjectName("helpContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(0)

        lbl = QLabel(self._build_help_html(), content)
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f'color: {tm.text_primary}; font-size: 13px; line-height: 1.6; '
            f'font-family: "{tm.font_family}"; background: transparent;'
        )
        content_layout.addWidget(lbl)
        layout.addWidget(content, 1)
        dlg.setStyleSheet(
            f"""
            QDialog {{
                background-color: {tm.bg_page};
                border-radius: 12px;
                font-family: "{tm.font_family}";
            }}
            QFrame#helpContent {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border_light};
                border-radius: 14px;
            }}
            """
        )
        dlg.exec_()

    def _show_metrics_info(self) -> None:
        dlg = MetricsGlossaryDialog(self)
        dlg.exec_()

    def _build_help_html(self) -> str:
        colors = _beamplot_theme_colors(self.theme.is_dark)
        text = self.theme.text_primary
        muted = self.theme.text_secondary
        if self.i18n.is_chinese:
            intro = (
                "Beamplot 图中下方的 x 轴表示论文的被引次数，"
                "y 轴按发表年份分布论文。各类标记颜色会跟随当前主题，"
                "并与图表中的颜色保持一致："
            )
            items = [
                ("◆", colors["diamond"], "单篇论文的引用次数点"),
                ("━", colors["beam"], "某一年论文引用次数范围"),
                ("▲", colors["median_marker"], "某一年引用次数中位数"),
                ("●", colors["publication"], "某一年发文量"),
                ("┅", colors["publication"], "每年发文量中位数参考线"),
            ]
            tail = (
                "另一条与范围线同色的虚线表示所有年份的引用次数中位数。"
                "上方 x 轴显示每年的论文数量。"
            )
        else:
            intro = (
                "In a Beamplot, the bottom x-axis shows citation counts and the y-axis "
                "distributes publications by publication year. Marker colors follow the "
                "current theme and match the plot:"
            )
            items = [
                ("◆", colors["diamond"], "single-publication citation point"),
                ("━", colors["beam"], "citation range for one publication year"),
                ("▲", colors["median_marker"], "citation median for one publication year"),
                ("●", colors["publication"], "publication count for one year"),
                ("┅", colors["publication"], "yearly publication-count median reference line"),
            ]
            tail = (
                "The other dashed line, using the same color as the range line, marks "
                "the citation median across all years. The top x-axis shows the number "
                "of publications per year."
            )
        legend = "".join(
            f'<div style="margin:3px 0;"><span style="color:{color}; '
            f'font-weight:700; font-size:15px;">{symbol}</span>&nbsp;'
            f'<span style="color:{text};">{label}</span></div>'
            for symbol, color, label in items
        )
        return (
            f'<div style="color:{text}; font-size:13px; line-height:1.55; font-family:{self.theme.font_family};">'
            f'<p style="margin:0 0 8px 0;">{intro}</p>'
            f'<div style="margin:0 0 8px 0;">{legend}</div>'
            f'<p style="margin:14px 0 0 0; color:{muted}; line-height:1.55;">{tail}</p>'
            f'</div>'
        )

    def _apply_language(self) -> None:
        t = self.i18n.t
        self.file_edit.setPlaceholderText(t("beamplot_select_wos"))
        self.upload_file_button.setText(t("beamplot_upload"))
        self.upload_hint.setText(t("beamplot_upload_hint"))
        self.upload_sub_hint.setText(t("beamplot_upload_sub"))
        self.weight_checkbox.setText(t("beamplot_weighted"))
        self.run_button.setText("Beamplots Viz.")
        self.ai_toggle.setToolTip(t("beamplot_ai_panel"))
        self.save_button.setText(t("beamplot_export"))
        self._help_btn.setToolTip(t("beamplot_help_title"))
        self._data_title.setText(t("beamplot_data"))
        self._settings_title.setText(t("beamplot_settings"))
        self._mode_label.setText(t("beamplot_mode"))
        self._static_btn.setText(t("beamplot_static"))
        self._interactive_btn.setText(t("beamplot_interactive"))
        self._metrics_title.setText(t("beamplot_metrics"))
        self._legend_title.setText(t("beamplot_legend"))
        if self._data_loaded and self._loaded_file_name:
            self._set_loaded_file_label(self._loaded_file_name)
        self._apply_theme()

    def _apply_theme(self) -> None:
        tm = self.theme
        ff = tm.font_family
        secondary_text = tm.text_secondary
        check_svg = "check_light.svg" if tm.is_dark else "check_dark.svg"
        self._update_logo()
        self._update_help_icon()
        self._update_capsule_styles()
        self._update_demo_button_style()
        self._update_upload_button_style()
        self._update_ai_toggle_style()
        self.canvas.set_theme_colors(_beamplot_theme_colors(tm.is_dark))
        self.canvas.set_static_theme_colors(_beamplot_static_theme_colors(tm.is_dark))
        self.setStyleSheet(f"""
            QWidget#beamplotView {{
                background-color: {tm.bg_page};
                font-family: "{ff}";
            }}
            QFrame#sidebar {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border_light};
                border-radius: 12px;
                font-family: "{ff}";
            }}
            QLabel#metricsTitle, QLabel#sectionTitle {{
                color: {tm.text_primary};
                font-size: 16px;
                font-weight: 500;
                font-family: "{ff}";
                background: transparent;
            }}
            QLabel#aiTitle {{
                color: {tm.text_primary};
                font-size: 15px;
                font-weight: 600;
                font-family: "{ff}";
                background: transparent;
            }}
            QLabel#modeLabel {{
                color: {secondary_text};
                font-size: 13px;
                font-weight: 400;
                font-family: "{ff}";
                background: transparent;
            }}
            QCheckBox#weightedCheckBox {{
                color: {secondary_text};
                font-size: 13px;
                font-weight: 400;
                font-family: "{ff}";
                spacing: 6px;
            }}
            QCheckBox#weightedCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1.5px solid {secondary_text};
                border-radius: 3px;
                background-color: transparent;
            }}
            QCheckBox#weightedCheckBox::indicator:hover {{
                border-color: {tm.text_primary};
            }}
            QCheckBox#weightedCheckBox::indicator:checked {{
                image: url("{(ICON_DIR / check_svg).as_posix()}");
                border: 1.5px solid {secondary_text};
                background-color: transparent;
            }}
            QLabel#interactionHint {{
                color: {"#ffffff" if not tm.is_dark else tm.text_primary};
                background-color: {"rgba(0,0,0,0.70)" if not tm.is_dark else "rgba(255,255,255,0.16)"};
                border: none;
                border-radius: 14px;
                padding: 5px 12px;
                font-size: 12px;
                font-family: "{ff}";
            }}
            QFrame#uploadFrame {{
                background-color: {tm.bg_surface if tm.is_dark else '#fbfbfb'};
                border: 2px dashed {tm.border};
                border-radius: 10px;
            }}
            QFrame#optionsFrame {{
                background-color: {tm.bg_surface if tm.is_dark else '#f9f9f9'};
                border: 1px solid {tm.border_light};
                border-radius: 10px;
            }}
            QFrame#legendFrame {{
                background-color: {tm.bg_surface if tm.is_dark else '#f9f9f9'};
                border: 1px solid {tm.border_light};
                border-radius: 10px;
            }}
            QLabel#legendTitle {{
                color: {tm.text_primary};
                font-size: 13px;
                font-weight: 600;
                font-family: "{ff}";
                background: transparent;
            }}
            QLabel#legendItem {{
                color: {tm.text_secondary};
                font-family: "{ff}";
                background: transparent;
            }}
            QLabel#uploadHint {{
                color: {tm.primary};
                font-size: 12px;
                font-family: "{ff}";
                background: transparent;
                border: none;
            }}
            QFrame#plotCard {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border_light};
                border-radius: 8px;
            }}
            QPushButton#runButton, QPushButton#exportButton {{
                background-color: {tm.primary};
                color: white;
                border: 1px solid {tm.primary};
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                font-family: "{ff}";
                padding: 4px 14px;
            }}
            QPushButton#runButton:hover, QPushButton#exportButton:hover {{
                background-color: {tm.primary_hover};
                border-color: {tm.primary_hover};
            }}
            QPushButton#runButton:pressed, QPushButton#exportButton:pressed {{
                background-color: {tm.primary_light};
                border-color: {tm.primary_light};
            }}
            QPushButton#helpBtn {{
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 4px;
            }}
            QPushButton#helpBtn:hover {{
                background-color: {tm.bg_hover};
            }}
            QPushButton#metricsInfoBtn {{
                background-color: {tm.primary};
                color: #ffffff;
                border: none;
                border-radius: 11px;
                font-size: 13px;
                font-weight: 700;
                font-family: "Georgia", "Times New Roman", serif;
                font-style: italic;
                padding: 0;
            }}
            QPushButton#metricsInfoBtn:hover {{
                background-color: {tm.primary_hover};
            }}
        """)
        if hasattr(self, '_legend_items'):
            colors = _beamplot_theme_colors(tm.is_dark)
            t = self.i18n.t
            legend_data = [
                ("◆", colors["diamond"], t("beamplot_legend_single")),
                ("━", colors["beam"], t("beamplot_legend_range")),
                ("▲", colors["median_marker"], t("beamplot_legend_median")),
                ("●", colors["publication"], t("beamplot_legend_publication")),
                ("┅", colors["publication"], t("beamplot_legend_pub_median")),
            ]
            for (icon_label, text_label), (symbol, color, desc) in zip(self._legend_items, legend_data):
                icon_label.setText(symbol)
                icon_label.setStyleSheet(
                    f"color:{color}; font-weight:700; font-size:14px; "
                    f"font-family:'{tm.font_family}'; background: transparent;"
                )
                text_label.setText(desc)
                text_label.setStyleSheet(
                    f"color:{tm.text_secondary}; font-size:11px; "
                    f"font-family:'{tm.font_family}'; background: transparent;"
                )
        if hasattr(self, 'ai_window'):
            self._apply_ai_window_theme()

    def _apply_ai_window_theme(self) -> None:
        tm = self.theme
        ff = tm.font_family
        bg = "#ffffff" if not tm.is_dark else tm.bg_card
        self.ai_window.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                font-family: "{ff}";
            }}
            ScrollArea#chatScroll, QScrollArea#chatScroll {{
                background: {bg};
                border: none;
            }}
            ScrollArea#chatScroll > QWidget > QWidget, QScrollArea#chatScroll > QWidget > QWidget {{
                background: {bg};
            }}
        """)
        self._update_ai_logo()

    def _update_capsule_styles(self) -> None:
        tm = self.theme
        ff = tm.font_family
        for btn, active in [
            (self._interactive_btn, self._is_interactive),
            (self._static_btn, not self._is_interactive),
        ]:
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tm.primary_bg};
                        color: {tm.primary};
                        border: 1px solid {tm.primary_border};
                        border-radius: 13px;
                        padding: 0 14px;
                        font-size: 12px;
                        font-weight: 400;
                        font-family: "{ff}";
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {tm.text_secondary};
                        border: none;
                        border-radius: 13px;
                        padding: 0 14px;
                        font-size: 12px;
                        font-weight: 400;
                        font-family: "{ff}";
                    }}
                    QPushButton:hover {{
                        color: {tm.text_primary};
                        background-color: {tm.bg_hover};
                    }}
                """)
        self._mode_frame.setStyleSheet(f"""
            QFrame#modeCapsule {{
                background-color: {tm.bg_surface};
                border: 1px solid {tm.border_light};
                border-radius: 16px;
            }}
        """)

    def _update_demo_button_style(self) -> None:
        tm = self.theme
        ff = tm.font_family
        if tm.is_dark:
            demo_bg = tm.bg_surface
            demo_hover = tm.bg_hover
        else:
            demo_bg = "#ffffff"
            demo_hover = "#f5f5f5"
        self.demo_button.setStyleSheet(f"""
            PushButton#demoButton, QPushButton#demoButton {{
                background-color: {demo_bg};
                color: {tm.text_primary};
                border: 1px solid {tm.border_light};
                border-radius: 6px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: 400;
                font-family: "{ff}";
            }}
            PushButton#demoButton:hover, QPushButton#demoButton:hover {{
                background-color: {demo_hover};
                color: {tm.text_primary};
                border: 1px solid {tm.border};
            }}
            PushButton#demoButton:pressed, QPushButton#demoButton:pressed {{
                background-color: {demo_hover};
                color: {tm.text_primary};
                border: 1px solid {tm.border};
            }}
        """)

    def _update_upload_button_style(self) -> None:
        tm = self.theme
        ff = tm.font_family
        self.upload_file_button.setStyleSheet(f"""
            PushButton#uploadButton, QPushButton#uploadButton {{
                background-color: {tm.primary};
                color: #ffffff;
                border: 1px solid {tm.primary};
                border-radius: 6px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: 600;
                font-family: "{ff}";
            }}
            PushButton#uploadButton:hover, QPushButton#uploadButton:hover {{
                background-color: {tm.primary_hover};
                border: 1px solid {tm.primary_hover};
                color: #ffffff;
            }}
            PushButton#uploadButton:pressed, QPushButton#uploadButton:pressed {{
                background-color: {tm.primary_light};
                border: 1px solid {tm.primary_light};
                color: #ffffff;
            }}
        """)

    def _update_help_icon(self) -> None:
        tm = self.theme
        self._help_btn.setIcon(svg_icon("question_circle.svg", tm.text_secondary))
        self._help_btn.setIconSize(QSize(20, 20))

    def _update_ai_logo(self) -> None:
        """Update the logo shown on the AI welcome page."""
        candidates = (
            ["IES dark.png", "IES.png"] if self.theme.is_dark else ["IES.png", "IES dark.png"]
        )
        for name in candidates:
            path = ICON_DIR / name
            if path.exists():
                pix = QPixmap(str(path))
                if not pix.isNull():
                    dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
                    dpr = max(dpr, 1.0)
                    target_width = int(340 * dpr)
                    scaled = pix.scaledToWidth(target_width, Qt.SmoothTransformation)
                    scaled.setDevicePixelRatio(dpr)
                    self._ai_logo.setPixmap(scaled)
                return

    def _update_logo(self) -> None:
        candidates = (
            ["IES dark.png", "IES.png"] if self.theme.is_dark else ["IES.png", "IES dark.png"]
        )
        for name in candidates:
            path = ICON_DIR / name
            if path.exists():
                pix = QPixmap(str(path))
                if not pix.isNull():
                    logo_width = 300
                    dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
                    dpr = max(dpr, 1.0)
                    target_width = int(logo_width * dpr)
                    scaled = pix.scaledToWidth(target_width, Qt.SmoothTransformation)
                    scaled.setDevicePixelRatio(dpr)
                    self.logo.setPixmap(scaled)
                return

    def _select_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.i18n.t("beamplot_select_wos"),
            str(DEFAULT_DATA.parent if DEFAULT_DATA.parent.exists() else ASSETS_DIR),
            "WoS Text Files (*.txt *.ciw *.wos);;All Files (*)",
        )
        if paths:
            self._load_wos_sources(paths)

    def _load_wos_file(self, path: str) -> None:
        self._load_wos_sources([path])

    def _load_wos_sources(self, paths: list[str] | tuple[str, ...]) -> None:
        try:
            files = discover_wos_files(list(paths))
        except FileNotFoundError:
            self._show_error(self.i18n.t("beamplot_file_missing"))
            return
        if not files:
            self._show_error(self.i18n.t("beamplot_no_wos_files"))
            return
        source_paths = [str(p) for p in files]
        self._source_paths = source_paths
        self.file_edit.setText(source_paths[0])
        self._data_loaded = True
        self._set_loaded_sources_label(list(paths), files)

    def _use_default_data(self) -> None:
        if DEFAULT_DATA.exists():
            self._load_wos_sources([str(DEFAULT_DATA)])
            self._show_success(self.i18n.t("beamplot_default_selected"))
        else:
            self._show_error(self.i18n.t("beamplot_default_missing"))

    def _set_loaded_sources_label(self, selected: list[str], files: list[Path]) -> None:
        count = len(files)
        if count == 1:
            name = files[0].name
        elif len(selected) == 1 and Path(selected[0]).is_dir():
            name = self.i18n.t(
                "beamplot_upload_loaded_folder",
                name=Path(selected[0]).name,
                count=count,
            )
        else:
            name = self.i18n.t("beamplot_upload_loaded_multi", count=count)
        self._set_loaded_file_label(name)

    def _set_loaded_file_label(self, name: str) -> None:
        self._loaded_file_name = name
        self.upload_hint.setText(self.i18n.t("beamplot_upload_loaded", name=name))
        self.upload_sub_hint.setText(self.i18n.t("beamplot_upload_loaded_sub"))

    def _prompt_lang(self) -> str:
        return "en" if self.i18n.language == "en_US" else "zh"

    def _fmt_num(self, value) -> str:
        return fmt_num(value)

    def _on_point_clicked(self, info: dict) -> None:
        from beamplot.gui.prompt_loader import load_prompt

        customdata = info.get("customdata") or {}
        point_type = customdata.get("type", "unknown")
        year = customdata.get("year", info.get("y", "?"))
        lang = self._prompt_lang()

        if point_type == "citation":
            citations = customdata.get("raw_citations", customdata.get("citations", info.get("x", "?")))
            citations_fmt = self._fmt_num(citations)
            records_data = customdata.get("records") or []
            if records_data:
                records_info = self._format_dict_records_info(records_data)
            else:
                matching_records = self._find_matching_records(year, citations)
                records_info = self._format_records_info(matching_records)
            template = load_prompt("citation", lang)
            prompt = template.format(year=year, citations=citations_fmt, records_info=records_info)
            summary = self.i18n.t("beamplot_selected_citation", year=year, citations=citations_fmt)
        elif point_type == "median":
            median = customdata.get("median", info.get("x", "?"))
            median_fmt = self._fmt_num(median)
            year_records = [r for r in self._current_records if r.year == year]
            year_citations = [r.citations for r in year_records]
            year_info = ""
            if year_records:
                year_info = (
                    f"\n该年共有 {len(year_records)} 篇论文，"
                    f"引用范围为 {self._fmt_num(min(year_citations))} ~ {self._fmt_num(max(year_citations))}。"
                ) if lang == "zh" else (
                    f"\nThis year has {len(year_records)} papers, "
                    f"citation range: {self._fmt_num(min(year_citations))} ~ {self._fmt_num(max(year_citations))}."
                )
            template = load_prompt("median", lang)
            prompt = template.format(year=year, median=median_fmt, year_info=year_info)
            summary = self.i18n.t("beamplot_selected_median", year=year, median=median_fmt)
        elif point_type == "publication":
            count = customdata.get("count", "?")
            records_data = customdata.get("records") or []
            year_records = [r for r in self._current_records if r.year == year]
            year_citations = [r.citations for r in year_records]
            citation_summary = ""
            if year_citations:
                avg_cit = sum(year_citations) / len(year_citations)
                if lang == "zh":
                    citation_summary = (
                        f"\n这 {count} 篇论文的引用统计：总引用={self._fmt_num(sum(year_citations))}，"
                        f"平均引用={self._fmt_num(avg_cit)}，"
                        f"最高引用={self._fmt_num(max(year_citations))}，最低引用={self._fmt_num(min(year_citations))}。"
                    )
                else:
                    citation_summary = (
                        f"\nCitation stats for {count} papers: total={self._fmt_num(sum(year_citations))}, "
                        f"avg={self._fmt_num(avg_cit)}, max={self._fmt_num(max(year_citations))}, "
                        f"min={self._fmt_num(min(year_citations))}."
                    )
            template = load_prompt("publication", lang)
            prompt = template.format(year=year, count=count, citation_summary=citation_summary)
            summary = self.i18n.t("beamplot_selected_publication", year=year, count=count)
            self._show_point_info_panel(
                "publication", year, count, records_data
            )
        else:
            prompt = f"用户点击了图表中的一个点：x={info.get('x')}, y={info.get('y')}。请分析这个数据点。"
            summary = self.i18n.t("beamplot_selected_point")

        self._pending_prompt = prompt
        self._pending_context = f"最近一次图表交互：点击点。\n{prompt}"
        self._pending_interaction_summary = summary

    def _show_point_info_panel(
        self, ptype: str, year, value, records: list[dict]
    ) -> None:
        if not hasattr(self, "_point_info_panel"):
            self._point_info_panel = PointInfoPanel(self.canvas)
            self._point_info_panel.panel_hidden.connect(self.canvas.hide_plot_indicator)
        panel = self._point_info_panel
        if ptype == "citation":
            panel.show_citation_info(int(year), float(value), records)
        elif ptype == "publication":
            panel.show_publication_info(int(year), int(value), records)

    def _on_publication_hovered(self, info: dict) -> None:
        pass

    def _on_publication_unhovered(self) -> None:
        pass

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if hasattr(self, "_point_info_panel") and self._point_info_panel.isVisible():
            self._point_info_panel.hide()
        self.canvas.hide_citation_hover()

    def _find_matching_records(self, year: int, citations: float) -> list:
        """找到匹配给定年份和引用次数的文献记录"""
        matching = []
        for record in self._current_records:
            if record.year == year and abs(record.citations - citations) < 0.5:
                matching.append(record)
        return matching

    def _format_records_info(self, records: list) -> str:
        """格式化文献记录信息"""
        if not records:
            return "（未找到匹配的文献记录）"
        info_lines = ["匹配的文献记录:"]
        for i, record in enumerate(records[:5], 1):
            info_lines.append(
                f"  {i}. 年份: {record.year}, 引用: {self._fmt_num(record.citations)}"
            )
        if len(records) > 5:
            info_lines.append(f"  ... 共 {len(records)} 条记录")
        return "\n".join(info_lines)

    def _format_dict_records_info(self, records: list[dict]) -> str:
        if not records:
            return "（未找到匹配的文献记录）"
        info_lines = ["匹配的文献记录:"]
        for i, record in enumerate(records[:5], 1):
            year_val = record.get("year", "?")
            cit_val = self._fmt_num(
                record.get("citations", record.get("plot_citations", "?"))
            )
            title = record.get("title", "")
            line = f"  {i}. 年份: {year_val}, 引用: {cit_val}"
            if title:
                line += f", 标题: {title}"
            info_lines.append(line)
        if len(records) > 5:
            info_lines.append(f"  ... 共 {len(records)} 条记录")
        return "\n".join(info_lines)

    def _send_pending_interaction(self) -> None:
        """Send the latest chart interaction when the user opens the AI panel."""
        prompt = self._pending_prompt
        if not prompt:
            return
        self._active_session_id = self._chat_session_id
        self._switch_to_chat_page()
        self._interaction_context = self._pending_context
        self.chat_bar.set_context(self._build_current_ai_context())
        short_summary = self._pending_interaction_summary or prompt[:80]
        self._add_chat_bubble(short_summary, "user")
        self._current_ai_bubble = self._add_chat_bubble("Analyzing...", "assistant")
        self._chat_messages.append({"role": "user", "content": prompt})
        self.chat_bar.auto_send(prompt)
        self._pending_prompt = ""
        self._pending_context = ""
        self._pending_interaction_summary = ""

    def _on_region_selected(self, info: dict) -> None:
        from beamplot.gui.prompt_loader import load_prompt

        points = info.get("points", [])
        count = info.get("count", len(points))
        x_range = info.get("xRange")
        y_range = info.get("yRange")
        lang = self._prompt_lang()

        years_in_selection = set()
        citations_in_selection = []
        for p in points:
            customdata = p.get("customdata") or {}
            if customdata.get("type") == "citation":
                years_in_selection.add(customdata.get("year", p.get("y")))
                citations_in_selection.append(
                    customdata.get("raw_citations", customdata.get("citations", p.get("x")))
                )

        range_desc = ""
        detail = ""

        if years_in_selection:
            year_str = ", ".join(str(y) for y in sorted(years_in_selection))
            if lang == "zh":
                range_desc = f"涵盖年份：{year_str}。"
            else:
                range_desc = f"Years: {year_str}."
            if citations_in_selection:
                avg_citations = sum(citations_in_selection) / len(citations_in_selection)
                selected_pairs = ", ".join(
                    f"{p.get('customdata', {}).get('year', p.get('y'))}/"
                    f"{self._fmt_num((p.get('customdata') or {}).get('raw_citations', (p.get('customdata') or {}).get('citations', p.get('x'))))}"
                    for p in points[:20]
                    if (p.get("customdata") or {}).get("type") == "citation"
                )
                min_cit = self._fmt_num(min(citations_in_selection))
                max_cit = self._fmt_num(max(citations_in_selection))
                avg_cit = self._fmt_num(avg_citations)
                if lang == "zh":
                    detail = (
                        f"引用次数范围：{min_cit} ~ {max_cit}，"
                        f"平均引用：{avg_cit}。\n"
                        f"选中的数据点（year/citations）：{selected_pairs}"
                    )
                else:
                    detail = (
                        f"Citation range: {min_cit} ~ {max_cit}, "
                        f"average: {avg_cit}.\n"
                        f"Selected data points (year/citations): {selected_pairs}"
                    )
                summary = self.i18n.t(
                    "beamplot_selected_region_stats",
                    count=count,
                    min_citations=min_cit,
                    max_citations=max_cit,
                    avg_citations=avg_cit,
                )
            else:
                summary = self.i18n.t("beamplot_selected_region_years", count=count, years=year_str)
        else:
            if x_range:
                range_desc += (
                    f"引用次数范围: {self._fmt_num(x_range[0])} - {self._fmt_num(x_range[1])}。"
                    if lang == "zh"
                    else f"Citation range: {self._fmt_num(x_range[0])} - {self._fmt_num(x_range[1])}. "
                )
            if y_range:
                range_desc += (f"年份范围: {y_range[0]:.0f} - {y_range[1]:.0f}。" if lang == "zh"
                               else f"Year range: {y_range[0]:.0f} - {y_range[1]:.0f}. ")
            summary = self.i18n.t("beamplot_selected_region", count=count, range_desc=range_desc)

        template = load_prompt("region", lang)
        prompt = template.format(count=count, range_desc=range_desc, detail=detail)

        self._pending_prompt = prompt
        self._pending_context = f"最近一次图表交互：框选区域。\n{prompt}"
        self._pending_interaction_summary = summary
        self.interaction_hint.setText(summary)
        self._show_interaction_hint()

    def _run_analysis(self, *, show_success: bool = True) -> None:
        sources = list(self._source_paths) or ([self.file_edit.text().strip()] if self.file_edit.text().strip() else [])
        if not self._data_loaded or not sources:
            self._show_error(self.i18n.t("beamplot_need_file"))
            return
        if any(not Path(p).exists() for p in sources):
            self._show_error(self.i18n.t("beamplot_file_missing"))
            return
        path = sources[0]

        try:
            if self._publications_dirty and self._current_full_rows:
                full_rows = _enrich_publication_scores(self._current_full_rows)
                records = records_from_rows(full_rows)
            else:
                records, full_rows = read_wos_records_and_rows(sources)
                full_rows = _enrich_publication_scores(full_rows)
            result = build_beamplot_result(records, do_weight=self.weight_checkbox.isChecked())
            stats_result = build_beamplot_result(records, do_weight=False)
        except Exception as exc:
            self._show_error(str(exc))
            return

        mode = "interactive" if self._is_interactive else "static"
        self.canvas.set_pending_mode(mode)

        self._current_result = result
        self._stats_result = stats_result
        self._current_records = records
        self._current_full_rows = full_rows
        self._publications_dirty = False
        self.canvas.set_publication_rows(full_rows)
        self.canvas.render_result(result, raw_result=stats_result)
        summary = format_beamplot_summary(
            result=stats_result, i18n=self.i18n, plot_weighted=result.weighted
        )
        self._beamplot_text = summary
        metrics = _compute_metrics(stats_result)
        context = _build_ai_context(
            stats_result, records, self.i18n, plot_weighted=result.weighted
        )
        self.chat_bar.set_context(context)
        self._welcome_chat_bar.set_context(context)
        self.publications_ready.emit(full_rows)
        self._update_metrics(stats_result, metrics)
        self.save_button.setEnabled(True)
        self._save_memory_in_background(
            stats_result, records, metrics, path, full_rows, plot_weighted=result.weighted
        )

        if show_success:
            self._show_success(self.i18n.t("beamplot_ready"))

    def _save_memory_in_background(
        self,
        result: BeamplotResult,
        records: tuple[CitationRecord, ...],
        metrics: dict[str, str],
        source_path: str,
        full_rows: list[dict],
        *,
        plot_weighted: bool = False,
    ) -> None:
        try:
            if self._memory_worker and self._memory_worker.isRunning():
                self._memory_worker.requestInterruption()
                self._memory_worker.quit()
                self._memory_worker.wait(500)
        except RuntimeError:
            pass
        worker = MemorySaveWorker(
            result, records, metrics, source_path, full_rows, plot_weighted, self
        )
        worker.failed.connect(lambda message: self._show_error(f"Memory save failed: {message}"))
        worker.finished.connect(lambda: setattr(self, "_memory_worker", None))
        worker.finished.connect(worker.deleteLater)
        self._memory_worker = worker
        worker.start()

    def _update_metrics(self, result: BeamplotResult, metrics: dict[str, str] | None = None) -> None:
        metrics = metrics or _compute_metrics(result)
        for key, value in metrics.items():
            card = self.metric_cards.get(key)
            if card:
                card.set_value(value)

    def _save_plot(self) -> None:
        if self._current_result is None:
            self._show_error(self.i18n.t("beamplot_save_missing"))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.t("beamplot_save_title"),
            "beamplot.html" if self._is_interactive else "beamplot.png",
            "HTML File (*.html);;PNG Image (*.png);;PDF File (*.pdf);;SVG File (*.svg)"
            if self._is_interactive else
            "PNG Image (*.png);;PDF File (*.pdf);;SVG File (*.svg)",
        )
        if not path:
            return
        if self._is_interactive:
            path = str(Path(path).with_suffix(".html"))
        try:
            self.canvas.save_figure(path)
        except Exception as e:
            self._show_error(f"Export failed: {e}")
            return
        add_history_record(
            title=Path(self.file_edit.text()).name or "Beamplot Result",
            result=self._current_result,
            stats_result=self._stats_result,
            plot_weighted=bool(self._current_result and self._current_result.weighted),
            image_path=path,
            qa=self._qa_records,
            beamplot_text=self._beamplot_text,
            ai_text=self._ai_text,
            source_path=self.file_edit.text().strip(),
        )
        self.history_saved.emit()
        self._show_success(self.i18n.t("beamplot_saved"))

    def _record_qa(self, question: str, answer: str) -> None:
        sid = getattr(self, '_active_session_id', -1)
        if sid != self._chat_session_id:
            return
        self._qa_records.append({"question": question, "answer": answer})
        self._chat_messages.append({"role": "assistant", "content": answer})
        self._ai_text = answer
        if self._current_ai_bubble is not None:
            html = self._markdown_to_html(answer)
            self._current_ai_bubble.setText(html)
            self._current_ai_bubble.adjustSize()
            self._chat_layout.invalidate()
            self._chat_container.adjustSize()
            QTimer.singleShot(30, lambda: self._chat_scroll.verticalScrollBar().setValue(
                self._chat_scroll.verticalScrollBar().maximum()
            ))
        self._current_ai_bubble = None
        self._pending_stream_text = None

    def _build_current_ai_context(self) -> str:
        if self._current_result is None:
            memory_context = build_memory_context("")
            return "\n\n".join(part for part in [memory_context, self._interaction_context] if part)
        context = _build_ai_context(
            self._stats_result or self._current_result,
            self._current_records,
            self.i18n,
            plot_weighted=bool(self._current_result and self._current_result.weighted),
        )
        if self._interaction_context:
            context += "\n\n" + self._interaction_context
        return context

    def _show_error(self, message: str) -> None:
        InfoBar.error(
            title=self.i18n.t("beamplot_process_failed"), content=message,
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=5000, parent=self,
        )

    def _show_success(self, message: str) -> None:
        InfoBar.success(
            title=self.i18n.t("beamplot_done"), content=message,
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=2500, parent=self,
        )

    def _show_data_refreshed_tip(self) -> None:
        InfoBar.success(
            title=self.i18n.t("beamplot_data_refreshed_title"),
            content=self.i18n.t("beamplot_data_refreshed_content"),
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP, duration=3500, parent=self,
        )


class PublicationsView(QWidget):
    records_changed = pyqtSignal(object)

    CORE_FIELDS = [
        ("POS", "Pos"),
        ("AU", "Author"),
        ("TI", "Title"),
        ("SO", "Source"),
        ("PY", "Year"),
        ("GCS", "GCS"),
        ("LCS", "LCS"),
        ("DI", "DOI"),
        ("CONTROL", "CONTROL"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = ThemeManager.instance()
        self.i18n = I18n.instance()
        self._rows: list[dict] = []
        self._filtered_rows: list[dict] = []
        self._sort_column: int | None = None
        self._sort_order = Qt.AscendingOrder
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Publication List", self)
        title.setObjectName("publicationListTitle")
        self._title = title
        header_row.addWidget(title)
        self._stats_label = QLabel(self)
        self._stats_label.setObjectName("publicationStatsLabel")
        header_row.addWidget(self._stats_label)
        header_row.addStretch(1)
        self._year_filter_label = QLabel(self)
        header_row.addWidget(self._year_filter_label)
        self._year_filter = EditableComboBox(self)
        self._year_filter.setFixedWidth(136)
        self._year_filter.currentIndexChanged.connect(self._on_year_filter_changed)
        self._year_filter.returnPressed.connect(self._on_year_filter_changed)
        header_row.addWidget(self._year_filter)
        layout.addLayout(header_row)
        self.table = TableWidget(self)
        self.table.setColumnCount(len(self.CORE_FIELDS))
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels([label for _, label in self.CORE_FIELDS])
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self._on_header_clicked)
        self.table.setSortingEnabled(False)
        layout.addWidget(self.table)
        self._init_column_widths()
        self._apply_theme()
        self._apply_language()
        self.theme.theme_changed.connect(self._apply_theme)
        self.i18n.language_changed.connect(self._apply_language)

    def set_records(self, rows: object) -> None:
        if isinstance(rows, tuple):
            table_rows = [{"PY": r.year, "TC": f"{r.citations:g}"} for r in rows]
        else:
            table_rows = list(rows or [])
        self._rows = [dict(row) for row in table_rows]
        self._refresh_year_filter()
        self._populate_table()

    def _populate_table(self) -> None:
        selected_year = self._year_filter.currentData() if hasattr(self, "_year_filter") else None
        if not selected_year and hasattr(self, "_year_filter"):
            typed = self._year_filter.currentText().strip()
            if typed and typed != self.i18n.t("publication_all_years"):
                selected_year = typed
        if selected_year:
            self._filtered_rows = [
                row for row in self._rows
                if str(_field_value(row, "PY")) == str(selected_year)
            ]
        else:
            self._filtered_rows = list(self._rows)
        self._update_stats_line()
        self.table.setRowCount(len(self._filtered_rows))
        for row_idx, row_data in enumerate(self._filtered_rows):
            for col_idx, (field, _label) in enumerate(self.CORE_FIELDS):
                if field == "POS":
                    item = QTableWidgetItem(str(row_idx + 1))
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(QColor(self.theme.text_primary))
                    item.setData(Qt.UserRole, row_idx + 1)
                    self.table.setItem(row_idx, col_idx, item)
                    continue
                if field == "CONTROL":
                    self.table.setCellWidget(row_idx, col_idx, self._create_control_widget(row_data))
                    continue
                value = _field_value(row_data, field)
                if field == "DI":
                    doi = str(value or "").strip()
                    item = QTableWidgetItem("Full Text" if doi else "")
                    if doi:
                        item.setForeground(QColor("#1890ff"))
                        item.setToolTip(f"Click to open: https://doi.org/{doi}")
                        font = item.font()
                        font.setUnderline(True)
                        font.setFamily(self.theme.font_family)
                        font.setPointSize(9)
                        item.setFont(font)
                    else:
                        item.setForeground(QColor(self.theme.text_primary))
                        item.setToolTip("")
                else:
                    item = QTableWidgetItem(_compact_cell(_format_publication_cell(field, value)))
                    item.setForeground(QColor(self.theme.text_primary))
                    item.setToolTip(str(_format_publication_cell(field, value)))
                item.setData(Qt.UserRole, _sort_key(field, value))
                self.table.setItem(row_idx, col_idx, item)
        self._resize_columns()
        try:
            self.table.cellClicked.disconnect(self._on_cell_clicked)
        except TypeError:
            pass
        self.table.cellClicked.connect(self._on_cell_clicked)

    def _update_stats_line(self) -> None:
        years: list[int] = []
        for row in self._filtered_rows:
            value = str(_field_value(row, "PY")).strip()
            if not value:
                continue
            try:
                years.append(int(value))
            except ValueError:
                continue
        if years:
            year_span = f"{min(years)}-{max(years)}"
        else:
            year_span = "-"
        self._stats_label.setText(
            self.i18n.t(
                "publication_stats_line",
                count=len(self._filtered_rows),
                span=year_span,
            )
        )

    _COL_BASE_WIDTHS = [52, 150, 360, 170, 72, 72, 72, 92, 170]
    _COL_STRETCH = [0.0, 0.20, 0.48, 0.22, 0.0, 0.0, 0.0, 0.0, 0.10]

    def _init_column_widths(self) -> None:
        header = self.table.horizontalHeader()
        for col, base_w in enumerate(self._COL_BASE_WIDTHS):
            self.table.setColumnWidth(col, base_w)
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        self.table.setShowGrid(False)

    def _resize_columns(self) -> None:
        header = self.table.horizontalHeader()
        viewport_width = self.table.viewport().width()
        base_total = sum(self._COL_BASE_WIDTHS)
        available = max(viewport_width, base_total)
        extra = max(0, available - base_total)
        for col, base_w in enumerate(self._COL_BASE_WIDTHS):
            adjusted = base_w + int(extra * self._COL_STRETCH[col])
            self.table.setColumnWidth(col, adjusted)
            header.setSectionResizeMode(col, QHeaderView.Interactive)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "table"):
            self._resize_columns()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if hasattr(self, "table"):
            QTimer.singleShot(0, self._resize_columns)

    def _control_styles(self) -> dict[str, str]:
        ff = self.theme.font_family
        return {
            "edit": (
                f"QPushButton {{ background-color: #1890ff; color: #ffffff;"
                f" border: none; border-radius: 4px; font-size: 11px; font-family: '{ff}'; }}"
                f" QPushButton:hover {{ background-color: #40a9ff; }}"
            ),
            "delete": (
                f"QPushButton {{ background-color: #ff4d4f; color: #ffffff;"
                f" border: none; border-radius: 4px; font-size: 11px; font-family: '{ff}'; }}"
                f" QPushButton:hover {{ background-color: #ff7875; }}"
            ),
            "cite": (
                f"QPushButton {{ background-color: #52c41a; color: #ffffff;"
                f" border: none; border-radius: 4px; font-size: 11px; font-family: '{ff}'; }}"
                f" QPushButton:hover {{ background-color: #73d13d; }}"
            ),
        }

    def _create_control_widget(self, row_data: dict) -> QWidget:
        widget = QWidget(self.table)
        widget.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignCenter)
        styles = self._control_styles()
        for text, role in (("Edit", "edit"), ("Delete", "delete"), ("Cite", "cite")):
            btn = QPushButton(text, widget)
            btn.setFixedSize(50 if role != "delete" else 60, 26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(styles[role])
            btn.clicked.connect(lambda _checked=False, r=row_data, action=role: self._handle_control_action(action, r))
            layout.addWidget(btn)
        return widget

    def _handle_control_action(self, action: str, row_data: dict) -> None:
        if action == "cite":
            dialog = PublicationCiteDialog(row_data, self)
            dialog.exec_()
            return
        if action == "delete" and row_data in self._rows:
            self._rows.remove(row_data)
            is_filtered = self._year_filter.currentData() is not None
            if is_filtered:
                if row_data in self._filtered_rows:
                    vis_idx = self._filtered_rows.index(row_data)
                    self._filtered_rows.remove(row_data)
                    self.table.removeRow(vis_idx)
                    for i in range(vis_idx, self.table.rowCount()):
                        pos_item = self.table.item(i, 0)
                        if pos_item:
                            pos_item.setText(str(i + 1))
                            pos_item.setData(Qt.UserRole, i + 1)
                self._update_stats_line()
            else:
                self._refresh_year_filter(keep_current=True)
                self._populate_table()
            self.records_changed.emit(list(self._rows))
            return
        if action == "edit":
            dialog = PublicationEditDialog(row_data, self)
            if dialog.exec_():
                row_data.update(dialog.updated_fields())
                self._refresh_year_filter(keep_current=True)
                self._populate_table()
                self.records_changed.emit(list(self._rows))

    def _on_cell_clicked(self, row: int, column: int) -> None:
        if row < 0 or row >= len(self._filtered_rows):
            return
        field, _label = self.CORE_FIELDS[column]
        if field != "DI":
            return
        doi = str(_field_value(self._filtered_rows[row], "DI") or "").strip()
        if doi:
            QDesktopServices.openUrl(QUrl(f"https://doi.org/{doi}"))

    def _show_info(self, title: str, content: str) -> None:
        InfoBar.info(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self,
        )

    def _on_header_clicked(self, logical_index: int) -> None:
        field, _label = self.CORE_FIELDS[logical_index]
        if field in ("CONTROL", "POS"):
            self.table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
            return
        if self._sort_column == logical_index:
            self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self._sort_column = logical_index
            self._sort_order = Qt.AscendingOrder
        reverse = self._sort_order == Qt.DescendingOrder
        self._rows.sort(key=lambda row: _sort_key(field, _field_value(row, field)), reverse=reverse)
        self.table.horizontalHeader().setSortIndicator(logical_index, self._sort_order)
        self._populate_table()

    def _refresh_year_filter(self, keep_current: bool = False) -> None:
        current = self._year_filter.currentData() if keep_current else None
        years = sorted({str(_field_value(row, "PY")) for row in self._rows if str(_field_value(row, "PY")).strip()}, reverse=True)
        self._year_filter.blockSignals(True)
        self._year_filter.clear()
        self._year_filter.addItem(self.i18n.t("publication_all_years"), userData=None)
        for year in years:
            self._year_filter.addItem(year, userData=year)
        if current:
            idx = self._year_filter.findData(current)
            if idx >= 0:
                self._year_filter.setCurrentIndex(idx)
        self._year_filter.blockSignals(False)

    def _on_year_filter_changed(self) -> None:
        self._populate_table()

    def _apply_language(self) -> None:
        self._title.setText(self.i18n.t("publication_list_title"))
        self._year_filter_label.setText(self.i18n.t("publication_year_filter"))
        current = self._year_filter.currentData()
        self._refresh_year_filter(keep_current=True)
        if current:
            idx = self._year_filter.findData(current)
            if idx >= 0:
                self._year_filter.setCurrentIndex(idx)
        self._update_stats_line()

    def _apply_theme(self) -> None:
        tm = self.theme
        if tm.is_dark:
            row_bg = "#2d2d2d"
            alt_bg = "#363636"
            header_bg = "#333333"
        else:
            row_bg = "#ffffff"
            alt_bg = "#f5f9f9"
            header_bg = tm.bg_surface
        text_color = "#eeeeee" if tm.is_dark else "#1a1a1a"

        self.setStyleSheet(f"background-color: {tm.bg_page};")
        self._title.setStyleSheet(
            f"color: {tm.text_primary}; font-size: 16px; font-weight: 500;"
            f" font-family: '{tm.font_family}'; background: transparent;"
        )
        self._year_filter_label.setStyleSheet(
            f"color: {tm.text_secondary}; font-size: 12px; "
            f"font-family: '{tm.font_family}'; background: transparent;"
        )
        self._stats_label.setStyleSheet(
            f"color: {tm.text_secondary}; font-size: 12px; "
            f"font-family: '{tm.font_family}'; background: transparent; margin-left: 8px;"
        )
        self._year_filter.setStyleSheet(f"""
            EditableComboBox {{
                background-color: {tm.bg_surface};
                color: {tm.text_primary};
                border: 1px solid {tm.border_light};
                border-radius: 6px;
                padding: 4px 24px 4px 8px;
                font-family: "{tm.font_family}";
                font-size: 12px;
            }}
        """)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {row_bg};
                alternate-background-color: {alt_bg};
                color: {text_color};
                gridline-color: {tm.border_light};
                border: 1px solid {tm.border_light};
                border-radius: 8px;
                font-family: "{tm.font_family}";
                font-size: 12px;
                selection-background-color: {tm.primary_bg};
                selection-color: {text_color};
            }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {text_color};
                border: none;
                border-right: 1px solid {tm.border_light};
                border-bottom: 1px solid {tm.border_light};
                padding: 6px;
                font-weight: 500;
                font-family: "{tm.font_family}";
                font-size: 12px;
            }}
            QTableWidget::item {{
                color: {text_color};
                padding: 4px;
                outline: none;
            }}
            QTableWidget::item:selected {{
                background-color: {tm.primary_bg};
                color: {text_color};
                outline: none;
            }}
            QScrollBar:vertical {{
                background: {row_bg};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {tm.border};
                min-height: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {tm.text_secondary};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: {row_bg};
                height: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {tm.border};
                min-width: 30px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {tm.text_secondary};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """)
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, self.table.columnCount() - 1)
            if widget:
                widget.setStyleSheet("background-color: transparent;")
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    field = self.CORE_FIELDS[col][0]
                    if field == "DI":
                        item.setForeground(QColor("#1890ff"))
                    else:
                        item.setForeground(QColor(text_color))


class PublicationEditDialog(QDialog):
    EDITABLE_FIELDS = [
        ("AU", "Authors"),
        ("TI", "Title"),
        ("SO", "Source"),
        ("PY", "Year"),
        ("DI", "DOI"),
        ("AB", "Abstract"),
        ("DE", "Keywords (DE)"),
        ("ID", "Keywords (ID)"),
    ]

    _LONG_FIELDS = {"AB", "DE", "ID"}

    def __init__(self, record: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Record")
        self.setMinimumSize(700, 600)
        self.theme = ThemeManager.instance()
        self._editors: dict[str, object] = {}
        self._field_labels: list[QLabel] = []

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        self._title_label = QLabel("Edit Record Fields", self)
        root.addWidget(self._title_label)

        self._scroll = ScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget()
        form = QVBoxLayout(self._container)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 16)

        for field, label_text in self.EDITABLE_FIELDS:
            raw = record.get(field, "")
            value = "" if raw is None or str(raw).lower() == "nan" else str(raw)

            lbl = QLabel(label_text, self._container)
            self._field_labels.append(lbl)
            form.addWidget(lbl)

            if field in self._LONG_FIELDS:
                edit = TextEdit(self._container)
                edit.setPlainText(value)
                edit.setMinimumHeight(90)
                edit.setMaximumHeight(130)
            else:
                edit = LineEdit(self._container)
                edit.setText(value)

            self._editors[field] = edit
            form.addWidget(edit)

        form.addStretch(1)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = PushButton("Cancel", self)
        cancel_btn.clicked.connect(self.reject)
        save_btn = PrimaryPushButton("Save", self)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

        self._apply_theme()
        self.theme.theme_changed.connect(self._apply_theme)

    def _apply_theme(self) -> None:
        tm = self.theme
        ff = tm.font_family
        self.setStyleSheet(
            f"QDialog {{ background-color: {tm.bg_page}; font-family: '{ff}'; }}"
        )
        self._title_label.setStyleSheet(
            f"color: {tm.text_primary}; font-size: 15px; font-weight: 600;"
            f" font-family: '{ff}'; background: transparent;"
        )
        self._scroll.setStyleSheet(
            f"border: 1px solid {tm.border_light}; border-radius: 6px;"
            f" background: {tm.bg_card};"
        )
        self._container.setStyleSheet(f"background: {tm.bg_card};")
        label_ss = (
            f"color: {tm.text_primary}; font-size: 13px; font-weight: 600;"
            f" font-family: '{ff}'; background: transparent; border: none;"
        )
        for lbl in self._field_labels:
            lbl.setStyleSheet(label_ss)

    def updated_fields(self) -> dict:
        result: dict[str, str] = {}
        for field, editor in self._editors.items():
            if isinstance(editor, TextEdit):
                result[field] = editor.toPlainText().strip()
            else:
                result[field] = editor.text().strip()
        return result


class PublicationCiteDialog(QDialog):
    """Multi-format citation dialog."""

    FORMATS = [
        ("GB/T 7714-2015", "gbt"),
        ("APA (7th Edition)", "apa"),
        ("MLA (9th Edition)", "mla"),
        ("Chicago (17th Edition)", "chicago"),
    ]

    def __init__(self, record: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Citation Formats")
        self.setMinimumSize(550, 280)
        self._record = record
        self.theme = ThemeManager.instance()

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        header = QHBoxLayout()
        fmt_label = QLabel("Formats", self)
        fmt_label.setObjectName("citeFormatsLabel")
        header.addWidget(fmt_label)

        self._combo = ComboBox(self)
        self._combo.setFixedWidth(220)
        for display, code in self.FORMATS:
            self._combo.addItem(display, userData=code)
        self._combo.currentIndexChanged.connect(self._update_citation)
        header.addWidget(self._combo)
        header.addStretch(1)
        root.addLayout(header)

        self._text = TextEdit(self)
        self._text.setReadOnly(True)
        root.addWidget(self._text, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        copy_btn = PrimaryPushButton("Copy", self)
        copy_btn.setFixedSize(90, 34)
        copy_btn.clicked.connect(self._copy)
        close_btn = PushButton("Close", self)
        close_btn.setFixedSize(90, 34)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

        self._apply_theme()
        self.theme.theme_changed.connect(self._apply_theme)
        self._update_citation()

    def _apply_theme(self) -> None:
        tm = self.theme
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {tm.bg_page};
                font-family: "{tm.font_family}";
            }}
            QLabel#citeFormatsLabel {{
                color: {tm.text_primary};
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }}
        """)

    def _update_citation(self) -> None:
        fmt = self._combo.currentData()
        citation = self._generate(fmt or "gbt")
        self._text.setPlainText(citation)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._text.toPlainText())
        self._text.selectAll()

    def _generate(self, fmt: str) -> str:
        r = self._record
        if fmt == "gbt":
            return _format_gbt_citation(r)
        if fmt == "apa":
            return self._format_apa(r)
        if fmt == "mla":
            return self._format_mla(r)
        if fmt == "chicago":
            return self._format_chicago(r)
        return _format_gbt_citation(r)

    @staticmethod
    def _get(record: dict, field: str) -> str:
        val = _field_value(record, field)
        s = str(val or "").strip()
        return "" if s.lower() == "nan" else s

    def _authors_list(self, record: dict) -> list[str]:
        raw = self._get(record, "AU")
        if not raw:
            return []
        return [a.strip() for a in raw.split(";") if a.strip()]

    def _format_apa(self, r: dict) -> str:
        authors = self._authors_list(r)
        title = self._get(r, "TI")
        source = self._get(r, "SO")
        year = self._get(r, "PY")
        volume = str(r.get("VL", "") or "").strip()
        issue = str(r.get("IS", "") or "").strip()
        pages_b = str(r.get("BP", "") or "").strip()
        pages_e = str(r.get("EP", "") or "").strip()
        doi = self._get(r, "DI")

        formatted = []
        for a in authors[:7]:
            parts = a.split(",")
            if len(parts) >= 2:
                formatted.append(a.strip())
            else:
                tokens = a.strip().split()
                if len(tokens) >= 2:
                    formatted.append(f"{tokens[-1]}, {' '.join(tokens[:-1])}")
                else:
                    formatted.append(a.strip())
        if len(authors) > 7:
            author_str = ", ".join(formatted[:6]) + ", ... " + formatted[-1]
        elif len(formatted) > 1:
            author_str = ", ".join(formatted[:-1]) + ", & " + formatted[-1]
        else:
            author_str = formatted[0] if formatted else ""

        parts_out: list[str] = []
        if author_str:
            parts_out.append(f"{author_str} ({year})." if year else f"{author_str}.")
        if title:
            parts_out.append(f"{title}.")
        journal = _format_title_case(source) if source else ""
        if journal:
            j = f"*{journal}*"
            if volume:
                j += f", *{volume}*"
                if issue:
                    j += f"({issue})"
            if pages_b:
                j += f", {pages_b}"
                if pages_e:
                    j += f"-{pages_e}"
            parts_out.append(f"{j}.")
        if doi:
            parts_out.append(f"https://doi.org/{doi}")
        return " ".join(parts_out)

    def _format_mla(self, r: dict) -> str:
        authors = self._authors_list(r)
        title = self._get(r, "TI")
        source = self._get(r, "SO")
        year = self._get(r, "PY")
        volume = str(r.get("VL", "") or "").strip()
        issue = str(r.get("IS", "") or "").strip()
        pages_b = str(r.get("BP", "") or "").strip()
        pages_e = str(r.get("EP", "") or "").strip()
        doi = self._get(r, "DI")

        if len(authors) > 2:
            author_str = authors[0] + ", et al"
        elif len(authors) == 2:
            author_str = authors[0] + ", and " + authors[1]
        else:
            author_str = authors[0] if authors else ""

        parts: list[str] = []
        if author_str:
            parts.append(f"{author_str}.")
        if title:
            parts.append(f'"{title}."')
        if source:
            j = f"*{_format_title_case(source)}*"
            if volume:
                j += f", vol. {volume}"
                if issue:
                    j += f", no. {issue}"
            if year:
                j += f", {year}"
            if pages_b:
                j += f", pp. {pages_b}"
                if pages_e:
                    j += f"-{pages_e}"
            parts.append(f"{j}.")
        if doi:
            parts.append(f"https://doi.org/{doi}.")
        return " ".join(parts)

    def _format_chicago(self, r: dict) -> str:
        authors = self._authors_list(r)
        title = self._get(r, "TI")
        source = self._get(r, "SO")
        year = self._get(r, "PY")
        volume = str(r.get("VL", "") or "").strip()
        pages_b = str(r.get("BP", "") or "").strip()
        pages_e = str(r.get("EP", "") or "").strip()
        doi = self._get(r, "DI")

        if len(authors) > 3:
            author_str = ", ".join(authors[:3]) + ", et al"
        else:
            author_str = ", ".join(authors)

        parts: list[str] = []
        if author_str:
            parts.append(f"{author_str}.")
        if title:
            parts.append(f'"{title}."')
        if source:
            j = f"*{_format_title_case(source)}*"
            if volume:
                j += f" {volume}"
            if year:
                j += f" ({year})"
            if pages_b:
                j += f": {pages_b}"
                if pages_e:
                    j += f"-{pages_e}"
            parts.append(f"{j}.")
        if doi:
            parts.append(f"https://doi.org/{doi}.")
        return " ".join(parts)


class HistoryView(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = ThemeManager.instance()
        self.i18n = I18n.instance()
        self.records: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("History", self)
        self._title.setObjectName("historyViewTitle")
        title_row.addWidget(self._title)
        title_row.addStretch(1)
        self._clear_all_btn = QPushButton(self)
        self._clear_all_btn.setObjectName("historyClearAllBtn")
        self._clear_all_btn.setCursor(Qt.PointingHandCursor)
        self._clear_all_btn.clicked.connect(self._clear_all_records)
        title_row.addWidget(self._clear_all_btn)
        layout.addLayout(title_row)
        layout.addSpacing(8)
        body = QHBoxLayout()
        self.list_widget = ListWidget(self)
        self.list_widget.setFixedWidth(320)
        self.detail = TextEdit(self)
        self.detail.setReadOnly(True)
        body.addWidget(self.list_widget)
        body.addWidget(self.detail, 1)
        layout.addLayout(body)
        self.list_widget.currentRowChanged.connect(self._show_record)
        self._apply_history_theme()
        self.theme.theme_changed.connect(self._apply_history_theme)
        self.i18n.language_changed.connect(self._apply_language)
        self._apply_language()
        self.refresh()

    def _apply_language(self) -> None:
        self._clear_all_btn.setText(self.i18n.t("clear_all"))
        self._title.setText(self.i18n.t("history_title"))
        row = self.list_widget.currentRow()
        if row >= 0:
            self._show_record(row)

    def _apply_history_theme(self) -> None:
        tm = self.theme
        self._title.setStyleSheet(
            f"color: {tm.text_primary}; font-size: 18px; font-weight: 600;"
            f" font-family: '{tm.font_family}'; background: transparent;"
        )
        self._clear_all_btn.setStyleSheet(f"""
            QPushButton#historyClearAllBtn {{
                background: transparent;
                color: {tm.text_primary};
                border: 1px solid {tm.border_light};
                border-radius: 8px;
                padding: 5px 12px;
                font-size: 12px;
                font-family: "{tm.font_family}";
            }}
            QPushButton#historyClearAllBtn:hover {{
                color: {tm.text_primary};
                background-color: {tm.bg_hover};
            }}
        """)
        item_bg = tm.bg_surface if tm.is_dark else '#f9f9f9'
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {item_bg};
                color: {tm.text_primary};
                border: 1px solid {tm.border_light};
                border-radius: 8px;
                font-family: "{tm.font_family}";
                outline: none;
            }}
            QListWidget::item {{
                background-color: {item_bg};
                color: {tm.text_primary};
                border-left: 3px solid transparent;
                padding: 2px 4px;
            }}
            QListWidget::item:selected {{
                background-color: {tm.primary_bg};
                color: {tm.text_primary};
                border-left: 3px solid {tm.primary};
            }}
            QListWidget::item:hover:!selected {{
                background-color: {tm.bg_hover};
            }}
            QListWidget::item:focus {{
                outline: none;
            }}
        """)
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            widget = self.list_widget.itemWidget(item)
            if widget:
                widget.setStyleSheet(f"background-color: transparent;")
                for label in widget.findChildren(QLabel):
                    label.setStyleSheet(
                        f"color: {tm.text_primary}; font-size: 12px; "
                        f"font-family: '{tm.font_family}'; background: transparent;"
                    )

    def refresh(self) -> None:
        self.records = list(reversed(load_history_records()))
        self.list_widget.clear()
        for row, record in enumerate(self.records):
            self._add_history_item(row, record)
        self._clear_all_btn.setEnabled(bool(self.records))
        if self.records:
            self.list_widget.setCurrentRow(0)
        else:
            self.detail.setPlainText(self.i18n.t("no_history"))
        self._apply_history_theme()

    def _add_history_item(self, row: int, record: dict) -> None:
        from PyQt5.QtWidgets import QListWidgetItem

        tm = self.theme
        item = QListWidgetItem()
        item.setSizeHint(QSize(300, 54))
        widget = QWidget(self.list_widget)
        widget.setStyleSheet("background-color: transparent;")
        item_layout = QHBoxLayout(widget)
        item_layout.setContentsMargins(8, 5, 6, 5)
        item_layout.setSpacing(6)

        title = record.get("title", "Beamplot Result")
        timestamp = record.get("timestamp", "")
        text = QLabel(f"{title}\n{timestamp}", widget)
        text.setStyleSheet(
            f"color: {tm.text_primary}; font-size: 12px; "
            f"font-family: '{tm.font_family}'; background: transparent;"
        )
        item_layout.addWidget(text, 1)

        delete_btn = QPushButton(widget)
        delete_btn.setObjectName("historyDeleteBtn")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setIcon(svg_icon("close.svg", tm.text_secondary))
        delete_btn.setIconSize(QSize(14, 14))
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.setToolTip(self.i18n.t("delete"))
        delete_btn.setStyleSheet(
            "QPushButton#historyDeleteBtn { background: transparent; border: none; border-radius: 6px; padding: 3px; }"
            f"QPushButton#historyDeleteBtn:hover {{ background-color: {tm.bg_hover}; }}"
        )
        delete_btn.clicked.connect(lambda _=False, rid=record.get("id", ""): self._delete_record(rid))
        item_layout.addWidget(delete_btn)

        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _delete_record(self, record_id: str) -> None:
        if not record_id:
            return
        delete_history_record(record_id)
        self.refresh()

    def _clear_all_records(self) -> None:
        clear_history_records()
        self.refresh()

    def _show_record(self, row: int) -> None:
        if row < 0 or row >= len(self.records):
            return
        record = self.records[row]
        qa = record.get("qa") or []
        image_rel = record.get("image", "")
        image_abs = resolve_asset_path(image_rel) if image_rel else Path()
        image_exists = self.i18n.t(
            "history_detail_image_yes" if image_abs.exists() else "history_detail_image_no"
        )
        lines = [
            f"{self.i18n.t('history_detail_title')}: {record.get('title', '')}",
            f"{self.i18n.t('history_detail_time')}: {record.get('timestamp', '')}",
            f"{self.i18n.t('history_detail_image')}: {image_rel}",
            f"{self.i18n.t('history_detail_image_exists')}: {image_exists}",
            "",
            self.i18n.t("history_detail_beamplots"),
            history_summary_text(record, self.i18n),
            "",
            self.i18n.t("history_detail_ai"),
            record.get("ai_text", ""),
        ]
        if qa:
            lines.extend(["", self.i18n.t("history_detail_qa")])
            for item in qa:
                lines.append(f"{self.i18n.t('history_detail_question')}: {item.get('question', '')}")
                lines.append(f"{self.i18n.t('history_detail_answer')}: {item.get('answer', '')}")
                lines.append("")
        self.detail.setPlainText("\n".join(lines))


def _field_value(row: dict, field: str) -> object:
    if field in row:
        return row.get(field)
    aliases = {
        "PY": ("year", "Year"),
        "TC": ("citations", "timesCited", "Times Cited"),
        "GCS": ("TC", "citations", "timesCited", "Times Cited", "GCS"),
        "LCS": ("LC", "localCitations", "Local Citations", "LCS"),
        "AU": ("authors", "Authors"),
        "TI": ("title", "Title"),
        "SO": ("journal", "source", "Source"),
        "DI": ("doi", "DOI"),
        "UT": ("uid", "UT (Unique WOS ID)"),
    }
    for alias in aliases.get(field, ()):
        if alias in row:
            return row.get(alias)
    return ""


def _enrich_publication_scores(rows: list[dict]) -> list[dict]:
    enriched = [dict(row) for row in rows]
    uid_by_row = [_row_uid(row, idx) for idx, row in enumerate(enriched)]
    lookup = _build_publication_lookup(enriched, uid_by_row)
    lcs_map = {uid: 0 for uid in uid_by_row}

    for idx, row in enumerate(enriched):
        citing_uid = uid_by_row[idx]
        references = _split_references(row.get("CR", ""))
        for ref in references:
            cited_uid = _match_local_reference(ref, lookup)
            if cited_uid and cited_uid != citing_uid:
                lcs_map[cited_uid] = lcs_map.get(cited_uid, 0) + 1

    for idx, row in enumerate(enriched):
        uid = uid_by_row[idx]
        row["GCS"] = _coerce_int(_field_value(row, "TC"))
        row["LCS"] = lcs_map.get(uid, 0)
    return enriched


def _row_uid(row: dict, idx: int) -> str:
    value = row.get("UT") or row.get("uid") or row.get("UID") or f"WOS:{idx}"
    return str(value).strip()


def _build_publication_lookup(rows: list[dict], uid_by_row: list[str]) -> dict[str, dict[str, str]]:
    lookup = {
        "doi": {},
        "author_year_vol": {},
        "author_year_page": {},
    }
    for row, uid in zip(rows, uid_by_row):
        doi = str(row.get("DI", "") or row.get("DOI", "")).strip().lower()
        if doi and doi != "nan":
            lookup["doi"][doi] = uid

        first_author = _extract_first_author(str(row.get("AU", "") or row.get("authors", "")))
        year = str(row.get("PY", "") or row.get("year", "")).strip()
        volume = str(row.get("VL", "") or "").strip()
        page = str(row.get("BP", "") or "").strip()
        if first_author and year:
            if volume:
                lookup["author_year_vol"][f"{first_author}|{year}|{volume}"] = uid
            if page:
                lookup["author_year_page"][f"{first_author}|{year}|{page}"] = uid
    return lookup


def _split_references(value: object) -> list[str]:
    if value in (None, ""):
        return []
    text = str(value)
    if text.lower() == "nan":
        return []
    return [ref.strip() for ref in text.split(";") if ref.strip()]


def _match_local_reference(ref: str, lookup: dict[str, dict[str, str]]) -> str | None:
    doi_match = re.search(r"DOI\s+(10\.\S+)", ref, re.IGNORECASE)
    if doi_match:
        doi = doi_match.group(1).strip().rstrip(".").lower()
        if doi in lookup["doi"]:
            return lookup["doi"][doi]

    parts = [part.strip() for part in ref.split(",")]
    if len(parts) < 3:
        return None

    author = _normalize_reference_author(parts[0])
    year = parts[1].strip()
    volume = ""
    page = ""
    for part in parts[2:]:
        vol_match = re.match(r"^V(\d+)", part)
        if vol_match:
            volume = vol_match.group(1)
        page_match = re.match(r"^P(\d+)", part)
        if page_match:
            page = page_match.group(1)

    if not author or not year:
        return None
    if volume:
        uid = lookup["author_year_vol"].get(f"{author}|{year}|{volume}")
        if uid:
            return uid
    if page:
        return lookup["author_year_page"].get(f"{author}|{year}|{page}")
    return None


def _extract_first_author(authors: str) -> str:
    if not authors or authors.lower() == "nan":
        return ""
    first = authors.split(";")[0].strip()
    return _normalize_reference_author(first.split(",")[0])


def _normalize_reference_author(author: str) -> str:
    surname = author.strip().split(",")[0].strip().upper()
    return re.sub(r"[^A-Z\s\-]", "", surname)


def _coerce_int(value: object) -> int:
    try:
        return int(float(str(value or "").replace(",", "").strip()))
    except ValueError:
        return 0


def _compact_cell(value: object, limit: int = 160) -> str:
    text = str(value or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _format_publication_cell(field: str, value: object) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if not text:
        return ""
    if field in {"AU", "AF"}:
        return _format_authors(text)
    if field in {"TI", "SO", "DE", "ID"}:
        return _format_title_case(text)
    if field == "DT":
        return _format_document_type(text)
    return text


def _sort_key(field: str, value: object) -> object:
    if field in {"PY", "TC", "GCS", "LCS"}:
        try:
            return float(str(value or "").replace(",", ""))
        except ValueError:
            return float("-inf")
    return str(_format_publication_cell(field, value)).casefold()


def _format_gbt_citation(row: dict) -> str:
    authors_raw = str(_field_value(row, "AU") or "").strip()
    title = str(_field_value(row, "TI") or "").strip()
    source = str(_field_value(row, "SO") or "").strip()
    year = str(_field_value(row, "PY") or "").strip()
    volume = str(row.get("VL", "") or "").strip()
    issue = str(row.get("IS", "") or "").strip()
    begin_page = str(row.get("BP", "") or "").strip()
    end_page = str(row.get("EP", "") or "").strip()
    doi = str(_field_value(row, "DI") or "").strip()

    parts: list[str] = []
    if authors_raw:
        authors = [_format_author_name(author.strip()) for author in authors_raw.split(";") if author.strip()]
        author_text = ", ".join(authors[:3]) + (", et al" if len(authors) > 3 else "")
        if author_text:
            parts.append(author_text)
    if title:
        parts.append(f"{title}[J]")

    journal_parts: list[str] = []
    if source:
        journal_parts.append(_format_title_case(source))
    if year:
        year_part = year
        if volume:
            year_part += f", {volume}"
            if issue:
                year_part += f"({issue})"
        journal_parts.append(year_part)
    if begin_page or end_page:
        journal_parts.append(f"{begin_page}-{end_page}" if begin_page and end_page else begin_page or end_page)
    if journal_parts:
        parts.append(". ".join(journal_parts))
    if doi:
        parts.append(f"DOI: {doi}")
    return ". ".join(part for part in parts if part).rstrip(".") + "." if parts else ""


def _format_authors(text: str) -> str:
    return "; ".join(
        _format_author_name(part.strip())
        for part in text.split(";")
        if part.strip()
    )


def _format_author_name(name: str) -> str:
    tokens = []
    for idx, token in enumerate(name.split()):
        if idx == 0:
            tokens.append(token.capitalize() if token.isupper() or token.islower() else token)
        elif any(char.isalpha() for char in token):
            tokens.append(token.upper())
        else:
            tokens.append(token)
    return " ".join(tokens)


def _format_title_case(text: str) -> str:
    small_words = {
        "a", "an", "and", "as", "at", "but", "by", "for", "from", "in",
        "into", "nor", "of", "on", "onto", "or", "over", "per", "the",
        "to", "up", "via", "vs", "with", "within", "without",
    }
    acronym_whitelist = {
        "ai", "api", "bpd", "citespace", "doi", "esg", "html", "ieee",
        "isi", "json", "llm", "nlp", "pdf", "sdss", "ui", "ut", "wos",
    }
    words = re.split(r"(\s+)", text.strip().lower())
    formatted: list[str] = []
    word_positions = [i for i, token in enumerate(words) if token.strip()]
    first_word = word_positions[0] if word_positions else -1
    last_word = word_positions[-1] if word_positions else -1

    for idx, token in enumerate(words):
        if not token.strip():
            formatted.append(token)
            continue
        if token in small_words and idx not in (first_word, last_word):
            formatted.append(token)
            continue
        formatted.append(_capitalize_compound(token, acronym_whitelist))
    return "".join(formatted)


def _capitalize_compound(token: str, acronym_whitelist: set[str]) -> str:
    parts = re.split(r"([-/])", token)
    out = []
    for part in parts:
        if part in {"-", "/"}:
            out.append(part)
        elif part in acronym_whitelist:
            out.append(part.upper() if part != "citespace" else "CiteSpace")
        elif part:
            out.append(part[:1].upper() + part[1:])
    return "".join(out)


def _format_document_type(text: str) -> str:
    return "; ".join(
        _format_title_case(part.strip())
        for part in text.split(";")
        if part.strip()
    )


_METRIC_GLOSSARY = [
    (
        "TC", "Total Citations",
        "TC = \u03A3 c\u1D62",
        "Total Web of Science citation count across all loaded publications.",
    ),
    (
        "Avg.Cit.", "Average Citations",
        "Avg = TC / n",
        "Average citation count per publication, where n is the total number of publications.",
    ),
    (
        "h-index", "h-index",
        "h = max{ i : c\u1D62 \u2265 i }",
        "A value h means h publications have at least h citations each.",
    ),
    (
        "g-index", "g-index",
        "g = max{ i : \u03A3\u2C7C\u208C\u2081\u2071 c\u2C7C \u2265 i\u00B2 }",
        "The largest g such that the top g publications have at least g\u00B2 citations combined.",
    ),
    (
        "i10-index", "i10-index",
        "i10 = |{ i : c\u1D62 \u2265 10 }|",
        "Number of publications with at least 10 citations.",
    ),
    (
        "hg-index", "hg-index",
        "hg = \u221A(h \u00D7 g)",
        "Geometric mean of h-index and g-index.",
    ),
    (
        "\u03C0-index", "\u03C0-index",
        "\u03C0 = (\u03A3 c\u1D62 for top \u221An papers) / 100",
        "Citation sum of the top \u221An publications divided by 100.",
    ),
    (
        "w-index", "w-index",
        "w = max{ i : c\u1D62 \u2265 10i }",
        "The largest w such that at least w publications have 10\u00D7w citations each.",
    ),
    (
        "m-index", "m-index",
        "m = h / (y_max \u2212 y_min + 1)",
        "h-index divided by the publication-year span of the loaded dataset.",
    ),
]


class MetricsGlossaryDialog(QDialog):
    """CiteInsight-style glossary dialog for metric indicators."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Glossary of Metric Indicators")
        self.resize(660, 600)
        self.theme = ThemeManager.instance()

        self._badges: list[QLabel] = []
        self._names: list[QLabel] = []
        self._formula_boxes: list[QFrame] = []
        self._formula_labels: list[QLabel] = []
        self._desc_labels: list[QLabel] = []
        self._separators: list[QFrame] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = ScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._container = QWidget()
        form = QVBoxLayout(self._container)
        form.setContentsMargins(24, 20, 24, 20)
        form.setSpacing(0)

        for idx, (abbr, name, formula, desc) in enumerate(_METRIC_GLOSSARY):
            entry = self._build_entry(abbr, name, formula, desc, self._container)
            form.addWidget(entry)
            if idx < len(_METRIC_GLOSSARY) - 1:
                form.addSpacing(5)

        form.addStretch(1)
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll)

        self._apply_theme()
        self.theme.theme_changed.connect(self._apply_theme)

    def _build_entry(
        self, abbr: str, name: str, formula: str, desc: str, parent: QWidget
    ) -> QWidget:
        entry = QWidget(parent)
        layout = QVBoxLayout(entry)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(3)

        header = QHBoxLayout()
        header.setSpacing(10)

        badge = QLabel(abbr, entry)
        badge.setFixedHeight(24)
        self._badges.append(badge)
        header.addWidget(badge)

        title = QLabel(desc, entry)
        title.setWordWrap(False)
        self._names.append(title)
        header.addWidget(title, 1)
        header.addStretch(1)
        layout.addLayout(header)

        formula_box = QFrame(entry)
        fb_layout = QVBoxLayout(formula_box)
        fb_layout.setContentsMargins(12, 14, 12, 14)
        formula_label = QLabel(formula, formula_box)
        formula_label.setAlignment(Qt.AlignCenter)
        fb_layout.addWidget(formula_label)
        self._formula_boxes.append(formula_box)
        self._formula_labels.append(formula_label)
        layout.addWidget(formula_box)

        desc_label = QLabel("", entry)
        desc_label.setWordWrap(True)
        desc_label.hide()
        self._desc_labels.append(desc_label)
        layout.addWidget(desc_label)

        return entry

    def _apply_theme(self) -> None:
        tm = self.theme
        ff = tm.font_family
        bg = tm.bg_page

        self.setStyleSheet(
            f"QDialog {{ background-color: {bg}; font-family: '{ff}'; }}"
        )
        self._scroll.setStyleSheet(f"background: {bg}; border: none;")
        self._container.setStyleSheet(f"background: {bg};")

        badge_ss = (
            f"background-color: {tm.primary}; color: #ffffff;"
            f" font-size: 11px; font-weight: 600; font-family: '{ff}';"
            f" border-radius: 4px; padding: 2px 8px;"
        )
        name_ss = (
            f"color: {tm.text_secondary}; font-size: 12px; font-weight: 400;"
            f" font-family: '{ff}'; background: transparent;"
        )
        fbox_ss = (
            f"background-color: {tm.bg_surface};"
            f" border: 1px solid {tm.border_light}; border-radius: 6px;"
        )
        flabel_ss = (
            f"color: {tm.text_primary}; font-size: 13px;"
            f" font-family: 'Cambria Math', 'Times New Roman', serif;"
            f" background: transparent; border: none;"
        )
        desc_ss = (
            f"color: {tm.text_secondary}; font-size: 11px;"
            f" font-family: '{ff}'; background: transparent;"
        )
        sep_ss = f"background-color: {tm.border_light};"

        for b in self._badges:
            b.setStyleSheet(badge_ss)
        for n in self._names:
            n.setStyleSheet(name_ss)
        for fb in self._formula_boxes:
            fb.setStyleSheet(fbox_ss)
        for fl in self._formula_labels:
            fl.setStyleSheet(flabel_ss)
        for d in self._desc_labels:
            d.setStyleSheet(desc_ss)
        for s in self._separators:
            s.setStyleSheet(sep_ss)



def _build_ai_context(
    result: BeamplotResult,
    records: tuple[CitationRecord, ...],
    i18n: I18n | None = None,
    *,
    plot_weighted: bool = False,
) -> str:
    i18n = i18n or I18n.instance()
    memory_context = build_memory_context("")
    sample = "\n".join(
        f"- year={record.year}, citations={fmt_num(record.citations)}"
        for record in records
    )
    summary_text = format_beamplot_summary(
        result=result, i18n=i18n, plot_weighted=plot_weighted
    )
    weighted_note = (
        f"\n{i18n.t('beamplot_plot_weighted_note')}" if plot_weighted else ""
    )
    raw_context = (
        summary_text
        + weighted_note
        + f"\n\n全部 {len(records)} 条 WoS 记录（year/citations）:\n"
        + sample
        + "\n\n图表标记说明："
        + "\n- ◆ 菱形：每个菱形代表一篇具体论文，其x坐标为该论文的被引次数，y坐标为发表年份"
        + "\n- ▲ 三角形：代表某一年所有论文被引次数的中位数"
        + "\n- ● 圆形：代表某一年的发文数量（映射到上方x轴）"
        + "\n- 虚线：水平虚线=全局引用中位数，竖直红色虚线=年发文量中位数"
        + (
            "\n- 数值格式：引用次数及相关统计数值，整数不带小数，有小数部分时统一保留两位小数。"
        )
        + (
            "\n- 年龄加权说明：若图表启用了年龄加权，菱形/波束位置按加权被引次数绘制；"
            "metrics、交互信息与上述统计数据均使用原始未加权被引次数。"
            if plot_weighted
            else ""
        )
    )
    return "\n\n".join(part for part in (memory_context, raw_context) if part)


def _compute_metrics(result: BeamplotResult) -> dict[str, str]:
    citations = sorted((float(record.citations) for record in result.records), reverse=True)
    n = len(citations)
    total = sum(citations)
    h_index = _h_index(citations)
    g_index = _g_index(citations)
    i10_index = sum(1 for c in citations if c >= 10)
    hg_index = (h_index * g_index) ** 0.5 if h_index and g_index else 0.0
    pi_index = sum(citations[: max(1, n // 100)]) if n else 0.0
    w_index = _w_index(citations)
    year_span = max(result.years) - min(result.years) + 1 if result.years else 0
    m_index = h_index / year_span if year_span else 0.0
    return {
        "tc": fmt_num(total),
        "avg": fmt_num((total / n) if n else 0),
        "h": str(h_index),
        "g": str(g_index),
        "i10": str(i10_index),
        "hg": fmt_num(hg_index),
        "pi": fmt_num(pi_index),
        "w": str(w_index),
        "m": fmt_num(m_index),
    }


def _h_index(citations: list[float]) -> int:
    h = 0
    for idx, value in enumerate(citations, 1):
        if value >= idx:
            h = idx
        else:
            break
    return h


def _g_index(citations: list[float]) -> int:
    total = 0.0
    g = 0
    for idx, value in enumerate(citations, 1):
        total += value
        if total >= idx * idx:
            g = idx
    return g


def _w_index(citations: list[float]) -> int:
    w = 0
    for idx, value in enumerate(citations, 1):
        if value >= 10 * idx:
            w = idx
        else:
            break
    return w


class _MetricRow(QWidget):
    def __init__(self, value: str, label: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = ThemeManager.instance()
        self._value_color = color
        self.setMinimumWidth(0)
        self.card = SimpleCardWidget(self)
        self.card.setBorderRadius(8)
        self.card.setFixedHeight(72)
        self.value_label = QLabel(value, self)
        self.label_widget = QLabel(label, self)
        self.value_label.setContentsMargins(0, 0, 0, 0)
        self.label_widget.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 1)
        layout.setSpacing(0)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(4, 5, 4, 4)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.value_label, alignment=Qt.AlignHCenter)
        card_layout.addWidget(self.label_widget, alignment=Qt.AlignHCenter)
        layout.addWidget(self.card)
        self._apply_theme()
        self.theme.theme_changed.connect(self._apply_theme)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def _apply_theme(self) -> None:
        border_color = self.theme.border_light
        bg_color = self.theme.bg_surface if self.theme.is_dark else "#f9f9f9"
        self.card.setStyleSheet(
            f"SimpleCardWidget {{ background-color: {bg_color}; "
            f"border: 1px solid {border_color}; border-radius: 8px; }}"
        )
        self.value_label.setStyleSheet(
            f"font-family: '{self.theme.font_family}'; font-size: 20px; "
            f"font-weight: 700; color: {self._value_color}; background: transparent; "
            f"margin: 0; margin-top: 3px; padding: 0; line-height: 1.05;"
        )
        self.label_widget.setStyleSheet(
            f"font-family: '{self.theme.font_family}'; font-size: 11px; "
            f"color: {self.theme.text_secondary}; background: transparent; "
            f"margin: 0; padding: 0; margin-top: -4px; line-height: 1.1;"
        )


class PointInfoPanel(QWidget):
    """Floating, movable and resizable panel to display point info on chart click."""

    panel_hidden = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMinimumSize(380, 200)
        self.resize(520, 360)
        self.theme = ThemeManager.instance()
        self.i18n = I18n.instance()
        self._drag_pos = None
        self._resize_edge = None
        self._edge_margin = 8
        self.setMouseTracking(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(self._edge_margin, self._edge_margin,
                                self._edge_margin, self._edge_margin)
        root.setSpacing(0)

        inner = QWidget(self)
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)

        self._title_bar = QWidget(inner)
        self._title_bar.setFixedHeight(32)
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(12, 0, 8, 0)
        self._title_label = QLabel("", self._title_bar)
        self._title_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        title_layout.addWidget(self._title_label)
        title_layout.addStretch(1)
        close_btn = QPushButton("✕", self._title_bar)
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        self._close_btn = close_btn
        title_layout.addWidget(close_btn)
        inner_layout.addWidget(self._title_bar)

        self._scroll = ScrollArea(inner)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._content = QLabel(self._scroll)
        self._content.setWordWrap(True)
        self._content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._content.setTextFormat(Qt.RichText)
        self._content.setOpenExternalLinks(True)
        self._content.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self._content.setContentsMargins(14, 10, 14, 14)
        self._scroll.setWidget(self._content)
        inner_layout.addWidget(self._scroll)
        root.addWidget(inner)

        self._apply_theme()
        self.theme.theme_changed.connect(self._apply_theme)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.panel_hidden.emit()

    def show_citation_info(self, year: int, citations: float, records: list[dict]) -> None:
        first = records[0] if records else {}
        title = first.get("title", "")
        source = first.get("source", "")
        authors = first.get("authors", "")
        keywords = first.get("keywords", "")
        pos = first.get("pos", "?")
        lcs = first.get("lcs", "")
        gcs = first.get("gcs", first.get("citations", ""))

        is_dark = self.theme.is_dark
        label_color = "#9e9e9e" if is_dark else "#666666"
        text_color = "#e0e0e0" if is_dark else "#1a1a1a"
        badge_bg = "#3a3a3a" if is_dark else "#f0f0f0"
        badge_border = self.theme.border_light
        accent = self.theme.primary

        kw_list = [k.strip() for k in keywords.replace(";", ",").split(",") if k.strip()]
        kw_cells = ""
        for i, k in enumerate(kw_list[:10]):
            kw_cells += (
                f"<td style='background:{badge_bg}; border:1px solid {badge_border}; "
                f"padding:2px 8px; font-size:11px; color:{text_color};'>"
                f"{_html_esc(k)}</td>"
            )
            if (i + 1) % 4 == 0 and i + 1 < len(kw_list[:10]):
                kw_cells += "</tr><tr>"
            else:
                kw_cells += "<td width='4'></td>"
        kw_html = f"<table cellspacing='0' cellpadding='0'><tr>{kw_cells}</tr></table>" if kw_cells else ""

        html = (
            f"<table width='100%' cellspacing='0' cellpadding='4'>"
            f"<tr><td style='color:{label_color}; font-weight:600; width:75px; "
            f"vertical-align:top; font-size:12px;'>Title:</td>"
            f"<td style='color:{text_color}; font-size:12px;'>{_html_esc(title)}</td></tr>"
            f"<tr><td style='color:{label_color}; font-weight:600; "
            f"vertical-align:top; font-size:12px;'>Journal:</td>"
            f"<td style='color:{text_color}; font-size:12px;'>{_html_esc(source)}</td></tr>"
            f"<tr><td style='color:{label_color}; font-weight:600; "
            f"vertical-align:top; font-size:12px;'>Authors:</td>"
            f"<td style='color:{text_color}; font-size:12px;'>{_html_esc(authors)}"
            f"<span style='color:{accent}; margin-left:8px; font-size:11px;'>{year}</span>"
            f"</td></tr>"
            f"<tr><td style='color:{label_color}; font-weight:600; "
            f"vertical-align:top; font-size:12px;'>Keywords:</td>"
            f"<td>{kw_html}</td></tr>"
            f"</table>"
        )

        title_text = (
            f"<b>P{pos}</b>"
            f"&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<span style='color:{accent}; font-size:12px;'>LCS {_html_esc(str(lcs))}</span>"
            f"&nbsp;&nbsp;"
            f"<span style='color:{accent}; font-size:12px;'>GCS {_html_esc(str(gcs))}</span>"
        )
        self._title_label.setTextFormat(Qt.RichText)
        self._title_label.setText(title_text)
        self._content.setText(html)
        self._show_near_parent()

    def show_publication_info(
        self, year: int, count: int, records: list[dict]
    ) -> None:
        def _citation_value(rec: dict) -> float:
            return float(rec.get("citations", rec.get("plot_citations", 0)))

        sorted_recs = sorted(records, key=_citation_value, reverse=True)
        is_dark = self.theme.is_dark
        tc_color = "#52c41a" if not is_dark else "#95de64"
        link_color = "#1890ff" if not is_dark else "#69c0ff"
        total_tc = sum(_citation_value(r) for r in records)

        rows_html = ""
        for idx, rec in enumerate(sorted_recs[:30]):
            tc = fmt_num(_citation_value(rec))
            authors = _html_esc(rec.get("authors", ""))
            rec_year = rec.get("year", "")
            title = _html_esc(rec.get("title", ""))
            doi = str(rec.get("doi", "")).strip()
            doi_link = (
                f", <a href='https://doi.org/{_html_esc(doi)}' style='color:{link_color};'>"
                f"{_html_esc(doi)}</a>"
            ) if doi else ""
            rows_html += (
                f"<div style='margin:5px 0; line-height:1.5;'>"
                f"<span style='color:#888;'>({idx + 1})</span> "
                f"<b style='color:{tc_color};'>{tc}</b>, "
                f"{authors}, ({rec_year}), {title}{doi_link}</div>"
            )

        html = f"{rows_html}"
        self._title_label.setText(
            self.i18n.t(
                "beamplot_pub_info_title",
                year=year,
                count=count,
                total=fmt_num(total_tc),
            )
        )
        self._content.setText(html)
        self._show_near_parent()

    def _show_near_parent(self) -> None:
        if self.parent():
            parent_geo = self.parent().rect()
            x = 20
            y = parent_geo.height() - self.height() - 20
            global_pos = self.parent().mapToGlobal(self.parent().rect().topLeft())
            self.move(global_pos.x() + x, global_pos.y() + y)
        self.show()
        self.raise_()

    def _apply_theme(self) -> None:
        is_dark = self.theme.is_dark
        bg = self.theme.bg_surface if is_dark else "#ffffff"
        text = self.theme.text_primary
        border = self.theme.primary_border if is_dark else "#b0b0b0"
        title_bg = "#353535" if is_dark else "#f5f5f5"
        ff = self.theme.font_family

        self.setStyleSheet(
            f"PointInfoPanel {{ background: {bg}; "
            f"border: 1.5px solid {border}; border-radius: 10px; }}"
        )
        self._title_bar.setStyleSheet(
            f"background: {title_bg}; border-top-left-radius: 10px; "
            f"border-top-right-radius: 10px;"
        )
        self._title_label.setStyleSheet(
            f"color: {text}; font-weight: 600; font-size: 13px; "
            f"font-family: '{ff}'; background: transparent;"
        )
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {text}; "
            f"font-size: 14px; font-family: '{ff}'; border-radius: 12px; }}"
            f"QPushButton:hover {{ background: {'#4a4a4a' if is_dark else '#ddd'}; }}"
        )
        self._content.setStyleSheet(
            f"color: {text}; font-family: '{ff}'; font-size: 13px; "
            f"background: transparent; line-height: 1.4;"
        )
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {bg}; border: none; "
            f"border-bottom-left-radius: 10px; border-bottom-right-radius: 10px; }}"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            edge = self._hit_edge(event.pos())
            if edge:
                self._resize_edge = edge
                self._drag_pos = event.globalPos()
            elif event.pos().y() <= self._edge_margin + 32:
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                self._resize_edge = None
            else:
                self._drag_pos = None
                self._resize_edge = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resize_edge and self._drag_pos:
            delta = event.globalPos() - self._drag_pos
            self._drag_pos = event.globalPos()
            geo = self.geometry()
            if "right" in self._resize_edge:
                geo.setRight(geo.right() + delta.x())
            if "bottom" in self._resize_edge:
                geo.setBottom(geo.bottom() + delta.y())
            if "left" in self._resize_edge:
                geo.setLeft(geo.left() + delta.x())
            if "top" in self._resize_edge:
                geo.setTop(geo.top() + delta.y())
            if geo.width() >= self.minimumWidth() and geo.height() >= self.minimumHeight():
                self.setGeometry(geo)
        elif self._drag_pos and not self._resize_edge:
            self.move(event.globalPos() - self._drag_pos)
        else:
            edge = self._hit_edge(event.pos())
            if edge in ("right", "left"):
                self.setCursor(Qt.SizeHorCursor)
            elif edge in ("top", "bottom"):
                self.setCursor(Qt.SizeVerCursor)
            elif edge in ("top-left", "bottom-right"):
                self.setCursor(Qt.SizeFDiagCursor)
            elif edge in ("top-right", "bottom-left"):
                self.setCursor(Qt.SizeBDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        self._resize_edge = None
        super().mouseReleaseEvent(event)

    def _hit_edge(self, pos) -> str | None:
        m = self._edge_margin
        w, h = self.width(), self.height()
        x, y = pos.x(), pos.y()
        on_left = x < m
        on_right = x > w - m
        on_top = y < m
        on_bottom = y > h - m
        if on_top and on_left:
            return "top-left"
        if on_top and on_right:
            return "top-right"
        if on_bottom and on_left:
            return "bottom-left"
        if on_bottom and on_right:
            return "bottom-right"
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        return None


def _html_esc(value: object) -> str:
    import html as _html
    return _html.escape(str(value or ""))
