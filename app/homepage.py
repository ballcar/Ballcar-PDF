"""หน้าแรก (2.0) — แสดงแทนหน้าเอกสารตอนยังไม่ได้เปิดไฟล์

มีปุ่มงานหลัก (เปิดไฟล์ / รวมไฟล์ / ประมวลผลหลายไฟล์) และรายการไฟล์ที่เปิดล่าสุด
สีมาจากธีมกลาง (theme.py) ผ่าน objectName / property role
"""
from __future__ import annotations

import time

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
                               QPushButton, QToolButton, QVBoxLayout, QWidget)

from . import recent


class HomePage(QWidget):
    open_requested = Signal(str)          # คลิกไฟล์ล่าสุด -> หน้าต่างหลักเปิดไฟล์นี้

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("homePage")
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QHBoxLayout(self)
        outer.addStretch(1)
        column = QWidget()
        column.setMaximumWidth(760)
        outer.addWidget(column, 4)
        outer.addStretch(1)

        layout = QVBoxLayout(column)
        layout.setContentsMargins(24, 40, 24, 24)
        layout.setSpacing(10)

        self.title = QLabel()
        self.title.setProperty("role", "homeTitle")
        layout.addWidget(self.title)
        self.subtitle = QLabel()
        self.subtitle.setProperty("role", "hint")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self._cards = QHBoxLayout()
        self._cards.setSpacing(10)
        layout.addSpacing(12)
        layout.addLayout(self._cards)

        layout.addSpacing(18)
        head = QHBoxLayout()
        self.recent_title = QLabel()
        self.recent_title.setProperty("role", "header")
        head.addWidget(self.recent_title)
        head.addStretch(1)
        self.clear_button = QToolButton()
        self.clear_button.setObjectName("linkButton")
        self.clear_button.setAutoRaise(True)
        self.clear_button.clicked.connect(self._clear_recent)
        head.addWidget(self.clear_button)
        layout.addLayout(head)

        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recentList")
        self.recent_list.setIconSize(QSize(22, 22))
        # ที่อยู่ไฟล์ยาว -> ย่อตรงกลางด้วย … แทนแถบเลื่อนแนวนอน (ที่อยู่เต็มอยู่ใน tooltip)
        self.recent_list.setTextElideMode(Qt.ElideMiddle)
        self.recent_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # คลิกครั้งเดียวเปิดเลย (ต่อ itemActivated ด้วยจะเปิดซ้ำตอนดับเบิลคลิก)
        self.recent_list.itemClicked.connect(self._open_item)
        self.recent_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.recent_list.customContextMenuRequested.connect(self._recent_menu)
        layout.addWidget(self.recent_list, 1)

        self.empty = QLabel()
        self.empty.setProperty("role", "hint")
        layout.addWidget(self.empty)
        layout.addStretch(0)     # ยังไม่มีไฟล์ล่าสุด (รายการซ่อน) -> ดันทุกอย่างขึ้นบน ไม่กระจายห่างกัน

        self._texts: dict[str, str] = {}

    def set_texts(self, **texts: str) -> None:
        """title, subtitle, recent, clear, empty, remove, folder"""
        self._texts = texts
        self.title.setText(texts.get("title", ""))
        self.subtitle.setText(texts.get("subtitle", ""))
        self.recent_title.setText(texts.get("recent", ""))
        self.clear_button.setText(texts.get("clear", ""))
        self.empty.setText(texts.get("empty", ""))
        self.refresh()

    def set_actions(self, actions: list) -> None:
        """ปุ่มงานหลัก — ผูกกับ QAction ตัวเดียวกับเมนู [(action, ชื่อบนการ์ด, คำอธิบายสั้น), ...]"""
        while self._cards.count():
            item = self._cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for action, title, detail in actions:
            # ชื่อตัวหนา + คำอธิบายสีจาง (ข้อความบน QPushButton ทำได้แค่แบบเดียวทั้งปุ่ม จึงวาง label ข้างใน)
            card = QPushButton()
            card.setProperty("role", "card")
            card.setProperty("title", title)
            card.setAccessibleName(f"{title} — {detail}")
            card.setToolTip(detail)
            card.setMinimumHeight(64)
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 10, 14, 10)
            row.setSpacing(12)
            icon = QLabel()
            icon.setPixmap(action.icon().pixmap(QSize(28, 28)))
            texts = QVBoxLayout()
            texts.setSpacing(2)
            name = QLabel(title)
            name.setProperty("role", "cardTitle")
            sub = QLabel(detail)
            sub.setProperty("role", "hint")
            texts.addWidget(name)
            texts.addWidget(sub)
            row.addWidget(icon)
            row.addLayout(texts, 1)
            for label in (icon, name, sub):
                label.setAttribute(Qt.WA_TransparentForMouseEvents)   # คลิกทะลุไปที่การ์ด
            for label in (name, sub):
                label.ensurePolished()       # ให้ขนาดคิดจากฟอนต์ตัวหนาของธีมแล้ว
            card.setMinimumWidth(row.sizeHint().width())   # ปุ่มไม่คิดขนาดจาก label ข้างใน -> กันข้อความถูกตัด
            card.setCursor(Qt.PointingHandCursor)
            card.clicked.connect(action.trigger)
            self._cards.addWidget(card, 1)

    def refresh(self) -> None:
        """อ่านรายการไฟล์ล่าสุดใหม่ (เรียกทุกครั้งที่หน้าแรกถูกแสดง)"""
        self.recent_list.clear()
        files = recent.items()
        from PySide6.QtWidgets import QApplication, QStyle
        icon = QApplication.style().standardIcon(QStyle.SP_FileIcon)
        for path in files:
            try:
                when = time.strftime("%d/%m/%Y %H:%M", time.localtime(path.stat().st_mtime))
            except OSError:
                when = ""
            item = QListWidgetItem(icon, f"{path.name}\n{path.parent}   ·   {when}")
            item.setData(Qt.UserRole, str(path))
            item.setToolTip(str(path))
            self.recent_list.addItem(item)
        self.recent_list.setVisible(bool(files))
        self.clear_button.setVisible(bool(files))
        self.empty.setVisible(not files)

    def _open_item(self, item: QListWidgetItem) -> None:
        self.open_requested.emit(item.data(Qt.UserRole))

    def _recent_menu(self, pos) -> None:
        item = self.recent_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.addAction(self._texts.get("remove", "Remove"),
                       lambda: (recent.remove(item.data(Qt.UserRole)), self.refresh()))
        menu.addAction(self._texts.get("folder", "Open folder"),
                       lambda: _reveal(item.data(Qt.UserRole)))
        menu.exec(self.recent_list.mapToGlobal(pos))

    def _clear_recent(self) -> None:
        recent.clear()
        self.refresh()


def _reveal(path: str) -> None:
    """เปิด Explorer ที่ไฟล์นั้น"""
    import subprocess
    import sys
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", path])
