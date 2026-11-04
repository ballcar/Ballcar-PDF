"""เครื่องมือลายเซ็น (2.3): วาดลายเซ็นด้วยเมาส์/ปากกา และตรายางสำเร็จรูปพร้อมวันที่

ผลลัพธ์เป็นไฟล์ PNG พื้นใส — ใช้วางด้วยโหมดวางรูปเดิม (ลากย้าย/ย่อขยาย/Shift คงสัดส่วน)
และเก็บเข้าคลังลายเซ็นได้เหมือนรูปลายเซ็นทั่วไป
"""
from __future__ import annotations

import tempfile
import uuid
from datetime import date
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QPushButton, QRadioButton,
                               QVBoxLayout, QWidget)

from .i18n import t

INK = {"black": QColor(20, 20, 25), "blue": QColor(25, 60, 170)}
STAMP_COLORS = {"red": QColor(200, 30, 35), "blue": QColor(25, 70, 180), "green": QColor(20, 130, 60)}
THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
               "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def _temp_png(prefix: str) -> Path:
    return Path(tempfile.gettempdir()) / f"ballcar-{prefix}-{uuid.uuid4().hex[:8]}.png"


def thai_date(day: date | None = None) -> str:
    """4 พ.ย. 2569 (พ.ศ. แบบที่ออฟฟิศไทยใช้บนตรายาง)"""
    day = day or date.today()
    return f"{day.day} {THAI_MONTHS[day.month - 1]} {day.year + 543}"


# ---------------- วาดลายเซ็น ----------------

