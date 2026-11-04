"""แผงความคิดเห็น (2.2) — รวมโน้ต ไฮไลต์ ขีดเส้น และรูปวาดทั้งไฟล์ไว้ที่เดียว

คลิกรายการ = ไปหน้านั้น · ดับเบิลคลิกโน้ต = แก้ข้อความ · ปุ่มลบ = เอาออก
ไฟล์นี้ดูแลแค่การแสดงผลและส่งสัญญาณ งานจริงอยู่ใน pdfops (ย้อนกลับด้วย Ctrl+Z ได้)
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout, QWidget)

from . import icons
from .i18n import t

KIND_ICON = {"note": "sticky-note", "text": "type", "highlight": "highlighter",
             "underline": "highlighter", "strike": "highlighter", "drawing": "pen-tool"}


class CommentsPanel(QWidget):
    addRequested = Signal()            # ปุ่ม "+ เพิ่มโน้ต"
    goRequested = Signal(dict)         # คลิกรายการ -> ไปหน้านั้น
    editRequested = Signal(dict)       # ดับเบิลคลิก / ปุ่มแก้ไข
    deleteRequested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("commentsPanel")
        self.setMinimumWidth(200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setProperty("role", "header")
        head.addWidget(self.title, 1)
        self.add_button = QPushButton()
        self.add_button.setProperty("role", "primary")
        self.add_button.clicked.connect(self.addRequested.emit)
        head.addWidget(self.add_button)
        layout.addLayout(head)

        self.list = QListWidget()
        self.list.setObjectName("commentList")
        self.list.setWordWrap(True)
        self.list.setIconSize(QSize(18, 18))
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)   # ข้อความยาวตัดบรรทัด
        self.list.itemClicked.connect(lambda item: self.goRequested.emit(item.data(Qt.UserRole)))
        self.list.itemDoubleClicked.connect(
            lambda item: self.editRequested.emit(item.data(Qt.UserRole)))
        self.list.currentItemChanged.connect(lambda *_: self._sync_buttons())
        layout.addWidget(self.list, 1)

        self.empty = QLabel()
        self.empty.setProperty("role", "hint")
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)

        row = QHBoxLayout()
        self.edit_button = QPushButton()
        self.edit_button.clicked.connect(lambda: self._emit_current(self.editRequested))
        self.delete_button = QPushButton()
        self.delete_button.clicked.connect(lambda: self._emit_current(self.deleteRequested))
        row.addWidget(self.edit_button)
        row.addWidget(self.delete_button)
        layout.addLayout(row)
        self.retranslate()
        self.set_comments([])

    def retranslate(self) -> None:
        self.add_button.setText("+ " + t("cm.add"))
        self.edit_button.setText(t("cm.edit"))
        self.delete_button.setText(t("cm.delete"))
        self.empty.setText(t("cm.empty"))
        self.title.setText(t("cm.title", n=self.list.count()))

    def set_comments(self, comments: list[dict], select: tuple | None = None) -> None:
        """select = (page, xref) ของรายการที่จะเลือกไว้ (เช่นโน้ตที่เพิ่งแปะ)"""
        self.list.clear()
        for c in comments:
            kind = t(f"cm.kind.{c['kind']}")
            head = t("cm.page", n=c["page"] + 1) + " · " + kind
            if c["author"]:
                head += " · " + c["author"]
            if c["floating"] is not None:
                head += " · " + t("cm.unsaved")
            body = c["text"] or t("cm.no_text")
            if len(body) > 90:                    # รายการยาวเกิน 2-3 บรรทัด อ่านเต็มที่ tooltip
                body = body[:87] + "…"
            item = QListWidgetItem(icons.icon(KIND_ICON.get(c["kind"], "sticky-note")),
                                   f"{head}\n{body}")
            item.setData(Qt.UserRole, c)
            item.setToolTip(c["text"])
            self.list.addItem(item)
            if select and c["xref"] is not None and (c["page"], c["xref"]) == select:
                self.list.setCurrentItem(item)
        self.title.setText(t("cm.title", n=len(comments)))
        self.empty.setVisible(not comments)
        self._sync_buttons()

    def current(self) -> dict | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _emit_current(self, signal) -> None:
        c = self.current()
        if c is not None:
            signal.emit(c)

    def _sync_buttons(self) -> None:
        c = self.current()
        self.edit_button.setEnabled(bool(c and c["xref"] is not None
                                         and c["kind"] in ("note", "text", "highlight",
                                                           "underline", "strike")))
        self.delete_button.setEnabled(c is not None)
