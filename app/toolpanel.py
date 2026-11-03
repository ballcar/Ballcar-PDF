"""แถบเครื่องมือด้านซ้าย (2.0) — รวมเครื่องมือทั้งหมดแบ่งหมวด + ช่องค้นหาเครื่องมือ

ปุ่มทุกปุ่มสั่งงาน QAction ตัวเดียวกับเมนู และเปิด/ปิดใช้งานตาม action อัตโนมัติ
(เปลี่ยนภาษาแล้วหน้าต่างหลักสร้างรายการใหม่ทั้งหมด)
สีมาจากธีมกลาง (theme.py) ผ่าน objectName / property role
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)


def _plain(text: str) -> str:
    """ข้อความสำหรับค้นหา: ตัด & (ปุ่มลัด) และ … ออก ตัวพิมพ์เล็ก"""
    return text.replace("&", "").replace("…", "").replace("...", "").strip().lower()


def short_name(text: str) -> str:
    """ชื่อสั้นสำหรับแถบด้านซ้าย (แถบแคบ): ตัด emoji นำหน้า วงเล็บอธิบาย และ … ออก

    'แทรกรูปภาพ (ลากย้าย/ย่อขยายได้)…' -> 'แทรกรูปภาพ'   '🖍 ไฮไลต์' -> 'ไฮไลต์'
    ชื่อเต็มยังอยู่ใน tooltip
    """
    text = text.replace("&", "").replace("…", "").replace("...", "").strip()
    while text and not (text[0].isalnum()):
        text = text[1:].lstrip()            # emoji / สัญลักษณ์นำหน้า (ไอคอนแสดงอยู่แล้ว)
    if " (" in text and text.endswith(")"):
        text = text[:text.rindex(" (")]
    return text.strip()


class ToolButton(QToolButton):
    """ปุ่มในแถบ — สั่งงาน action เดียวกับเมนู แต่ใช้ชื่อสั้นของตัวเอง

    ไม่ใช้ setDefaultAction เพราะปุ่มจะลอกชื่อเต็มกลับมาทุกครั้งที่ action เปลี่ยนสถานะ
    sync เป็นเมธอดของปุ่ม: ปุ่มถูกลบ (สร้างรายการใหม่) Qt ตัดการเชื่อมให้เอง
    """

    def __init__(self, action) -> None:
        super().__init__()
        self.action = action
        self.setIcon(action.icon())
        self.setText(short_name(action.text()))
        self.setToolTip(action.text().replace("&", ""))      # ชื่อเต็ม
        self.setProperty("role", "tool")
        self.setIconSize(QSize(ToolPanel.ICON_SIZE, ToolPanel.ICON_SIZE))
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAutoRaise(True)
        self.clicked.connect(action.trigger)
        action.changed.connect(self.sync)
        self.sync()

    def sync(self) -> None:
        self.setEnabled(self.action.isEnabled())


class ToolPanel(QWidget):
    WIDTH = 236
    COLLAPSED_WIDTH = 54       # ยุบแล้วเหลือแถบไอคอน (ชื่อเครื่องมือดูได้จาก tooltip)
    ICON_SIZE = 20

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("toolPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(self.WIDTH)
        self.collapsed = False
        self.on_collapse_changed = None     # หน้าต่างหลักผูกไว้จำค่า

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel()
        self.title.setProperty("role", "panelTitle")
        header.addWidget(self.title, 1)
        self.collapse_button = QToolButton()
        self.collapse_button.setObjectName("collapseButton")
        self.collapse_button.setAutoRaise(True)
        self.collapse_button.clicked.connect(lambda: self.set_collapsed(not self.collapsed))
        header.addWidget(self.collapse_button)
        layout.addLayout(header)

        self.search = QLineEdit()
        self.search.setObjectName("toolSearch")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self.run_first_match)
        layout.addWidget(self.search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._body = QWidget()
        self._body.setObjectName("toolPanelBody")
        self._list = QVBoxLayout(self._body)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(1)
        scroll.setWidget(self._body)
        layout.addWidget(scroll, 1)

        self.empty = QLabel()
        self.empty.setProperty("role", "hint")
        self.empty.setWordWrap(True)
        self.empty.hide()
        layout.addWidget(self.empty)

        self._groups: list[tuple[QLabel, list[QToolButton]]] = []
        self._tips = ("", "")
        self._apply_collapsed()

    def set_texts(self, title: str, placeholder: str, empty: str,
                  collapse_tip: str = "", expand_tip: str = "") -> None:
        self.title.setText(title)
        self.search.setPlaceholderText(placeholder)
        self.empty.setText(empty)
        self._tips = (collapse_tip, expand_tip)
        self._apply_collapsed()

    def set_collapsed(self, collapsed: bool) -> None:
        """ยุบเหลือแถบไอคอนแคบๆ / ขยายกลับเป็นแถบเต็ม (มีชื่อเครื่องมือ + ช่องค้นหา)"""
        if collapsed == self.collapsed:
            return
        self.collapsed = collapsed
        if collapsed:
            self.search.clear()          # ยุบแล้วต้องเห็นเครื่องมือครบทุกตัว
        self._apply_collapsed()
        if self.on_collapse_changed:
            self.on_collapse_changed(collapsed)

    def _apply_collapsed(self) -> None:
        collapsed = self.collapsed
        self.setFixedWidth(self.COLLAPSED_WIDTH if collapsed else self.WIDTH)
        self.layout().setContentsMargins(*((4, 8, 4, 8) if collapsed else (8, 8, 8, 8)))
        self.title.setVisible(not collapsed)
        self.search.setVisible(not collapsed)
        self.collapse_button.setText("»" if collapsed else "«")
        self.collapse_button.setToolTip(self._tips[1] if collapsed else self._tips[0])
        for header, buttons in self._groups:
            # ยุบแล้วซ่อนชื่อหมวด เหลือเส้นคั่นระหว่างหมวดแทน
            header.setProperty("collapsed", collapsed)
            header.setText("" if collapsed else header.property("full_text"))
            header.style().unpolish(header)
            header.style().polish(header)
            for button in buttons:
                button.setToolButtonStyle(Qt.ToolButtonIconOnly if collapsed
                                          else Qt.ToolButtonTextBesideIcon)

    def set_groups(self, groups: list[tuple[str, list]]) -> None:
        """สร้างรายการใหม่ทั้งหมด — groups: [(ชื่อหมวด, [QAction, ...]), ...]"""
        while self._list.count():
            item = self._list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._groups = []
        for title, actions in groups:
            actions = [a for a in actions if a is not None]
            if not actions:
                continue
            header = QLabel(title)
            header.setProperty("role", "toolGroup")
            header.setProperty("full_text", title)
            self._list.addWidget(header)
            buttons = []
            for action in actions:
                button = ToolButton(action)
                self._list.addWidget(button)
                buttons.append(button)
            self._groups.append((header, buttons))
        self._list.addStretch(1)
        self._filter(self.search.text())
        self._apply_collapsed()

    def visible_buttons(self) -> list[QToolButton]:
        return [b for _, buttons in self._groups for b in buttons if not b.isHidden()]

    def _filter(self, text: str) -> None:
        """ซ่อนเครื่องมือที่ชื่อไม่ตรงกับคำค้น (ค้นได้ทั้งชื่อเครื่องมือและชื่อหมวด)"""
        words = _plain(text).split()
        found = 0
        for header, buttons in self._groups:
            group_name = _plain(header.property("full_text") or header.text())
            group_hit = all(w in group_name for w in words)
            shown = 0
            for button in buttons:
                name = _plain(button.action.text()) + " " + group_name
                hit = not words or group_hit or all(w in name for w in words)
                button.setHidden(not hit)
                shown += hit
            header.setHidden(shown == 0)
            found += shown
        self.empty.setHidden(found > 0)

    def run_first_match(self) -> None:
        """กด Enter ในช่องค้นหา = ใช้เครื่องมือแรกที่ตรง (ที่ใช้งานได้ตอนนี้)"""
        if not self.search.text().strip():
            return
        for button in self.visible_buttons():
            if button.action.isEnabled():
                button.action.trigger()
                return

    def focus_search(self) -> None:
        self.show()
        self.set_collapsed(False)      # ยุบอยู่ ช่องค้นหาซ่อนอยู่ — ขยายก่อน
        self.search.setFocus()
        self.search.selectAll()
