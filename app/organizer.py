"""จัดเรียงหน้าแบบตาราง (2.1) — แสดงทุกหน้าเป็นภาพใหญ่เรียงเป็นตาราง แทนพื้นที่เอกสาร

ลากสลับลำดับ / เลือกหลายหน้า (Ctrl, Shift, ลากคลุม, Ctrl+A) แล้วหมุน ลบ แทรก แยกเป็นไฟล์
งานจริง (หมุน/ลบ/ย้าย) ทำผ่านคำสั่งเดียวกับแถบภาพย่อใน main.py — ย้อนกลับด้วย Ctrl+Z ได้เหมือนกัน
ไฟล์นี้ดูแลแค่การแสดงผลและส่งสัญญาณ
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListView, QListWidget,
                               QListWidgetItem, QSizePolicy, QSlider, QStyledItemDelegate, QStyleOptionViewItem,
                               QToolButton, QVBoxLayout, QWidget)

MIN_WIDTH, MAX_WIDTH, DEFAULT_WIDTH = 110, 360, 180   # ความกว้างภาพหน้า (พิกเซล)


class _PageDelegate(QStyledItemDelegate):
    """ภาพหน้าอยู่บน เลขหน้าอยู่ใต้ภาพ (โหมด List แบบไหลเป็นแถวเพื่อให้ลากสลับลำดับได้จริง)"""

    def initStyleOption(self, option: QStyleOptionViewItem, index) -> None:
        super().initStyleOption(option, index)
        option.decorationPosition = QStyleOptionViewItem.Top
        option.displayAlignment = Qt.AlignHCenter | Qt.AlignTop


class PageGrid(QListWidget):
    """ตารางภาพหน้า — ลากวางเปลี่ยนลำดับ แล้วส่ง orderChanged([index เดิมตามลำดับใหม่])"""

    orderChanged = Signal(list)
    pageActivated = Signal(int)        # ดับเบิลคลิก = ไปดูหน้านั้น
    zoomRequested = Signal(int)        # Ctrl+ล้อเมาส์ (+1 ใหญ่ขึ้น / -1 เล็กลง)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pageGrid")
        # ใช้ ListMode + ไหลซ้ายไปขวาแล้วขึ้นแถวใหม่ (IconMode ลากแล้วแค่ย้ายตำแหน่งภาพ ไม่เปลี่ยนลำดับ)
        self.setViewMode(QListView.ListMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.Adjust)
        self.setUniformItemSizes(True)
        self.setSpacing(10)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setItemDelegate(_PageDelegate(self))
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.model().rowsMoved.connect(self._on_rows_moved)
        self.itemDoubleClicked.connect(lambda item: self.pageActivated.emit(self.row(item)))

    def set_pages(self, pixmaps: list[QPixmap], label: str, selected: list[int]) -> None:
        """label = รูปแบบข้อความใต้ภาพ เช่น "หน้า {n}" """
        self.blockSignals(True)
        self.clear()
        width = max((p.width() for p in pixmaps), default=DEFAULT_WIDTH)
        tallest = max((p.height() for p in pixmaps), default=DEFAULT_WIDTH)
        self.setIconSize(QSize(width, tallest))
        self.setGridSize(QSize(width + 24, tallest + 40))
        for i, pix in enumerate(pixmaps):
            icon = QIcon(pix)
            icon.addPixmap(pix, QIcon.Selected)     # หน้าที่เลือกไม่ย้อมสีทับภาพ (มีกรอบบอกแทน)
            item = QListWidgetItem(icon, label.format(n=i + 1))
            item.setData(Qt.UserRole, i)
            item.setTextAlignment(Qt.AlignHCenter)
            self.addItem(item)
        for row in selected:
            if 0 <= row < self.count():
                self.item(row).setSelected(True)
        if selected and 0 <= selected[0] < self.count():
            self.setCurrentRow(selected[0], self.selectionModel().SelectionFlag.NoUpdate)
            self.scrollToItem(self.item(selected[0]))
        self.blockSignals(False)

    def selected_rows(self) -> list[int]:
        return sorted(i.row() for i in self.selectedIndexes())

    def _on_rows_moved(self, *_args) -> None:
        order = [self.item(r).data(Qt.UserRole) for r in range(self.count())]
        if None not in order and order != sorted(order):
            QTimer.singleShot(0, lambda: self.orderChanged.emit(order))   # ให้ Qt จบการลากก่อน

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            self.zoomRequested.emit(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)


class Organizer(QWidget):
    """หน้าจัดเรียงหน้า: แถบคำสั่งด้านบน + ตารางภาพหน้า"""

    doneRequested = Signal()
    sizeChanged = Signal(int)          # ความกว้างภาพหน้าใหม่ (ให้ main.py render ใหม่)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("organizer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        bar.setObjectName("organizerBar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        self._bar = QHBoxLayout(bar)
        self._bar.setContentsMargins(12, 6, 12, 6)
        self._bar.setSpacing(6)
        self.title = QLabel()
        self.title.setProperty("role", "panelTitle")
        self._bar.addWidget(self.title)
        self.hint = QLabel()
        self.hint.setProperty("role", "hint")
        # คำแนะนำยาว: หน้าต่างแคบก็ตัดได้ ไม่ดันพื้นที่เอกสาร/แถบภาพย่อให้แคบลง
        self.hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.hint.setMinimumWidth(0)
        self._bar.addWidget(self.hint, 1)
        self._buttons = QHBoxLayout()
        self._buttons.setSpacing(4)
        self._bar.addLayout(self._buttons)
        self.zoom = QSlider(Qt.Horizontal)
        self.zoom.setRange(MIN_WIDTH, MAX_WIDTH)
        self.zoom.setValue(DEFAULT_WIDTH)
        self.zoom.setFixedWidth(120)
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(200)          # ลากแถบเลื่อนไม่ render ทุกพิกเซล
        self._zoom_timer.timeout.connect(lambda: self.sizeChanged.emit(self.zoom.value()))
        self.zoom.valueChanged.connect(lambda _v: self._zoom_timer.start())
        self._bar.addWidget(self.zoom)
        self.done_button = QToolButton()
        self.done_button.setObjectName("organizerDone")
        self.done_button.setCursor(Qt.PointingHandCursor)
        self.done_button.clicked.connect(self.doneRequested.emit)
        self._bar.addWidget(self.done_button)
        layout.addWidget(bar)

        self.grid = PageGrid()
        self.grid.zoomRequested.connect(self._step_zoom)
        layout.addWidget(self.grid, 1)

    def set_texts(self, title: str, hint: str, done: str, zoom_tip: str) -> None:
        self.title.setText(title)
        self.hint.setText(hint)
        self.done_button.setText(done)
        self.zoom.setToolTip(zoom_tip)

    def set_actions(self, actions: list) -> None:
        """ปุ่มคำสั่งบนแถบ — ใช้ QAction ตัวเดียวกับเมนู (ทำงานกับหน้าที่เลือกในตาราง)"""
        while self._buttons.count():
            item = self._buttons.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for action in actions:
            if action is None:
                continue
            button = QToolButton()
            button.setDefaultAction(action)
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setIconSize(QSize(22, 22))
            button.setAutoRaise(True)
            self._buttons.addWidget(button)

    def page_width(self) -> int:
        return self.zoom.value()

    def _step_zoom(self, direction: int) -> None:
        self.zoom.setValue(self.zoom.value() + direction * 30)
