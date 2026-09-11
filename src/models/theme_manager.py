from PyQt5.QtCore import QObject, pyqtSignal
from qfluentwidgets import isDarkTheme, setTheme, Theme

from models.config import load_config, save_config


FONT_FAMILY = "Microsoft YaHei UI"


class ThemeManager(QObject):
    """集中式主题管理单例。"""

    theme_changed = pyqtSignal()
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()

    @property
    def font_family(self) -> str:
        return FONT_FAMILY

    @property
    def is_dark(self) -> bool:
        return isDarkTheme()

    def switch_theme(self, theme: Theme):
        setTheme(theme)
        cfg = load_config()
        cfg["theme"] = "dark" if theme == Theme.DARK else "light"
        save_config(cfg)
        self.theme_changed.emit()

    def toggle_theme(self):
        if self.is_dark:
            self.switch_theme(Theme.LIGHT)
        else:
            self.switch_theme(Theme.DARK)

    @staticmethod
    def saved_theme() -> Theme:
        cfg = load_config()
        return Theme.DARK if cfg.get("theme") == "dark" else Theme.LIGHT

    # ── 页面层 ──
    @property
    def bg_page(self) -> str:
        return "#1c1c1c" if self.is_dark else "#ffffff"

    # ── 卡片层 ──
    @property
    def bg_card(self) -> str:
        return "#2a2a2a" if self.is_dark else "#ffffff"

    # ── 表面层 ──
    @property
    def bg_surface(self) -> str:
        return "#323232" if self.is_dark else "#fafafa"

    @property
    def bg_surface_light(self) -> str:
        return "#383838" if self.is_dark else "#f5f5f5"

    # ── 交互层 ──
    @property
    def bg_hover(self) -> str:
        return "#404040" if self.is_dark else "#e8f5f5"

    @property
    def bg_selected(self) -> str:
        return "#484848" if self.is_dark else "#d0eded"

    # ── 文字层 ──
    @property
    def text_primary(self) -> str:
        return "#e8e8e8" if self.is_dark else "#1a1a1a"

    @property
    def text_secondary(self) -> str:
        return "#a0a0a0" if self.is_dark else "#777777"

    @property
    def text_disabled(self) -> str:
        return "#666666" if self.is_dark else "#bfbfbf"

    # ── 边框层 ──
    @property
    def border(self) -> str:
        return "#444444" if self.is_dark else "#dcdcdc"

    @property
    def border_light(self) -> str:
        return "#3a3a3a" if self.is_dark else "#e8e8e8"

    @property
    def grid_line(self) -> str:
        return "#363636" if self.is_dark else "#f0f0f0"

    # ── 输入层 ──
    @property
    def input_bg(self) -> str:
        return "#252525" if self.is_dark else "#f8f8f8"

    @property
    def input_border(self) -> str:
        return "#4a4a4a" if self.is_dark else "#d8d8d8"

    # ── 品牌色（青绿色，匹配 IES 图标 #1ba8a0 色调） ──
    @property
    def primary(self) -> str:
        return "#26a69a" if self.is_dark else "#1a9e93"

    @property
    def primary_light(self) -> str:
        return "#4db6ac" if self.is_dark else "#26a69a"

    @property
    def primary_bg(self) -> str:
        return "#1a3230" if self.is_dark else "#e0f2f1"

    @property
    def primary_border(self) -> str:
        return "#2e7d75" if self.is_dark else "#80cbc4"

    @property
    def primary_hover(self) -> str:
        return "#4db6ac" if self.is_dark else "#00897b"

    # ── 文本选中高亮色（独立于 primary_bg，避免与按钮焦点混淆） ──
    # 选用偏 mint / 浅绿色系，黑白主题各自匹配清晰对比度
    @property
    def selection_bg(self) -> str:
        return "#2e7d32" if self.is_dark else "#c8e6c9"

    @property
    def selection_text(self) -> str:
        return "#ffffff" if self.is_dark else "#1a1a1a"

    # ── 状态色 ──
    @property
    def success(self) -> str:
        return "#4caf50"

    @property
    def warning(self) -> str:
        return "#ff9800"

    @property
    def error(self) -> str:
        return "#f44336"

