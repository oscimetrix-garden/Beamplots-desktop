"""输入框中显示已附加 PDF 文件的卡片组件（参考 ChatGPT/Cursor 风格）。"""

import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton

from models.theme_manager import ThemeManager
from models.i18n import I18n
from chat.components.svg_icon import svg_icon


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.0f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


class FileAttachmentCard(QFrame):
    """已附加文件的胶囊状卡片：PDF 图标 + 文件名 + 状态。"""

    remove_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fileCard")
        self.tm = ThemeManager.instance()
        self.i18n = I18n.instance()
        self._file_path = ""
        self._status = ""
        self._build_ui()
        self._apply_theme()
        self.tm.theme_changed.connect(self._apply_theme)
        self.tm.theme_changed.connect(self._refresh_icons)
        self.i18n.language_changed.connect(self._refresh_status_label)

    def _build_ui(self):
        self.setFixedHeight(56)
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 8, 8)
        layout.setSpacing(10)

        self._icon_label = QLabel()
        self._icon_label.setObjectName("fileCardIcon")
        self._icon_label.setFixedSize(36, 36)
        self._icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._icon_label)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        self._name_label = QLabel("")
        self._name_label.setObjectName("fileCardName")
        text_col.addWidget(self._name_label)
        self._status_label = QLabel("")
        self._status_label.setObjectName("fileCardStatus")
        text_col.addWidget(self._status_label)
        layout.addLayout(text_col, 1)

        self._close_btn = QPushButton("×")
        self._close_btn.setObjectName("fileCardClose")
        self._close_btn.setFixedSize(20, 20)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setToolTip(self.i18n.t("remove_file"))
        self._close_btn.clicked.connect(self.remove_requested.emit)
        layout.addWidget(self._close_btn, 0, Qt.AlignTop)

    def set_file(self, path: str, status: str = ""):
        self._file_path = path
        name = os.path.basename(path) if path else ""
        size_str = ""
        try:
            size_str = _format_size(os.path.getsize(path))
        except OSError:
            pass
        self._name_label.setText(self._elide(name, 22))
        self._name_label.setToolTip(name)
        self._status = status or self.i18n.t("ready")
        self._size_str = size_str
        self._refresh_status_label()
        self.setVisible(True)

    def set_status(self, status: str):
        self._status = status
        self._refresh_status_label()

    def clear(self):
        self._file_path = ""
        self._name_label.setText("")
        self._status_label.setText("")
        self.setVisible(False)

    def _refresh_status_label(self):
        if not self._file_path:
            return
        size = getattr(self, "_size_str", "")
        if size:
            self._status_label.setText(f"{self._status} · {size}")
        else:
            self._status_label.setText(self._status)

    def _elide(self, text: str, n: int) -> str:
        return text if len(text) <= n else text[: n - 1] + "…"

    def _refresh_icons(self):
        tm = self.tm
        self._icon_label.setPixmap(
            svg_icon("pdf.svg", tm.text_secondary).pixmap(28, 28)
        )

    def _apply_theme(self):
        tm = self.tm
        ff = tm.font_family
        self.setStyleSheet(f"""
            QFrame#fileCard {{
                background-color: {tm.bg_surface};
                border: 1px solid {tm.border_light};
                border-radius: 12px;
            }}
            QLabel#fileCardIcon {{
                background: transparent; border: none;
            }}
            QLabel#fileCardName {{
                color: {tm.text_primary}; font-size: 13px; font-weight: 600;
                font-family: '{ff}'; background: transparent;
            }}
            QLabel#fileCardStatus {{
                color: {tm.text_secondary}; font-size: 11px;
                font-family: '{ff}'; background: transparent;
            }}
            QPushButton#fileCardClose {{
                background: transparent; border: none; border-radius: 10px;
                color: {tm.text_secondary}; font-size: 14px;
            }}
            QPushButton#fileCardClose:hover {{
                background-color: {tm.bg_hover};
                color: {tm.text_primary};
            }}
        """)
        self._refresh_icons()

