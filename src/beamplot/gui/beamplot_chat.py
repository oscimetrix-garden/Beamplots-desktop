from __future__ import annotations

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, ToolTipFilter, ToolTipPosition

from chat.components.model_selector import ModelSelector
from chat.components.svg_icon import svg_icon
from models.i18n import I18n
from models.theme_manager import ThemeManager


_CHART_KEYWORDS = (
    "图", "图表", "beamplot", "beamp", "引用", "citation", "citations",
    "作者", "author", "年份", "year", "publication", "publications",
    "记录", "record", "records", "中位数", "median", "分布", "趋势",
    "数据", "wos", "指标", "metrics", "解读", "分析", "点", "框",
    "框选", "选区", "区域", "box", "select", "selected", "selection",
    "lasso", "range",
)


def _is_chart_question(text: str) -> bool:
    low = text.lower()
    return any(keyword in low for keyword in _CHART_KEYWORDS)


class _BeamplotChatWorker(QThread):
    chunk_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, user_msg: str, context: str, selected_model: str, lang: str,
                 history: list | None = None) -> None:
        super().__init__()
        self._user_msg = user_msg
        self._context = context if _is_chart_question(user_msg) else ""
        self._selected_model = selected_model
        self._lang = lang
        self._history = history or []
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            from models.llm_dispatch import chat_stream
            from beamplot.gui.memory_store import build_memory_context
            from beamplot.gui.prompt_loader import load_prompt

            lang_key = "en" if self._lang == "en" else "zh"
            memory_context = build_memory_context(self._user_msg)
            combined_context = "\n\n".join(
                part for part in (memory_context, self._context) if part
            )

            if combined_context:
                template = load_prompt("system", lang_key)
                if template:
                    system_prompt = template.replace("{context}", combined_context)
                else:
                    system_prompt = combined_context
            else:
                system_prompt = load_prompt("system_general", lang_key)

            messages = [{"role": "system", "content": system_prompt}]
            for msg in self._history:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": self._user_msg})

            for full in chat_stream(messages, selected_model=self._selected_model):
                if self._stop:
                    break
                self.chunk_ready.emit(full)
        except RuntimeError:
            self.error_occurred.emit(I18n.instance().t("no_llm_configured"))
        except Exception as exc:
            self.error_occurred.emit(str(exc)[:240])
        finally:
            self.finished_signal.emit()


