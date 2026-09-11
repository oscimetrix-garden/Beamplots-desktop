"""模型选择器：底部工具栏中的紧凑按钮 + 弹出的服务商分组列表。

视觉参考用户提供的图 1：
    - 顶层：服务商节点，带图标、名称、模型数量徽章；点击折叠/展开
    - 子项：模型节点，单选；点击后回填到按钮文字、关闭弹窗
    - 底部：搜索框 + 全部 / 收藏切换（搜索为基础实现）
"""

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QColor, QPen, QBrush
from PyQt5.QtWidgets import (
    QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
    QTreeWidget, QTreeWidgetItem, QLineEdit, QSizePolicy, QApplication,
    QHeaderView, QStyledItemDelegate, QStyle,
)

from models.theme_manager import ThemeManager
from models.i18n import I18n
from models.config import load_config, load_api_keys
from chat.components.svg_icon import svg_icon, provider_icon


PROVIDER_ICON_MAP = {
    "deepseek": "deepseek.svg",
    "siliconflow": "siliconflow.svg",
    "openai": "openai.svg",
    "azure": "azure.svg",
    "anthropic": "anthropic.svg",
    "gemini": "gemini.svg",
    "qwen": "qwen.svg",
    "custom": "custom.svg",
}

PROVIDER_DISPLAY_NAME = {
    "deepseek": "DeepSeek",
    "siliconflow": "SiliconFlow",
    "openai": "OpenAI",
    "azure": "Azure OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Gemini",
    "qwen": "Qwen",
    "custom": "Custom",
}


class _ProviderDividerDelegate(QStyledItemDelegate):
    """在每个顶层 (provider) 节点底部绘制一条分隔线。"""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color)

    def set_color(self, color: str):
        self._color = QColor(color)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if not index.parent().isValid():
            painter.save()
            painter.setRenderHint(painter.Antialiasing, False)
            pen = QPen(self._color)
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            r = option.rect
            y = r.bottom()
            painter.drawLine(r.left(), y, r.right(), y)
            painter.restore()


