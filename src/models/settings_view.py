"""设置视图 —— FluentWindow 子页面，参考 IES V2 风格。

包含：外观（主题/语言）、LLM 供应商配置（API Key/URL/模型探测/绿点状态）。
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QCheckBox, QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt5.QtGui import QIcon
from qfluentwidgets import (
    PrimaryPushButton, PushButton, FluentIcon,
    InfoBar, InfoBarPosition,
    SwitchButton, SpinBox, LineEdit, PasswordLineEdit,
    SubtitleLabel, BodyLabel, CaptionLabel, ScrollArea as FScrollArea,
    MessageBoxBase,
)

from models.theme_manager import ThemeManager
from models.i18n import I18n
from models.config import load_api_keys, save_api_keys, load_config, save_config
from chat.components.svg_icon import svg_icon, provider_icon

LLM_PROVIDERS = [
    {
        "key": "deepseek", "name": "DeepSeek", "icon": "deepseek.svg",
        "key_field": "deepseek_api_key",
        "default_base_url": "https://api.deepseek.com",
        "default_models": [],
    },
    {
        "key": "siliconflow", "name": "SiliconFlow", "icon": "siliconflow.svg",
        "key_field": "siliconflow_api_key",
        "default_base_url": "https://api.siliconflow.cn/v1",
        "default_models": [],
    },
    {
        "key": "qwen", "name": "Qwen", "icon": "qwen.svg",
        "key_field": "qwen_api_key",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_models": [],
    },
    {
        "key": "openai", "name": "OpenAI", "icon": "openai.svg",
        "key_field": "OPENAI_API_KEY",
        "default_base_url": "https://api.openai.com/v1",
        "default_models": [],
    },
    {
        "key": "azure", "name": "Azure OpenAI", "icon": "azure.svg",
        "key_field": "azure_openai_api_key",
        "default_base_url": "https://<resource>.openai.azure.com/",
        "default_models": [],
        "extra_fields": {"api_version": "2024-10-21"},
        "hidden": True,
    },
    {
        "key": "anthropic", "name": "Anthropic", "icon": "anthropic.svg",
        "key_field": "anthropic_api_key",
        "default_base_url": "https://api.anthropic.com",
        "default_models": ["claude-sonnet-4-5-20250414"],
    },
    {
        "key": "gemini", "name": "Gemini", "icon": "gemini.svg",
        "key_field": "gemini_api_key",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_models": ["gemini-2.5-flash"],
        "hidden": True,
    },
    {
        "key": "custom", "name": "Custom", "icon": "custom.svg",
        "key_field": "custom_api_key",
        "default_base_url": "",
        "default_models": [],
    },
]


# ─────────────────────────────────────────────────────
#  后台线程：测试 API 连通性并拉取可用模型列表
# ─────────────────────────────────────────────────────
class _APITestWorker(QThread):
    success = pyqtSignal(str, list)   # message, model_ids
    failed = pyqtSignal(str)

    def __init__(self, api_key: str, base_url: str, provider_key: str = ""):
        super().__init__()
        self._key = api_key
        self._url = base_url.rstrip("/")
        self._provider = provider_key

    def run(self):
        try:
            import httpx
            if self._provider == "anthropic":
                self._test_anthropic(httpx)
            elif self._provider == "gemini":
                self._test_gemini(httpx)
            elif self._provider == "azure":
                self._test_azure(httpx)
            else:
                self._test_openai_compat(httpx)
        except Exception as e:
            self.failed.emit(str(e)[:200])

    def _test_openai_compat(self, httpx):
        resp = httpx.get(
            f"{self._url}/models",
            headers={"Authorization": f"Bearer {self._key}"},
            timeout=15,
        )
        if resp.status_code == 200:
            models = self._parse_openai_models(resp)
            self.success.emit("Connection successful", models)
        else:
            self.failed.emit(f"HTTP {resp.status_code}: {resp.text[:200]}")

    def _test_anthropic(self, httpx):
        try:
            from anthropic import Anthropic
        except ImportError:
            self.failed.emit("Missing 'anthropic' package. Run: pip install anthropic")
            return
        kwargs = {"api_key": self._key, "timeout": 15.0}
        if self._url and self._url != "https://api.anthropic.com":
            kwargs["base_url"] = self._url
        client = Anthropic(**kwargs)

        models = []
        try:
            result = client.models.list(limit=100)
            for m in result.data:
                mid = getattr(m, "id", "")
                if mid:
                    models.append(mid)
            models.sort()
            self.success.emit("Connection successful", models)
            return
        except Exception:
            pass

        try:
            client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            default_models = [
                "claude-opus-4-6-20250414",
                "claude-sonnet-4-6-20250414",
                "claude-opus-4-1-20250414",
                "claude-sonnet-4-5-20250414",
                "claude-haiku-4-5-20250414",
                "claude-3-5-haiku-20241022",
                "claude-3-5-sonnet-20241022",
            ]
            self.success.emit("Connection successful", default_models)
        except Exception as e:
            err = str(e)
            if "model" in err.lower() and ("not found" in err.lower()
                                            or "not available" in err.lower()):
                self.success.emit("Connection successful",
                                  ["claude-sonnet-4-5-20250414"])
            else:
                self.failed.emit(err[:300])

    def _test_gemini(self, httpx):
        resp = httpx.get(
            f"{self._url}/models?key={self._key}",
            timeout=15,
        )
        if resp.status_code == 200:
            models = []
            try:
                data = resp.json()
                for item in data.get("models", []):
                    name = item.get("name", "")
                    if name.startswith("models/"):
                        models.append(name[7:])
                models.sort()
            except Exception:
                pass
            self.success.emit("Connection successful", models)
        else:
            self.failed.emit(f"HTTP {resp.status_code}: {resp.text[:200]}")

    def _test_azure(self, httpx):
        api_version = "2024-10-21"
        resp = httpx.get(
            f"{self._url}/openai/models?api-version={api_version}",
            headers={"api-key": self._key},
            timeout=15,
        )
        if resp.status_code == 200:
            models = self._parse_openai_models(resp)
            self.success.emit("Connection successful", models)
        else:
            self.failed.emit(f"HTTP {resp.status_code}: {resp.text[:200]}")

    @staticmethod
    def _parse_openai_models(resp) -> list:
        models = []
        try:
            data = resp.json()
            items = data.get("data", []) if isinstance(data, dict) else []
            for item in items:
                mid = item.get("id", "") if isinstance(item, dict) else ""
                if mid:
                    models.append(mid)
            models.sort()
        except Exception:
            pass
        return models


# ─────────────────────────────────────────────────────
#  模型选择对话框（从 API 拉取的模型中勾选）
# ─────────────────────────────────────────────────────
class _ModelSelectDialog(MessageBoxBase):

    def __init__(self, available_models: list, existing_models: list, parent=None):
        super().__init__(parent)
        tm = ThemeManager.instance()

        self.titleLabel = SubtitleLabel(I18n.instance().t("select_models"))

        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("Search models...")
        self.search_input.setFixedHeight(32)
        self.search_input.setClearButtonEnabled(True)

        scroll = FScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(320)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {tm.border_light};
                background-color: {tm.bg_surface};
                border-radius: 6px;
            }}
        """)

        list_widget = QWidget()
        list_widget.setStyleSheet(f"background-color: {tm.bg_surface};")
        self._list_layout = QVBoxLayout(list_widget)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(4)

        existing_set = set(existing_models)
        self._checkboxes = []
        for model_name in available_models:
            cb = QCheckBox(model_name)
            cb.setStyleSheet(
                f"font-size: 12px; color: {tm.text_primary}; "
                f"padding: 6px; background: transparent;"
            )
            if model_name in existing_set:
                cb.setChecked(True)
            self._checkboxes.append(cb)
            self._list_layout.addWidget(cb)

        self._list_layout.addStretch()
        scroll.setWidget(list_widget)

        def _filter(text):
            t = text.lower()
            for cb in self._checkboxes:
                cb.setVisible(t in cb.text().lower() if t else True)

        self.search_input.textChanged.connect(_filter)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.search_input)
        self.viewLayout.addWidget(scroll)

        self.yesButton.setText(I18n.instance().t("add_selected"))
        self.cancelButton.setText(I18n.instance().t("cancel"))
        self.widget.setMinimumWidth(420)

    def get_selected_models(self) -> list:
        return [cb.text() for cb in self._checkboxes if cb.isChecked()]


