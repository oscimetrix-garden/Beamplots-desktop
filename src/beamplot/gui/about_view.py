from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from models.theme_manager import ThemeManager

ASSETS_DIR = Path(__file__).parents[2] / "assets"
ICON_DIR = ASSETS_DIR / "icons"

_DESCRIPTION = (
    "Beamplots is a visualization-based bibliometric method designed to support "
    "the comprehensive assessment of individual researchers' academic impact. "
    "Its core objective is to provide a more informative and transparent alternative "
    "to traditional single-number indicators such as the h-index. Unlike the h-index, "
    "which compresses complex scholarly performance into a single value, Beamplots "
    "simultaneously present publication productivity, citation impact, temporal "
    "evolution, and academic career trajectories, thereby offering a more comprehensive "
    "representation of a researcher's scholarly contributions."
)

_TEAM = [
    ("Jie Li", "National Science Library, Chinese Academy of Sciences, China"),
    ("Xian Li", "National Science Library, Chinese Academy of Sciences, China"),
    ("Robin Haunschild", "Max Planck Institute for Solid State Research, Germany"),
]

_EMAILS = [
    "lijie2022@mail.las.ac.cn",
    "lixian@mail.las.ac.cn",
    "R.Haunschild@fkf.mpg.de",
]


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setFixedSize(720, 560)
        self.tm = ThemeManager.instance()

        self._email_labels: list[QLabel] = []

        self._setup_ui()
        self._apply_theme()
        self.tm.theme_changed.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 12, 36, 20)
        root.setSpacing(0)

        # ── Logo ──
        self.logo = QLabel(self)
        self.logo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.logo.setFixedHeight(82)
        root.addWidget(self.logo, 0, Qt.AlignLeft)

        self._logo_divider = QFrame(self)
        self._logo_divider.setObjectName("logoDivider")
        self._logo_divider.setFixedHeight(1)
        root.addWidget(self._logo_divider)
        root.addSpacing(16)

        # ── Description ──
        self.desc_label = QLabel(_DESCRIPTION, self)
        self.desc_label.setWordWrap(True)
        root.addWidget(self.desc_label)
        root.addSpacing(20)

        # ── Divider ──
        self._section_div1 = QFrame(self)
        self._section_div1.setFixedHeight(1)
        root.addWidget(self._section_div1)
        root.addSpacing(16)

        # ── Project Team ──
        self.team_title = QLabel("Project Team", self)
        root.addWidget(self.team_title)
        root.addSpacing(8)

        self._team_label = QLabel(self)
        self._team_label.setWordWrap(True)
        self._team_label.setTextFormat(Qt.RichText)
        root.addWidget(self._team_label)
        root.addSpacing(16)

        # ── Contact ──
        self.contact_title = QLabel("Contact", self)
        root.addWidget(self.contact_title)
        root.addSpacing(8)

        email_row = QHBoxLayout()
        email_row.setContentsMargins(0, 0, 0, 0)
        email_row.setSpacing(24)
        for email in _EMAILS:
            lbl = QLabel("", self)
            lbl.setProperty("email", email)
            lbl.setOpenExternalLinks(True)
            lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
            email_row.addWidget(lbl)
            self._email_labels.append(lbl)
        email_row.addStretch(1)
        root.addLayout(email_row)
        root.addSpacing(20)

        # ── Divider ──
        self._section_div2 = QFrame(self)
        self._section_div2.setFixedHeight(1)
        root.addWidget(self._section_div2)
        root.addSpacing(14)

        # ── Reference ──
        self.ref_title = QLabel("Reference", self)
        root.addWidget(self.ref_title)
        root.addSpacing(6)
        self._ref_labels: list[QLabel] = []
        refs = [
            "Haunschild, R., Bornmann, L., & Adams, J. (2019). R package for producing "
            "beamplots as a preferred alternative to the h index when assessing single "
            "researchers (based on downloads from Web of Science). Scientometrics, 120, 925–927.",
            "Bornmann, L., & Haunschild, R. (2018). Plots for visualizing paper impact and "
            "journal impact of single researchers in a single graph. Scientometrics, 115(1), 385–394.",
        ]
        for ref_text in refs:
            lbl = QLabel(ref_text, self)
            lbl.setWordWrap(True)
            root.addWidget(lbl)
            root.addSpacing(4)
            self._ref_labels.append(lbl)

        root.addStretch(1)

    def _apply_theme(self) -> None:
        tm = self.tm
        self._update_logo()
        fs = 13
        ff = tm.font_family
        bg = tm.bg_page
        text_color = "#ffffff" if tm.is_dark else "#1a1a1a"
        text_secondary = "#b0b0b0" if tm.is_dark else "#666666"
        teal = tm.primary
        divider_color = "#3a3a3a" if tm.is_dark else "#eaeaea"

        self.setStyleSheet(
            f"QDialog {{ background-color: {bg}; font-family: '{ff}'; }}"
        )

        self.logo.setStyleSheet("background: transparent;")
        self._logo_divider.setStyleSheet(
            f"background-color: {divider_color}; border: none;"
        )
        self._section_div1.setStyleSheet(
            f"background-color: {divider_color}; border: none;"
        )
        self._section_div2.setStyleSheet(
            f"background-color: {divider_color}; border: none;"
        )

        label_base = (
            f"font-size: {fs}px; font-family: '{ff}'; background: transparent;"
        )
        self.desc_label.setStyleSheet(
            f"color: {text_color}; {label_base} line-height: 1.5;"
        )

        title_style = (
            f"color: {text_color}; font-size: 13px; font-weight: 600;"
            f" font-family: '{ff}'; background: transparent;"
        )
        self.team_title.setStyleSheet(title_style)
        self.contact_title.setStyleSheet(title_style)
        self.ref_title.setStyleSheet(title_style)

        team_html = "<br>".join(
            f'<span style="color:{teal}; font-weight:500;">{name}</span>'
            f'<span style="color:{text_secondary};">, {affiliation}</span>'
            for name, affiliation in _TEAM
        )
        self._team_label.setStyleSheet(
            f"color: {text_color}; {label_base} line-height: 1.5;"
        )
        self._team_label.setText(team_html)

        for lbl in self._email_labels:
            lbl.setStyleSheet(f"color: {teal}; {label_base}")
            email = lbl.property("email")
            if email:
                lbl.setText(
                    f'<a style="color:{teal}; text-decoration:none;'
                    f" font-family:'{ff}'; font-size:{fs}px;\""
                    f' href="mailto:{email}">{email}</a>'
                )

        ref_style = (
            f"color: {text_secondary}; font-size: 12px; font-family: '{ff}';"
            f" background: transparent; line-height: 1.5;"
        )
        for lbl in self._ref_labels:
            lbl.setStyleSheet(ref_style)

    def _update_logo(self) -> None:
        self.logo.setStyleSheet("background: transparent;")
        candidates = (
            ["IES dark.png", "IES.png"] if self.tm.is_dark else ["IES.png", "IES dark.png"]
        )
        for name in candidates:
            path = ICON_DIR / name
            if path.exists():
                pix = QPixmap(str(path))
                if not pix.isNull():
                    dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
                    dpr = max(dpr, 2.0)
                    target_w = 380
                    target_h = 82
                    scaled = pix.scaled(
                        int(target_w * dpr),
                        int(target_h * dpr),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                    scaled.setDevicePixelRatio(dpr)
                    self.logo.setPixmap(scaled)
                return