class BeamplotChatBar(QWidget):
    response_ready = pyqtSignal(str)
    user_message_sent = pyqtSignal(str)
    exchange_finished = pyqtSignal(str, str)
    submit_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tm = ThemeManager.instance()
        self.i18n = I18n.instance()
        self._context = ""
        self._last_user_msg = ""
        self._conversation_history: list[dict[str, str]] = []
        self._worker: _BeamplotChatWorker | None = None
        self._external_submit = False
        self._build_ui()
        self._apply_language()
        self._apply_theme()
        self.tm.theme_changed.connect(self._apply_theme)
        self.i18n.language_changed.connect(self._apply_language)

    def _stop_worker(self) -> None:
        """Stop and detach the current worker before starting a new exchange."""
        if not self._worker:
            return
        if self._worker.isRunning():
            self._worker.request_stop()
            self._disconnect_worker()
            if not self._worker.wait(500):
                self._worker.terminate()
                self._worker.wait(500)
        else:
            self._disconnect_worker()
        self._worker = None

    def set_external_submit(self, enabled: bool) -> None:
        """When True, _on_send emits submit_requested instead of starting a worker."""
        self._external_submit = bool(enabled)

    def set_context(self, context: str) -> None:
        self._context = context

    def set_prompt_text(self, text: str) -> None:
        self.response_ready.emit(text)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._box = QFrame(self)
        self._box.setObjectName("chatInputBox")
        layout = QVBoxLayout(self._box)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(8)

        self._input = QLineEdit(self)
        self._input.setObjectName("chatInput")
        self._input.setMinimumHeight(36)
        self._input.returnPressed.connect(self._on_send)
        layout.addWidget(self._input)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._new_chat_btn = QPushButton(self)
        self._new_chat_btn.setObjectName("chatIconBtn")
        self._new_chat_btn.setFixedSize(30, 30)
        self._new_chat_btn.setIconSize(QSize(16, 16))
        self._new_chat_btn.setToolTip(self.i18n.t("beamplot_new_chat"))
        self._new_chat_btn.setCursor(Qt.PointingHandCursor)
        self._new_chat_btn.installEventFilter(ToolTipFilter(self._new_chat_btn, 300, ToolTipPosition.TOP))
        row.addWidget(self._new_chat_btn)

        row.addStretch(1)
        self._model_selector = ModelSelector(self)
        row.addWidget(self._model_selector)

        self._send_btn = QPushButton(self)
        self._send_btn.setObjectName("chatSendBtn")
        self._send_btn.setFixedSize(30, 30)
        self._send_btn.clicked.connect(self._on_send)
        self._send_btn.installEventFilter(ToolTipFilter(self._send_btn, 300, ToolTipPosition.TOP))
        row.addWidget(self._send_btn)

        layout.addLayout(row)
        outer.addWidget(self._box)

    def clear_history(self) -> None:
        """Clear conversation history for new chat."""
        self._conversation_history.clear()

    def reset_for_new_chat(self) -> None:
        """Stop the current response and reset this input bar for a new chat."""
        self._stop_worker()
        self._input.clear()
        self._last_user_msg = ""
        self._last_answer = ""
        self.clear_history()
        self._refresh_send_icon()

    def emit_user_message_only(self) -> None:
        """Submit text to the parent UI without starting a worker."""
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.submit_requested.emit(text)

    def _disconnect_worker(self) -> None:
        """Safely disconnect all signals from the current worker."""
        w = self._worker
        if w is None:
            return
        for sig in (w.chunk_ready, w.error_occurred, w.finished_signal):
            try:
                sig.disconnect()
            except TypeError:
                pass

    def auto_send(self, text: str) -> None:
        """Automatically send a message (used for AI interaction triggers)."""
        self._stop_worker()
        self._start_worker(text)

    def _apply_language(self) -> None:
        self._input.setPlaceholderText(self.i18n.t("beamplot_chat_placeholder"))
        self._new_chat_btn.setToolTip(self.i18n.t("beamplot_new_chat"))

    def _on_send(self) -> None:
        if self._worker and self._worker.isRunning():
            self._stop_worker()
            self._refresh_send_icon()
            return

        text = self._input.text().strip()
        if not text:
            return

        if self._external_submit:
            self._input.clear()
            self.submit_requested.emit(text)
            return

        self._input.clear()
        self._last_user_msg = text
        self.user_message_sent.emit(text)
        self._start_worker(text)

    def _start_worker(self, text: str) -> None:
        """Create one worker and bind callbacks to that exact instance."""
        selected_model = self._model_selector.current_value()
        self._last_user_msg = text
        self._last_answer = ""
        if not selected_model:
            self._emit_local_error_response(self.i18n.t("no_llm_configured"))
            return

        worker = _BeamplotChatWorker(
            text,
            self._context,
            selected_model,
            self.i18n.effective_output_lang,
            history=list(self._conversation_history),
        )
        self._worker = worker
        worker.chunk_ready.connect(lambda full, w=worker: self._on_chunk(w, full))
        worker.error_occurred.connect(self._show_error)
        worker.finished_signal.connect(lambda w=worker: self._on_finished(w))
        worker.start()
        self._refresh_send_icon()

    def _emit_local_error_response(self, message: str) -> None:
        """Render validation errors in the assistant bubble for the current turn."""
        self._last_answer = message
        self.response_ready.emit(message)
        if self._last_user_msg:
            self._conversation_history.append({"role": "user", "content": self._last_user_msg})
            self._conversation_history.append({"role": "assistant", "content": message})
            self.exchange_finished.emit(self._last_user_msg, message)
        self._refresh_send_icon()

    def _show_error(self, message: str) -> None:
        self._last_answer = message
        self.response_ready.emit(message)
        InfoBar.error(
            title=self.i18n.t("chat_error"),
            content=message,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self.window(),
        )

    def _on_chunk(self, worker: _BeamplotChatWorker, full: str) -> None:
        if worker is not self._worker:
            return
        self.response_ready.emit(full)
        self._last_answer = full

    def _on_finished(self, worker: _BeamplotChatWorker) -> None:
        if worker is not self._worker:
            return
        answer = getattr(self, "_last_answer", "")
        if self._last_user_msg and answer:
            self._conversation_history.append({"role": "user", "content": self._last_user_msg})
            self._conversation_history.append({"role": "assistant", "content": answer})
            self.exchange_finished.emit(self._last_user_msg, answer)
        self._worker = None
        self._refresh_send_icon()

    def _apply_theme(self) -> None:
        tm = self.tm
        self._box.setStyleSheet(f"""
            QFrame#chatInputBox {{
                background-color: {tm.bg_card};
                border: 1px solid {tm.border_light};
                border-radius: 14px;
            }}
            QLineEdit#chatInput {{
                background: transparent;
                border: none;
                color: {tm.text_primary};
                font-size: 14px;
                font-family: "{tm.font_family}";
                padding: 6px 4px;
            }}
            QPushButton#chatIconBtn, QPushButton#chatSendBtn {{
                background: transparent;
                border: none;
                border-radius: 8px;
                padding: 4px;
            }}
            QPushButton#chatIconBtn:hover, QPushButton#chatSendBtn:hover {{
                background-color: {tm.bg_hover};
            }}
        """)
        self._new_chat_btn.setIcon(svg_icon("new_task.svg", tm.text_secondary))
        self._refresh_send_icon()

    def _refresh_send_icon(self) -> None:
        w = self._worker
        running = bool(w and (w.isRunning() or not w.isFinished()))
        icon_name = "stop.svg" if running else "send.svg"
        color = "#f44336" if running else self.tm.text_primary
        self._send_btn.setIcon(svg_icon(icon_name, color))
        self._send_btn.setIconSize(QSize(16, 16))