# ─────────────────────────────────────────────────────
#  设置对话框主体
# ─────────────────────────────────────────────────────
class SettingsView(QWidget):
    """设置子页面（FluentWindow 的 subInterface）。"""

    llm_settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsView")
        self.tm = ThemeManager.instance()
        self.i18n = I18n.instance()
        self._current_key = LLM_PROVIDERS[0]["key"]
        self._provider_btns: list = []
        self._status_dots: dict = {}
        self._fetched_models: list = []
        self._test_worker = None

        self._build_ui()
        self._select_provider(self._current_key)
        self._apply_theme()
        self._apply_lang()
        self.tm.theme_changed.connect(self._apply_theme)
        self.i18n.language_changed.connect(self._apply_lang)

    # ═══════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("settingsScroll")
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setObjectName("settingsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        self._title = SubtitleLabel()
        layout.addWidget(self._title)
        layout.addSpacing(4)

        # ═══════════ 外观卡片 ═══════════
        appearance_card = QFrame()
        appearance_card.setObjectName("settingsCard")
        ac = QVBoxLayout(appearance_card)
        ac.setContentsMargins(20, 16, 20, 16)
        ac.setSpacing(14)

        # 主题行（对齐：标签 | stretch | ☀ switch ☽）
        theme_row = QHBoxLayout()
        theme_row.setSpacing(8)
        self._theme_label = BodyLabel()
        self._theme_label.setMinimumWidth(140)
        theme_row.addWidget(self._theme_label)
        theme_row.addStretch()

        self._sun_label = QLabel()
        self._sun_label.setFixedSize(20, 20)
        self._sun_label.setAlignment(Qt.AlignCenter)
        theme_row.addWidget(self._sun_label)
        self._theme_switch = SwitchButton()
        self._theme_switch.setOnText("")
        self._theme_switch.setOffText("")
        self._theme_switch.setChecked(self.tm.is_dark)
        self._theme_switch.checkedChanged.connect(self._on_theme_toggle)
        theme_row.addWidget(self._theme_switch)
        self._moon_label = QLabel()
        self._moon_label.setFixedSize(20, 20)
        self._moon_label.setAlignment(Qt.AlignCenter)
        theme_row.addWidget(self._moon_label)
        ac.addLayout(theme_row)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setObjectName("cardSep")
        ac.addWidget(sep1)

        # 语言行（对齐：标签 | stretch | CN switch EN）
        lang_row = QHBoxLayout()
        lang_row.setSpacing(8)
        self._lang_label = BodyLabel()
        self._lang_label.setMinimumWidth(140)
        lang_row.addWidget(self._lang_label)
        lang_row.addStretch()

        self._lang_cn_lbl = CaptionLabel("CN")
        self._lang_cn_lbl.setFixedWidth(20)
        self._lang_cn_lbl.setAlignment(Qt.AlignCenter)
        lang_row.addWidget(self._lang_cn_lbl)
        self._lang_switch = SwitchButton()
        self._lang_switch.setOnText("")
        self._lang_switch.setOffText("")
        self._lang_switch.setChecked(not self.i18n.is_chinese)
        self._lang_switch.checkedChanged.connect(self._on_lang_toggle)
        lang_row.addWidget(self._lang_switch)
        self._lang_en_lbl = CaptionLabel("EN")
        self._lang_en_lbl.setFixedWidth(20)
        self._lang_en_lbl.setAlignment(Qt.AlignCenter)
        lang_row.addWidget(self._lang_en_lbl)
        ac.addLayout(lang_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setObjectName("cardSep")
        ac.addWidget(sep2)

        # 输出语言行（与 UI 语言区分）：Auto / CN / EN 三态胶囊按钮
        out_lang_row = QHBoxLayout()
        out_lang_row.setSpacing(8)
        self._out_lang_label = BodyLabel()
        self._out_lang_label.setMinimumWidth(140)
        out_lang_row.addWidget(self._out_lang_label)
        out_lang_row.addStretch()

        self._out_lang_frame = QFrame()
        self._out_lang_frame.setObjectName("outputLangFrame")
        self._out_lang_frame.setFixedHeight(32)
        olf = QHBoxLayout(self._out_lang_frame)
        olf.setContentsMargins(3, 3, 3, 3)
        olf.setSpacing(0)

        self._out_lang_auto_btn = QPushButton()
        self._out_lang_zh_btn = QPushButton()
        self._out_lang_en_btn = QPushButton()
        for b in (self._out_lang_auto_btn, self._out_lang_zh_btn, self._out_lang_en_btn):
            b.setObjectName("outputLangBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(26)
            olf.addWidget(b)
        self._out_lang_auto_btn.setMinimumWidth(72)
        self._out_lang_zh_btn.setMinimumWidth(56)
        self._out_lang_en_btn.setMinimumWidth(56)
        self._out_lang_auto_btn.clicked.connect(lambda: self._on_output_lang_changed("auto"))
        self._out_lang_zh_btn.clicked.connect(lambda: self._on_output_lang_changed("zh"))
        self._out_lang_en_btn.clicked.connect(lambda: self._on_output_lang_changed("en"))

        out_lang_row.addWidget(self._out_lang_frame)
        ac.addLayout(out_lang_row)

        layout.addWidget(appearance_card)

        # ═══════════ LLM 设置卡片 ═══════════
        llm_card = QFrame()
        llm_card.setObjectName("settingsCard")
        lc = QVBoxLayout(llm_card)
        lc.setContentsMargins(0, 0, 0, 0)
        lc.setSpacing(0)

        llm_title_row = QHBoxLayout()
        llm_title_row.setContentsMargins(20, 16, 20, 8)
        self._llm_title = BodyLabel()
        llm_title_row.addWidget(self._llm_title)
        lc.addLayout(llm_title_row)

        llm_body = QHBoxLayout()
        llm_body.setSpacing(0)
        llm_body.setContentsMargins(0, 0, 0, 0)

        # ── 左侧供应商列表 ──
        self._left_panel = QFrame()
        self._left_panel.setObjectName("llmLeft")
        self._left_panel.setFixedWidth(200)
        left_lay = QVBoxLayout(self._left_panel)
        left_lay.setContentsMargins(0, 8, 0, 8)
        left_lay.setSpacing(0)

        for prov in LLM_PROVIDERS:
            if prov.get("hidden"):
                continue
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(0, 0, 8, 0)
            row_l.setSpacing(0)

            btn = QPushButton(f"  {prov['name']}")
            btn.setObjectName("providerBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(44)
            btn.setCheckable(True)
            btn.setIcon(provider_icon(prov["icon"]))
            btn.setIconSize(QSize(20, 20))
            btn.clicked.connect(
                lambda checked, k=prov["key"]: self._select_provider(k)
            )
            row_l.addWidget(btn, 1)

            dot = QLabel("●")
            dot.setFixedSize(16, 16)
            dot.setAlignment(Qt.AlignCenter)
            dot.setStyleSheet("font-size: 10px; color: transparent; border: none;")
            row_l.addWidget(dot)
            self._status_dots[prov["key"]] = dot

            left_lay.addWidget(row_w)
            self._provider_btns.append((prov["key"], btn))

        left_lay.addStretch()
        llm_body.addWidget(self._left_panel)

        # ── 右侧配置面板 ──
        self._right_panel = QFrame()
        self._right_panel.setObjectName("llmRight")
        rr = QVBoxLayout(self._right_panel)
        rr.setContentsMargins(28, 20, 28, 20)
        rr.setSpacing(16)

        self._provider_title = SubtitleLabel("")
        rr.addWidget(self._provider_title)

        # API Key（标签 + 输入 + 测试按钮 同一行）
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        self._api_key_label = BodyLabel("API Key")
        self._api_key_label.setFixedWidth(70)
        key_row.addWidget(self._api_key_label)
        self._api_key_input = PasswordLineEdit()
        self._api_key_input.setPlaceholderText("Enter your API key")
        key_row.addWidget(self._api_key_input, 1)
        self._test_btn = PushButton()
        self._test_btn.setFixedWidth(72)
        self._test_btn.setCursor(Qt.PointingHandCursor)
        self._test_btn.clicked.connect(self._on_test_connection)
        key_row.addWidget(self._test_btn)
        self._clear_btn = PushButton()
        self._clear_btn.setFixedWidth(72)
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._on_clear)
        key_row.addWidget(self._clear_btn)
        rr.addLayout(key_row)

        # Base URL（标签 + 输入 同一行）
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self._base_url_label = BodyLabel("Base URL")
        self._base_url_label.setFixedWidth(70)
        url_row.addWidget(self._base_url_label)
        self._base_url_input = LineEdit()
        self._base_url_input.setPlaceholderText("https://api.example.com/v1")
        url_row.addWidget(self._base_url_input, 1)
        rr.addLayout(url_row)

        # Models
        model_header = QHBoxLayout()
        self._models_label = BodyLabel()
        model_header.addWidget(self._models_label)
        model_header.addStretch()
        self._models_hint = CaptionLabel()
        model_header.addWidget(self._models_hint)
        rr.addLayout(model_header)

        self._model_list_widget = QWidget()
        self._model_list_layout = QVBoxLayout(self._model_list_widget)
        self._model_list_layout.setContentsMargins(0, 0, 0, 0)
        self._model_list_layout.setSpacing(6)
        rr.addWidget(self._model_list_widget)

        # Streaming
        stream_row = QHBoxLayout()
        stream_row.setSpacing(8)
        self._streaming_label = CaptionLabel()
        stream_row.addWidget(self._streaming_label)
        self._stream_switch = SwitchButton()
        self._stream_switch.setOnText("")
        self._stream_switch.setOffText("")
        self._stream_switch.setChecked(True)
        stream_row.addWidget(self._stream_switch)
        stream_row.addStretch()
        rr.addLayout(stream_row)

        # SpinBox 行
        spin_row = QHBoxLayout()
        spin_row.setSpacing(16)

        temp_col = QVBoxLayout()
        temp_col.setSpacing(4)
        self._temp_label = CaptionLabel()
        temp_col.addWidget(self._temp_label)
        self._temp_spin = SpinBox()
        self._temp_spin.setRange(0, 200)
        self._temp_spin.setValue(70)
        self._temp_spin.setSuffix(" %")
        self._temp_spin.setFixedWidth(140)
        self._temp_spin.setFixedHeight(32)
        temp_col.addWidget(self._temp_spin)
        spin_row.addLayout(temp_col)

        tok_col = QVBoxLayout()
        tok_col.setSpacing(4)
        self._tokens_label = CaptionLabel()
        tok_col.addWidget(self._tokens_label)
        self._tokens_spin = SpinBox()
        self._tokens_spin.setRange(100, 128000)
        self._tokens_spin.setValue(4096)
        self._tokens_spin.setFixedWidth(140)
        self._tokens_spin.setFixedHeight(32)
        tok_col.addWidget(self._tokens_spin)
        spin_row.addLayout(tok_col)

        timeout_col = QVBoxLayout()
        timeout_col.setSpacing(4)
        self._timeout_label = CaptionLabel()
        timeout_col.addWidget(self._timeout_label)
        self._timeout_spin = SpinBox()
        self._timeout_spin.setRange(5, 600)
        self._timeout_spin.setValue(300)
        self._timeout_spin.setFixedWidth(140)
        self._timeout_spin.setFixedHeight(32)
        timeout_col.addWidget(self._timeout_spin)
        spin_row.addLayout(timeout_col)

        spin_row.addStretch()
        rr.addLayout(spin_row)

        rr.addStretch()

        # Save 按钮
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = PrimaryPushButton("", self, FluentIcon.SAVE)
        self._save_btn.setFixedWidth(120)
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self._save_btn)
        rr.addLayout(save_row)

        llm_body.addWidget(self._right_panel, 1)
        lc.addLayout(llm_body)
        layout.addWidget(llm_card)

        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    # ═══════════════════════════════════════════════════
    #  国际化
    # ═══════════════════════════════════════════════════
    def _apply_lang(self):
        t = self.i18n.t
        self._title.setText(t("settings"))
        self._theme_label.setText(t("theme"))
        self._lang_label.setText(t("language_label"))
        self._out_lang_label.setText(t("output_language_label"))
        self._out_lang_auto_btn.setText(t("output_lang_auto"))
        self._out_lang_zh_btn.setText(t("output_lang_zh"))
        self._out_lang_en_btn.setText(t("output_lang_en"))
        self._llm_title.setText(t("llm_settings"))
        self._models_label.setText(t("models"))
        self._streaming_label.setText(t("streaming"))
        self._temp_label.setText(t("temperature"))
        self._tokens_label.setText(t("max_tokens"))
        self._timeout_label.setText(t("timeout"))
        self._save_btn.setText(t("save"))
        self._test_btn.setText(t("test"))
        self._clear_btn.setText(t("clear"))
        self._models_hint.setText(t("test_to_discover"))
        self._update_lang_label_styles()
        self._update_output_lang_styles()

    def _update_lang_label_styles(self):
        is_en = self._lang_switch.isChecked()
        tm = self.tm
        active_c = tm.primary
        inactive_c = tm.text_secondary
        self._lang_cn_lbl.setStyleSheet(
            f"color: {inactive_c if is_en else active_c}; font-weight: {'normal' if is_en else 'bold'}; "
            f"font-family: '{tm.font_family}';"
        )
        self._lang_en_lbl.setStyleSheet(
            f"color: {active_c if is_en else inactive_c}; font-weight: {'bold' if is_en else 'normal'}; "
            f"font-family: '{tm.font_family}';"
        )

    # ═══════════════════════════════════════════════════
    #  主题
    # ═══════════════════════════════════════════════════
    def _apply_theme(self):
        tm = self.tm
        ff = tm.font_family
        icon_color = "#e0e0e0" if tm.is_dark else "#555555"

        self._sun_label.setPixmap(svg_icon("sun.svg", icon_color).pixmap(18, 18))
        self._moon_label.setPixmap(svg_icon("moon.svg", icon_color).pixmap(18, 18))

        self.setStyleSheet(f"""
            QWidget#settingsView {{
                background-color: {tm.bg_page};
                font-family: '{ff}';
            }}
            QWidget#settingsContent {{
                background-color: {tm.bg_page};
            }}
            QScrollArea#settingsScroll {{
                background-color: {tm.bg_page};
                border: none;
            }}
            QFrame#settingsCard {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border_light};
                border-radius: 10px;
            }}
            QFrame#cardSep {{
                color: {tm.border_light};
                background: transparent; border: none;
                border-top: 1px solid {tm.border_light};
                max-height: 1px;
            }}
            QFrame#llmLeft {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border_light};
                border-right: none;
                border-radius: 12px 0 0 12px;
            }}
            QFrame#llmRight {{
                background-color: {tm.bg_surface_light};
                border: 1px solid {tm.border_light};
                border-left: none;
                border-radius: 0 12px 12px 0;
            }}
            QFrame#modelRow {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border_light};
                border-radius: 8px;
            }}
            QPushButton#modelDelBtn {{
                background: transparent; color: #e74c3c;
                border: none; border-radius: 16px; font-size: 20px;
            }}
            QPushButton#modelDelBtn:hover {{
                background-color: {tm.bg_hover};
            }}
            QScrollArea#settingsScroll QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 2px 4px 0;
                border-radius: 4px;
            }}
            QScrollArea#settingsScroll QScrollBar::handle:vertical {{
                background: {tm.border};
                min-height: 32px;
                border-radius: 4px;
            }}
            QScrollArea#settingsScroll QScrollBar::handle:vertical:hover {{
                background: {tm.text_secondary};
            }}
            QScrollArea#settingsScroll QScrollBar::add-line:vertical,
            QScrollArea#settingsScroll QScrollBar::sub-line:vertical {{
                height: 0; background: none;
            }}
            QScrollArea#settingsScroll QScrollBar::add-page:vertical,
            QScrollArea#settingsScroll QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollArea#settingsScroll QScrollBar:horizontal {{
                height: 0; background: none;
            }}
        """)

        self._theme_switch.setChecked(self.tm.is_dark)

        self._llm_title.setStyleSheet(
            f"font-weight: bold; font-size: 14px; color: {tm.text_primary};"
        )
        self._provider_title.setStyleSheet(
            f"color: {tm.text_primary};"
        )
        self._api_key_label.setStyleSheet(f"color: {tm.text_primary};")
        self._base_url_label.setStyleSheet(f"color: {tm.text_primary};")
        self._models_label.setStyleSheet(f"color: {tm.text_primary};")
        self._streaming_label.setStyleSheet(f"color: {tm.text_secondary};")
        self._temp_label.setStyleSheet(f"color: {tm.text_secondary};")
        self._tokens_label.setStyleSheet(f"color: {tm.text_secondary};")
        self._timeout_label.setStyleSheet(f"color: {tm.text_secondary};")
        self._models_hint.setStyleSheet(f"color: {tm.text_secondary};")

        self._update_provider_btn_styles()
        self._update_lang_label_styles()
        self._update_output_lang_styles()
        self._refresh_all_dots()

        for i in range(self._model_list_layout.count()):
            w = self._model_list_layout.itemAt(i).widget()
            if w:
                self._style_model_row(w)

    def _update_provider_btn_styles(self):
        tm = self.tm
        ff = tm.font_family
        for key, btn in self._provider_btns:
            if btn.isChecked():
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tm.bg_hover};
                        color: {tm.text_primary};
                        border: none; border-left: 3px solid {tm.primary};
                        text-align: left; padding-left: 12px;
                        font-family: '{ff}';
                        font-size: 13px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {tm.text_secondary};
                        border: none; border-left: 3px solid transparent;
                        text-align: left; padding-left: 12px;
                        font-family: '{ff}';
                        font-size: 13px;
                    }}
                    QPushButton:hover {{
                        background-color: {tm.bg_hover};
                        color: {tm.text_primary};
                    }}
                """)

    def _style_model_row(self, row: QFrame):
        tm = self.tm
        row.setStyleSheet(f"""
            QFrame#modelRow {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border_light};
                border-radius: 8px;
            }}
        """)
        del_btn = row.findChild(QPushButton, "modelDelBtn")
        if del_btn:
            del_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: #e74c3c;
                    border: none; border-radius: 16px; font-size: 20px;
                }}
                QPushButton:hover {{ background-color: {tm.bg_hover}; }}
            """)

    # ═══════════════════════════════════════════════════
    #  外观 / 语言 事件
    # ═══════════════════════════════════════════════════
    def _on_theme_toggle(self, checked: bool):
        self.tm.toggle_theme()

    def _on_lang_toggle(self, checked: bool):
        lang = "en_US" if checked else "zh_CN"
        self.i18n.set_language(lang)

    # ── 输出语言（auto / zh / en）──
    def _on_output_lang_changed(self, lang: str):
        self.i18n.set_output_language(lang)
        self._update_output_lang_styles()

    def _update_output_lang_styles(self):
        tm = self.tm
        cur = self.i18n.output_language
        mapping = {
            "auto": self._out_lang_auto_btn,
            "zh": self._out_lang_zh_btn,
            "en": self._out_lang_en_btn,
        }
        for key, btn in mapping.items():
            active = (key == cur)
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tm.primary};
                        color: white;
                        border: none;
                        border-radius: 13px;
                        padding: 0 12px;
                        font-size: 12px;
                        font-weight: bold;
                        font-family: '{tm.font_family}';
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {tm.text_secondary};
                        border: none;
                        border-radius: 13px;
                        padding: 0 12px;
                        font-size: 12px;
                        font-family: '{tm.font_family}';
                    }}
                    QPushButton:hover {{
                        color: {tm.text_primary};
                        background-color: {tm.bg_hover};
                    }}
                """)
        self._out_lang_frame.setStyleSheet(f"""
            QFrame#outputLangFrame {{
                background-color: {tm.bg_surface};
                border: 1px solid {tm.border_light};
                border-radius: 16px;
            }}
        """)

    # ═══════════════════════════════════════════════════
    #  供应商切换
    # ═══════════════════════════════════════════════════
    def _select_provider(self, key: str):
        self._current_key = key
        self._fetched_models = []
        for k, btn in self._provider_btns:
            btn.setChecked(k == key)
        self._update_provider_btn_styles()
        self._refresh_all_dots()

        prov = next((p for p in LLM_PROVIDERS if p["key"] == key), LLM_PROVIDERS[0])
        self._provider_title.setText(prov["name"])

        cfg = load_config()
        keys = load_api_keys()
        provider_cfg = cfg.get("llm_providers", {}).get(key, {})

        key_val = keys.get(prov["key_field"], "")
        if key_val and not key_val.startswith("YOUR_"):
            self._api_key_input.setText(key_val)
        else:
            self._api_key_input.clear()

        self._base_url_input.setText(
            provider_cfg.get("base_url", prov["default_base_url"])
        )

        models = provider_cfg.get("models", prov["default_models"])
        self._populate_model_list(models)
        count = len(models)
        t = self.i18n.t
        self._models_hint.setText(
            t("n_models", n=count) if count else t("test_to_discover")
        )

        self._stream_switch.setChecked(provider_cfg.get("streaming", True))
        self._temp_spin.setValue(provider_cfg.get("temperature", 70))
        self._tokens_spin.setValue(provider_cfg.get("max_tokens", 4096))
        self._timeout_spin.setValue(provider_cfg.get("timeout", 300))

    def _populate_model_list(self, models: list):
        while self._model_list_layout.count():
            item = self._model_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for name in models:
            self._add_model_row(name)

    def _add_model_row(self, name: str):
        row = QFrame()
        row.setObjectName("modelRow")
        row.setFixedHeight(40)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(12, 0, 8, 0)
        rl.setSpacing(8)
        name_lbl = BodyLabel(name)
        rl.addWidget(name_lbl, 1)
        del_btn = QPushButton("⊖")
        del_btn.setObjectName("modelDelBtn")
        del_btn.setFixedSize(32, 32)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda: self._remove_model_row(row))
        rl.addWidget(del_btn)
        self._model_list_layout.addWidget(row)
        self._style_model_row(row)

    def _remove_model_row(self, row: QFrame):
        self._model_list_layout.removeWidget(row)
        row.deleteLater()

    def _get_current_models(self) -> list:
        models = []
        for i in range(self._model_list_layout.count()):
            w = self._model_list_layout.itemAt(i).widget()
            if w:
                lbl = w.findChild(BodyLabel)
                if lbl:
                    models.append(lbl.text())
        return models

    # ═══════════════════════════════════════════════════
    #  绿点状态
    # ═══════════════════════════════════════════════════
    def _refresh_all_dots(self):
        cfg = load_config()
        keys = load_api_keys()
        for prov_key, dot in self._status_dots.items():
            prov = next((p for p in LLM_PROVIDERS if p["key"] == prov_key), None)
            provider_cfg = cfg.get("llm_providers", {}).get(prov_key, {})
            config_verified = provider_cfg.get("verified", False)
            has_key = False
            if prov:
                stored_key = keys.get(prov["key_field"], "")
                has_key = bool(stored_key) and not stored_key.startswith("YOUR_")
            has_models = len(provider_cfg.get("models", [])) > 0
            is_green = config_verified and has_key and has_models
            if not is_green and config_verified:
                provider_cfg["verified"] = False
                save_config(cfg)
            if is_green:
                dot.setStyleSheet("font-size: 10px; color: #52c41a; border: none;")
            else:
                dot.setStyleSheet("font-size: 10px; color: transparent; border: none;")

    # ═══════════════════════════════════════════════════
    #  API 测试 / 模型拉取
    # ═══════════════════════════════════════════════════
    def _on_test_connection(self):
        api_key = self._api_key_input.text().strip()
        base_url = self._base_url_input.text().strip()
        t = self.i18n.t
        if not api_key or not base_url:
            InfoBar.warning(
                title=t("hint"), content=t("missing_key_url"),
                orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=3000,
                parent=self.window(),
            )
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("...")
        InfoBar.info(
            title=t("testing"), content=t("connecting"),
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP_RIGHT, duration=2000,
            parent=self.window(),
        )
        self._test_worker = _APITestWorker(api_key, base_url, self._current_key)
        self._test_worker.success.connect(self._on_test_success)
        self._test_worker.failed.connect(self._on_test_failed)
        self._test_worker.start()

    def _on_test_success(self, msg: str, models: list):
        self._test_btn.setEnabled(True)
        self._test_btn.setText(self.i18n.t("test"))
        self._fetched_models = models
        t = self.i18n.t

        InfoBar.success(
            title=t("test_success"), content=msg,
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP_RIGHT, duration=3000,
            parent=self.window(),
        )

        if models:
            existing = self._get_current_models()
            dialog = _ModelSelectDialog(models, existing, self.window())
            if dialog.exec():
                selected = dialog.get_selected_models()
                self._populate_model_list(selected)
                self._models_hint.setText(t("n_models", n=len(selected)))
        else:
            self._models_hint.setText(t("no_models_found"))

    def _on_test_failed(self, msg: str):
        self._test_btn.setEnabled(True)
        self._test_btn.setText(self.i18n.t("test"))
        InfoBar.error(
            title=self.i18n.t("test_failed"), content=msg,
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP_RIGHT, duration=5000,
            parent=self.window(),
        )

    # ═══════════════════════════════════════════════════
    #  清除当前供应商配置
    # ═══════════════════════════════════════════════════
    def _on_clear(self):
        prov = next(
            (p for p in LLM_PROVIDERS if p["key"] == self._current_key),
            LLM_PROVIDERS[0],
        )
        t = self.i18n.t

        keys = load_api_keys()
        keys[prov["key_field"]] = ""
        save_api_keys(keys)

        cfg = load_config()
        if "llm_providers" not in cfg:
            cfg["llm_providers"] = {}
        cfg["llm_providers"][prov["key"]] = {
            "base_url": prov["default_base_url"],
            "models": [],
            "streaming": True,
            "temperature": 70,
            "max_tokens": 4096,
            "timeout": 300,
            "verified": False,
        }
        save_config(cfg)

        self._select_provider(self._current_key)

        InfoBar.success(
            title=t("clear_success"), content=t("provider_cleared"),
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP_RIGHT, duration=2000,
            parent=self.window(),
        )

    # ═══════════════════════════════════════════════════
    #  保存
    # ═══════════════════════════════════════════════════
    def _on_save(self):
        prov = next(
            (p for p in LLM_PROVIDERS if p["key"] == self._current_key),
            LLM_PROVIDERS[0],
        )
        t = self.i18n.t

        api_key = self._api_key_input.text().strip()
        keys = load_api_keys()
        if api_key:
            keys[prov["key_field"]] = api_key
        else:
            keys[prov["key_field"]] = ""
        save_api_keys(keys)

        cfg = load_config()
        if "llm_providers" not in cfg:
            cfg["llm_providers"] = {}

        models = self._get_current_models()
        has_key = bool(api_key)
        has_test_passed = bool(self._fetched_models)
        has_models = len(models) > 0
        verified = has_key and has_test_passed and has_models

        cfg["llm_providers"][prov["key"]] = {
            "base_url": self._base_url_input.text().strip(),
            "models": models,
            "streaming": self._stream_switch.isChecked(),
            "temperature": self._temp_spin.value(),
            "max_tokens": self._tokens_spin.value(),
            "timeout": self._timeout_spin.value(),
            "verified": verified,
        }
        save_config(cfg)
        self._refresh_all_dots()

        InfoBar.success(
            title=t("save_success"), content=t("settings_saved"),
            orient=Qt.Horizontal, isClosable=True,
            position=InfoBarPosition.TOP_RIGHT, duration=2000,
            parent=self.window(),
        )
        self.llm_settings_changed.emit()