class _ModelPopup(QFrame):
    """模型选择弹出窗口。"""

    model_selected = pyqtSignal(str, str)  # provider, model

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setObjectName("modelPopup")
        self.tm = ThemeManager.instance()
        self.i18n = I18n.instance()
        self._current_value = ""
        self._build_ui()
        self._apply_theme()
        self.tm.theme_changed.connect(self._apply_theme)
        self.tm.theme_changed.connect(self._refresh_icons)

    def _build_ui(self):
        self.setFixedWidth(380)
        self.setMinimumHeight(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._tree = QTreeWidget()
        self._tree.setObjectName("modelTree")
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(2)
        self._tree.setIndentation(18)
        self._tree.setRootIsDecorated(True)
        self._tree.setIconSize(QSize(18, 18))
        self._tree.setExpandsOnDoubleClick(False)
        self._tree.setAnimated(True)
        self._tree.itemClicked.connect(self._on_item_clicked)
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self._tree.setColumnWidth(1, 48)
        self._divider_delegate = _ProviderDividerDelegate(self.tm.border_light, self._tree)
        self._tree.setItemDelegate(self._divider_delegate)
        layout.addWidget(self._tree, 1)

        self._search = QLineEdit()
        self._search.setObjectName("modelSearch")
        self._search.setPlaceholderText(self.i18n.t("search_model"))
        self._search.setFixedHeight(28)
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

    def _refresh_icons(self):
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            provider = item.data(0, Qt.UserRole)
            if provider:
                item.setIcon(0, _provider_or_default(provider))

    def populate(self, providers_cfg: dict, current_value: str = ""):
        """根据 providers_cfg 重建列表。current_value 形如 "provider/model"。"""
        from models.settings_view import LLM_PROVIDERS
        key_field_map = {p["key"]: p["key_field"] for p in LLM_PROVIDERS}
        api_keys = load_api_keys()

        self._current_value = current_value or ""
        self._tree.clear()
        cur_prov = cur_model = None
        if "/" in self._current_value:
            cur_prov, cur_model = self._current_value.split("/", 1)

        count_color = QColor(self.tm.text_secondary)

        for key, pcfg in providers_cfg.items():
            if not pcfg.get("verified"):
                continue
            kf = key_field_map.get(key, f"{key}_api_key")
            stored_key = api_keys.get(kf, "")
            if not stored_key or stored_key.startswith("YOUR_"):
                continue
            models = pcfg.get("models") or []
            if not models:
                continue
            display = PROVIDER_DISPLAY_NAME.get(key, key.title())
            top = QTreeWidgetItem(self._tree)
            top.setText(0, display)
            top.setText(1, str(len(models)))
            top.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            top.setForeground(1, QBrush(count_color))
            top.setData(0, Qt.UserRole, key)
            top.setData(0, Qt.UserRole + 1, "provider")
            top.setIcon(0, _provider_or_default(key))
            f = top.font(0)
            f.setBold(False)
            top.setFont(0, f)
            top.setSizeHint(0, QSize(0, 30))
            top.setExpanded(key == cur_prov or self._tree.topLevelItemCount() == 1)
            for m in models:
                child = QTreeWidgetItem(top)
                child.setText(0, m)
                child.setData(0, Qt.UserRole, m)
                child.setData(0, Qt.UserRole + 1, "model")
                child.setData(0, Qt.UserRole + 2, key)
                child.setSizeHint(0, QSize(0, 28))
                if cur_prov == key and cur_model == m:
                    f = child.font(0)
                    f.setBold(True)
                    child.setFont(0, f)
                    child.setForeground(0, QBrush(QColor(self.tm.primary)))

    def _on_item_clicked(self, item: QTreeWidgetItem, _col: int):
        kind = item.data(0, Qt.UserRole + 1)
        if kind == "provider":
            item.setExpanded(not item.isExpanded())
            return
        if kind == "model":
            provider = item.data(0, Qt.UserRole + 2)
            model = item.data(0, Qt.UserRole)
            self.model_selected.emit(provider, model)
            self.hide()

    def _apply_filter(self, text: str):
        text = (text or "").strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            visible_children = 0
            for j in range(top.childCount()):
                child = top.child(j)
                hit = (not text) or (text in child.text(0).lower())
                child.setHidden(not hit)
                if hit:
                    visible_children += 1
            top.setHidden(visible_children == 0)
            if text:
                top.setExpanded(visible_children > 0)

    def show_under(self, anchor: QWidget):
        """将弹窗显示在 anchor 控件上方（聊天框风格）。"""
        gp = anchor.mapToGlobal(anchor.rect().topLeft())
        h = self.sizeHint().height()
        if h < 380:
            h = 380
        x = gp.x() + anchor.width() - self.width()
        y = gp.y() - h - 6
        screen = QApplication.primaryScreen().availableGeometry()
        if x < screen.left() + 8:
            x = screen.left() + 8
        if y < screen.top() + 8:
            y = gp.y() + anchor.height() + 6
        self.move(x, y)
        self.show()
        self._search.setFocus()

    def _apply_theme(self):
        tm = self.tm
        ff = tm.font_family
        if hasattr(self, "_divider_delegate"):
            self._divider_delegate.set_color(tm.border_light)
        import os
        from chat.components.svg_icon import ICON_DIR
        u_right = os.path.join(ICON_DIR, "chevron_right.svg").replace("\\", "/")
        u_down = os.path.join(ICON_DIR, "chevron_down.svg").replace("\\", "/")
        self.setStyleSheet(f"""
            QFrame#modelPopup {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border};
                border-radius: 12px;
            }}
            QTreeWidget#modelTree {{
                background: transparent; border: none;
                color: {tm.text_primary}; font-family: '{ff}';
                font-size: 13px; outline: 0;
            }}
            QTreeWidget#modelTree::item {{
                padding: 6px 4px;
                color: {tm.text_primary};
            }}
            QTreeWidget#modelTree::item:hover {{
                background-color: {tm.bg_hover};
                color: {tm.text_primary};
            }}
            QTreeWidget#modelTree::item:selected,
            QTreeWidget#modelTree::item:selected:active {{
                background-color: {tm.primary_bg};
                color: {tm.text_primary};
            }}
            QTreeWidget#modelTree::branch {{
                background: transparent;
            }}
            QTreeWidget#modelTree::branch:has-children:!has-siblings:closed,
            QTreeWidget#modelTree::branch:closed:has-children:has-siblings {{
                image: url({u_right});
            }}
            QTreeWidget#modelTree::branch:open:has-children:!has-siblings,
            QTreeWidget#modelTree::branch:open:has-children:has-siblings {{
                image: url({u_down});
            }}
            QLineEdit#modelSearch {{
                background-color: {tm.input_bg};
                border: 1px solid {tm.input_border};
                border-radius: 14px; padding: 2px 12px;
                color: {tm.text_primary}; font-family: '{ff}'; font-size: 12px;
            }}
            QLineEdit#modelSearch:focus {{ border-color: {tm.primary}; }}
        """)


def _provider_or_default(key: str) -> QIcon:
    name = PROVIDER_ICON_MAP.get(key)
    if name:
        return provider_icon(name)
    return svg_icon("settings.svg")


class ModelSelector(QPushButton):
    """聊天框底部的模型选择按钮。点击展开服务商分组的弹出框。"""

    model_changed = pyqtSignal(str)  # "provider/model"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("modelSelectorBtn")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.tm = ThemeManager.instance()
        self.i18n = I18n.instance()
        self._current_value = ""
        self._popup = _ModelPopup(self)
        self._popup.model_selected.connect(self._on_picked)
        self.clicked.connect(self._toggle_popup)
        self._apply_theme()
        self.refresh_models()
        self.tm.theme_changed.connect(self._apply_theme)
        self.tm.theme_changed.connect(self._update_button_icon)
        self.i18n.language_changed.connect(self.refresh_models)

    def current_value(self) -> str:
        return self._current_value

    def refresh_models(self):
        cfg = load_config()
        providers_cfg = cfg.get("llm_providers", {})
        # 若当前值已失效，重置为第一个可用模型
        valid = self._collect_valid(providers_cfg)
        if not valid:
            self._current_value = ""
            self.setText(self.i18n.t("no_model"))
            self._update_button_icon()
            return
        if self._current_value not in valid:
            self._current_value = valid[0]
        self._refresh_label()
        self._popup.populate(providers_cfg, self._current_value)

    def _collect_valid(self, providers_cfg: dict) -> list:
        from models.settings_view import LLM_PROVIDERS
        key_field_map = {p["key"]: p["key_field"] for p in LLM_PROVIDERS}
        api_keys = load_api_keys()
        out = []
        for key, pcfg in providers_cfg.items():
            if not pcfg.get("verified"):
                continue
            kf = key_field_map.get(key, f"{key}_api_key")
            stored_key = api_keys.get(kf, "")
            if not stored_key or stored_key.startswith("YOUR_"):
                continue
            for m in pcfg.get("models") or []:
                out.append(f"{key}/{m}")
        return out

    def _toggle_popup(self):
        if self._popup.isVisible():
            self._popup.hide()
        else:
            cfg = load_config()
            self._popup.populate(cfg.get("llm_providers", {}), self._current_value)
            self._popup.show_under(self)

    def _on_picked(self, provider: str, model: str):
        self._current_value = f"{provider}/{model}"
        self._refresh_label()
        self.model_changed.emit(self._current_value)

    def _refresh_label(self):
        if not self._current_value:
            self.setText(f"  {self.i18n.t('no_model')}   ▾")
        else:
            _, model = self._current_value.split("/", 1)
            self.setText(f"  {self._elide(model, 18)}   ▾")
        self._update_button_icon()

    def _elide(self, text: str, n: int) -> str:
        return text if len(text) <= n else text[: n - 1] + "…"

    def _update_button_icon(self):
        if self._current_value and "/" in self._current_value:
            provider = self._current_value.split("/", 1)[0]
            self.setIcon(_provider_or_default(provider))
            self.setIconSize(QSize(16, 16))
        else:
            self.setIcon(QIcon())

    def _apply_theme(self):
        tm = self.tm
        ff = tm.font_family
        self.setStyleSheet(f"""
            QPushButton#modelSelectorBtn {{
                background-color: {tm.bg_surface};
                border: 1px solid {tm.border};
                border-radius: 16px;
                padding: 0 12px;
                text-align: left;
                color: {tm.text_primary};
                font-family: '{ff}'; font-size: 12px;
            }}
            QPushButton#modelSelectorBtn:hover {{
                border-color: {tm.primary};
                background-color: {tm.bg_hover};
            }}
            QPushButton#modelSelectorBtn:pressed {{
                background-color: {tm.bg_selected};
            }}
        """)

