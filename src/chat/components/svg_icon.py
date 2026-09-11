"""主题感知的 SVG 图标渲染工具。"""

import os
from PyQt5.QtGui import QIcon, QIconEngine, QPixmap, QPainter, QImage, QColor
from PyQt5.QtCore import Qt, QRect, QRectF
from PyQt5.QtSvg import QSvgRenderer
from qfluentwidgets import isDarkTheme

_ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets",
)
ICON_DIR = os.path.join(_ASSETS_DIR, "icons")
PROVIDER_DIR = os.path.join(_ASSETS_DIR, "providers")


class _SvgIconEngine(QIconEngine):
    """每次绘制时根据当前主题实时着色的 SVG 引擎。"""

    def __init__(self, svg_path: str, color: str = None, raw: bool = False):
        super().__init__()
        self._svg_path = svg_path
        self._fixed_color = color
        self._raw = raw
        self._svg_content = None
        if os.path.exists(svg_path):
            with open(svg_path, "r", encoding="utf-8") as f:
                self._svg_content = f.read()

    def _colored_svg(self) -> bytes:
        if not self._svg_content:
            return b""
        if self._raw:
            return self._svg_content.encode("utf-8")
        if self._fixed_color:
            c = self._fixed_color
        else:
            c = "#e0e0e0" if isDarkTheme() else "#555555"
        svg = self._svg_content
        svg = svg.replace('stroke="currentColor"', f'stroke="{c}"')
        svg = svg.replace('fill="currentColor"', f'fill="{c}"')
        return svg.encode("utf-8")

    def paint(self, painter: QPainter, rect: QRect, mode, state):
        if not self._svg_content:
            return
        painter.save()
        if mode == QIcon.Disabled:
            painter.setOpacity(0.4)
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer = QSvgRenderer(self._colored_svg())
        renderer.render(painter, QRectF(rect))
        painter.restore()

    def pixmap(self, size, mode, state) -> QPixmap:
        img = QImage(size, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        pix = QPixmap.fromImage(img, Qt.NoFormatConversion)
        p = QPainter(pix)
        self.paint(p, QRect(0, 0, size.width(), size.height()), mode, state)
        p.end()
        return pix

    def clone(self):
        return _SvgIconEngine(self._svg_path, self._fixed_color, self._raw)


def svg_icon(name: str, color: str = None) -> QIcon:
    """按文件名加载 assets/icons/ 下的 SVG 并返回 QIcon。"""
    path = os.path.join(ICON_DIR, name)
    return QIcon(_SvgIconEngine(path, color))


def provider_icon(name: str) -> QIcon:
    """按文件名加载 assets/providers/ 下的彩色供应商 SVG 图标（保留原色）。"""
    path = os.path.join(PROVIDER_DIR, name)
    return QIcon(_SvgIconEngine(path, raw=True))