class _Pad(QWidget):
    """กระดาษสำหรับเซ็น — เก็บเส้นเป็นจุดๆ (ลบทีละเส้นได้ วาดคมทุกขนาด)"""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(560, 220)
        self.setCursor(Qt.CrossCursor)
        self.strokes: list[list[QPointF]] = []
        self.color = INK["black"]
        self.width_px = 3.0

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(255, 255, 255))
        p.setPen(QPen(QColor(200, 200, 200), 1, Qt.DashLine))
        base = self.height() - 50
        p.drawLine(30, base, self.width() - 30, base)          # เส้นบอกตำแหน่งเซ็น
        self._draw_strokes(p, 1.0)
        p.end()

    def _draw_strokes(self, p: QPainter, scale: float, offset=QPointF(0, 0)) -> None:
        p.setPen(QPen(self.color, self.width_px * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        for stroke in self.strokes:
            if len(stroke) == 1:
                p.drawPoint((stroke[0] - offset) * scale)
                continue
            path = QPainterPath((stroke[0] - offset) * scale)
            for pt in stroke[1:]:
                path.lineTo((pt - offset) * scale)
            p.drawPath(path)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self.strokes.append([e.position()])
            self.update()

    def mouseMoveEvent(self, e) -> None:
        if e.buttons() & Qt.LeftButton and self.strokes:
            self.strokes[-1].append(e.position())
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        self.changed.emit()

    def clear(self) -> None:
        self.strokes = []
        self.update()
        self.changed.emit()

    def undo(self) -> None:
        if self.strokes:
            self.strokes.pop()
            self.update()
            self.changed.emit()

    def bounds(self) -> QRectF:
        pts = [pt for s in self.strokes for pt in s]
        if not pts:
            return QRectF()
        xs, ys = [p.x() for p in pts], [p.y() for p in pts]
        pad = self.width_px * 2
        return QRectF(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + pad * 2,
                      max(ys) - min(ys) + pad * 2)

    def to_png(self, scale: float = 4.0) -> Path | None:
        """ลายเซ็นพื้นใส ตัดขอบว่างทิ้ง ความละเอียดสูง (ย่อขยายบน PDF แล้วยังคม)"""
        box = self.bounds()
        if box.isEmpty():
            return None
        image = QImage(QSize(int(box.width() * scale) + 2, int(box.height() * scale) + 2),
                       QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        p = QPainter(image)
        p.setRenderHint(QPainter.Antialiasing)
        self._draw_strokes(p, scale, box.topLeft())
        p.end()
        out = _temp_png("drawn-sig")
        image.save(str(out), "PNG")
        return out


class SignaturePadDialog(QDialog):
    """วาดลายเซ็นด้วยเมาส์/ปากกา/ทัชแพด แล้วใช้ทันทีหรือเก็บเข้าคลัง"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("sig.draw_title"))
        self.result_path: Path | None = None
        layout = QVBoxLayout(self)
        hint = QLabel(t("sig.draw_hint"))
        hint.setProperty("role", "hint")
        layout.addWidget(hint)
        self.pad = _Pad()
        layout.addWidget(self.pad, 1)

        tools = QHBoxLayout()
        self.ink = QButtonGroup(self)
        for key in ("black", "blue"):
            rb = QRadioButton(t(f"sig.ink.{key}"))
            rb.setChecked(key == "black")
            rb.toggled.connect(lambda on, k=key: on and self._set_ink(k))
            self.ink.addButton(rb)
            tools.addWidget(rb)
        tools.addSpacing(12)
        for label, width in ((t("sig.thin"), 2.0), (t("sig.medium"), 3.0), (t("sig.thick"), 5.0)):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, w=width: self._set_width(w))
            tools.addWidget(b)
        tools.addStretch(1)
        undo = QPushButton(t("sig.undo_stroke"))
        undo.clicked.connect(self.pad.undo)
        clear = QPushButton(t("sig.clear"))
        clear.clicked.connect(self.pad.clear)
        tools.addWidget(undo)
        tools.addWidget(clear)
        layout.addLayout(tools)

        name_row = QHBoxLayout()
        self.save_to_library = QCheckBox(t("sig.save_library"))
        self.save_to_library.setChecked(True)
        self.name = QLineEdit()
        self.name.setPlaceholderText(t("sig.name_placeholder"))
        name_row.addWidget(self.save_to_library)
        name_row.addWidget(self.name, 1)
        layout.addLayout(name_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.ok = buttons.addButton(t("sig.use"), QDialogButtonBox.AcceptRole)
        self.ok.setProperty("role", "primary")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.pad.changed.connect(self._sync)
        self.save_to_library.toggled.connect(self.name.setEnabled)
        self._sync()

    def _set_ink(self, key: str) -> None:
        self.pad.color = INK[key]
        self.pad.update()

    def _set_width(self, width: float) -> None:
        self.pad.width_px = width
        self.pad.update()

    def _sync(self) -> None:
        self.ok.setEnabled(bool(self.pad.strokes))

    def _accept(self) -> None:
        self.result_path = self.pad.to_png()
        if self.result_path:
            self.accept()


# ---------------- ตรายาง ----------------

STAMP_PRESETS = ["อนุมัติ", "ได้รับแล้ว", "สำเนาถูกต้อง", "จ่ายแล้ว", "ตรวจแล้ว", "ด่วน", "ยกเลิก"]


def make_stamp(text: str, color: QColor, sub: str = "", scale: float = 3.0) -> Path:
    """ตรายางกรอบสี่เหลี่ยมมุมมน ตัวหนาใหญ่ + บรรทัดรอง (เช่นวันที่) พื้นใส"""
    big = QFont("Leelawadee UI")
    big.setBold(True)
    big.setPixelSize(int(30 * scale))
    small = QFont("Leelawadee UI")
    small.setPixelSize(int(15 * scale))
    from PySide6.QtGui import QFontMetrics
    fm_big, fm_small = QFontMetrics(big), QFontMetrics(small)
    pad = int(14 * scale)
    text_w = max(fm_big.horizontalAdvance(text), fm_small.horizontalAdvance(sub) if sub else 0)
    width = text_w + pad * 2
    height = fm_big.height() + (fm_small.height() + int(2 * scale) if sub else 0) + pad
    border = 3.0 * scale
    image = QImage(QSize(int(width + border * 2), int(height + border * 2)), QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    outer = QRectF(border, border, width, height)
    p.setPen(QPen(color, border))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(outer, 8 * scale, 8 * scale)
    inner = outer.adjusted(border * 1.4, border * 1.4, -border * 1.4, -border * 1.4)
    p.setPen(QPen(color, border * 0.4))
    p.drawRoundedRect(inner, 6 * scale, 6 * scale)            # เส้นคู่แบบตรายางจริง
    p.setFont(big)
    top = outer.top() + pad / 2
    p.drawText(QRectF(outer.left(), top, width, fm_big.height()), Qt.AlignCenter, text)
    if sub:
        p.setFont(small)
        p.drawText(QRectF(outer.left(), top + fm_big.height(), width, fm_small.height()),
                   Qt.AlignCenter, sub)
    p.end()
    out = _temp_png("stamp")
    image.save(str(out), "PNG")
    return out


class StampDialog(QDialog):
    """เลือกข้อความตรายาง สี และใส่วันที่วันนี้ — เห็นตัวอย่างก่อนวาง"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("stamp.title"))
        self.result_path: Path | None = None
        self.result_text = ""
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel(t("stamp.pick")))
        self.presets = QListWidget()
        self.presets.addItems(STAMP_PRESETS)
        self.presets.setCurrentRow(0)
        self.presets.setFixedWidth(170)
        left.addWidget(self.presets)
        self.custom = QLineEdit()
        self.custom.setPlaceholderText(t("stamp.custom"))
        left.addWidget(self.custom)
        row.addLayout(left)

        right = QVBoxLayout()
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedSize(340, 180)        # ขนาดคงที่ (ภาพตัวอย่างไม่ดันหน้าต่างให้โตเรื่อยๆ)
        self.preview.setStyleSheet("background:#ffffff; border:1px solid #d0d0d0; border-radius:6px;")
        right.addWidget(self.preview)
        colors = QHBoxLayout()
        self.color_group = QButtonGroup(self)
        for key in STAMP_COLORS:
            rb = QRadioButton(t(f"stamp.color.{key}"))
            rb.setChecked(key == "red")
            rb.setProperty("key", key)
            self.color_group.addButton(rb)
            colors.addWidget(rb)
        right.addLayout(colors)
        self.with_date = QCheckBox(t("stamp.with_date", d=thai_date()))
        self.with_date.setChecked(True)
        right.addWidget(self.with_date)
        self.save_to_library = QCheckBox(t("sig.save_library"))
        right.addWidget(self.save_to_library)
        row.addLayout(right, 1)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        ok = buttons.addButton(t("stamp.place"), QDialogButtonBox.AcceptRole)
        ok.setProperty("role", "primary")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.presets.currentRowChanged.connect(lambda _r: (self.custom.clear(), self._render()))
        self.custom.textChanged.connect(lambda _t: self._render())
        self.color_group.buttonToggled.connect(lambda *_: self._render())
        self.with_date.toggled.connect(lambda _on: self._render())
        self._render()

    def text(self) -> str:
        custom = self.custom.text().strip()
        if custom:
            return custom
        item = self.presets.currentItem()
        return item.text() if item else ""

    def color(self) -> QColor:
        button = self.color_group.checkedButton()
        return STAMP_COLORS[button.property("key") if button else "red"]

    def _render(self) -> Path | None:
        text = self.text()
        if not text:
            self.preview.clear()
            return None
        path = make_stamp(text, self.color(), thai_date() if self.with_date.isChecked() else "")
        pix = QPixmap(str(path))
        self.preview.setPixmap(pix.scaled(self.preview.size() - QSize(20, 20),
                                          Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return path

    def _accept(self) -> None:
        self.result_path = self._render()
        self.result_text = self.text()
        if self.result_path:
            self.accept()
