"""หน้าต่างผู้ช่วยพิมพ์คำสั่ง (2.0)

พิมพ์แล้วเห็นทันทีว่าโปรแกรมเข้าใจว่าจะทำอะไร (ไม่ต้องกด OK แล้วค่อยรู้ว่าไม่เข้าใจ)
ไม่เข้าใจ -> มีคำสั่งใกล้เคียงให้กดเลือก · คำสั่งล่าสุด/ตัวอย่าง กดแล้วเติมให้เลย
ปุ่ม "ทำเลย" กดได้เฉพาะตอนเข้าใจคำสั่งแล้ว — ตัวอย่างที่เห็นคือการยืนยัน
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

from . import assistant
from .i18n import t


def _chip(text: str, on_click) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("role", "chip")
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(lambda: on_click(text))
    return button


class _FlowRow(QWidget):
    """แถวปุ่มเล็ก (chip) ขึ้นบรรทัดใหม่เองเมื่อเกินความกว้าง — ใช้กับคำแนะนำ/ล่าสุด"""

    def __init__(self, per_line: int = 3) -> None:
        super().__init__()
        self._per_line = per_line
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)

    def set_items(self, texts: list[str], on_click) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    w = item.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()
        row = None
        for n, text in enumerate(texts):
            if n % self._per_line == 0:
                row = QHBoxLayout()
                row.setSpacing(4)
                self._layout.addLayout(row)
            row.addWidget(_chip(text, on_click))
        if row is not None:
            row.addStretch(1)
        self.setVisible(bool(texts))


class AssistantDialog(QDialog):
    def __init__(self, parent=None, history: list[str] | None = None,
                 ai_ready: bool = False, ai_loading: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("ai.title"))
        self.setMinimumWidth(560)
        self.command = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        engine = self.engine = QLabel(t("ai.engine_ai") if ai_ready else
                                      t("ai.engine_loading") if ai_loading else t("ai.engine_rules"))
        engine.setProperty("role", "hint")
        layout.addWidget(engine)
        # AI กำลังโหลดเบื้องหลัง -> คอยดูจนพร้อม แล้วตีความคำที่พิมพ์ไว้ใหม่ด้วย AI
        self._ai_wait = QTimer(self)
        self._ai_wait.setInterval(300)
        self._ai_wait.timeout.connect(self._check_ai)
        if ai_loading and not ai_ready:
            self._ai_wait.start()

        self.input = QLineEdit()
        self.input.setPlaceholderText(t("ai.placeholder"))
        self.input.setObjectName("assistantInput")
        self.input.textChanged.connect(lambda: self._debounce.start())
        self.input.returnPressed.connect(self._run)
        layout.addWidget(self.input)

        # ตีความหลังหยุดพิมพ์แป๊บเดียว (AI จับความหมายใช้เวลานิดหน่อย ไม่ให้หน่วงทุกตัวอักษร)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self._update_preview)

        self.preview = QLabel()
        self.preview.setObjectName("assistantPreview")
        self.preview.setWordWrap(True)
        self.preview.setMinimumHeight(44)
        layout.addWidget(self.preview)

        self.suggest_title = QLabel(t("ai.try"))
        self.suggest_title.setProperty("role", "hint")
        layout.addWidget(self.suggest_title)
        self.suggestions = _FlowRow(per_line=2)
        layout.addWidget(self.suggestions)

        history = history or []
        self.recent_title = QLabel(t("ai.recent"))
        self.recent_title.setProperty("role", "hint")
        layout.addWidget(self.recent_title)
        self.recent = _FlowRow(per_line=2)
        self.recent.set_items(history[:6], self._use)
        layout.addWidget(self.recent)
        self.recent_title.setVisible(bool(history))

        examples_title = QLabel(t("ai.examples"))
        examples_title.setProperty("role", "hint")
        layout.addWidget(examples_title)
        self.examples = _FlowRow(per_line=2)
        # ตัวอย่างที่มีคำอธิบายในวงเล็บ ใส่เฉพาะตัวคำสั่ง
        self.examples.set_items([e.split("  ")[0].strip() for e in assistant.EXAMPLES
                                 if "·" not in e], self._use)
        layout.addWidget(self.examples)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.run_button = buttons.addButton(t("ai.run"), QDialogButtonBox.AcceptRole)
        self.run_button.setProperty("role", "primary")
        buttons.accepted.connect(self._run)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._intents = None
        self._update_preview()

    def _check_ai(self) -> None:
        from . import semantic
        if assistant.has_matcher():
            self._ai_wait.stop()
            self.engine.setText(t("ai.engine_ai"))
            self._update_preview()
        elif not semantic.loading():       # โหลดไม่สำเร็จ -> ใช้กฎต่อ
            self._ai_wait.stop()
            self.engine.setText(t("ai.engine_rules"))

    def _use(self, text: str) -> None:
        """กดคำแนะนำ/ตัวอย่าง -> เติมลงช่อง (แก้ต่อได้ก่อนกดทำเลย)"""
        self.input.setText(text)
        self.input.setFocus()
        self._update_preview()

    def _update_preview(self) -> None:
        text = self.input.text().strip()
        self._intents = assistant.parse_all(text) if text else None
        intents = self._intents
        ok = bool(intents) and not any(i.needs_online_ai for i in intents)
        self.run_button.setEnabled(ok)
        self.preview.setProperty("state", "ok" if ok else ("bad" if text else "idle"))
        if not text:
            self.preview.setText("")
        elif intents and not ok:
            online = next(i for i in intents if i.needs_online_ai)
            self.preview.setText(f"{online.preview}\n{t('ai.no_ai')}")
        elif ok:
            steps = intents[0].preview if len(intents) == 1 else "\n".join(
                f"{n}. {i.preview}" for n, i in enumerate(intents, start=1))
            self.preview.setText(f"{t('ai.will_do_live')} {steps}")
        else:
            self.preview.setText(t("ai.unknown_live"))
        near = assistant.suggest(text) if text and not intents else []
        self.suggestions.set_items(near, self._use)
        self.suggest_title.setVisible(bool(near))
        self.preview.style().unpolish(self.preview)
        self.preview.style().polish(self.preview)

    def _run(self) -> None:
        self._debounce.stop()
        self._update_preview()
        if self.run_button.isEnabled():
            self.command = self.input.text().strip()
            self.accept()
