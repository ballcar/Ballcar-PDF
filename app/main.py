"""Ballcar PDF — หน้าต่างหลัก"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import fitz

from PySide6.QtCore import Qt, QRect, QSize, QTimer, Signal
from PySide6.QtGui import (QAction, QColor, QFont, QIcon, QKeySequence, QPageLayout,
                          QPageSize, QPainter, QPixmap, QTransform)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QToolButton,
    QPushButton, QSplitter, QStatusBar, QToolBar, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

if __package__ in (None, ""):  # รันตรงๆ ด้วย python app/main.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app import assistant, autosave, batch, errorlog, i18n, library, pdfops, updater
    from app.i18n import t
    from app.pdfops import PdfDocument, merge_files, parse_page_ranges
    from app.viewer import PageViewer, pixmap_to_qimage
else:
    from . import assistant, autosave, batch, errorlog, i18n, library, pdfops, updater
    from .i18n import t
    from .pdfops import PdfDocument, merge_files, parse_page_ranges
    from .viewer import PageViewer, pixmap_to_qimage

APP_NAME = "Ballcar PDF"

_ICON_CACHE: dict[str, QIcon] = {}


def emoji_icon(emoji: str) -> QIcon:
    """ทำไอคอนเมนูจากอิโมจิ (วาดลง pixmap) — ไม่ต้องแนบไฟล์ไอคอนเพิ่ม

    วาดเป็น QIcon แทนการใส่อิโมจิไว้หน้าข้อความ เพราะเมนูจะจัดไอคอนเป็นคอลัมน์
    ทำให้ตัวหนังสือเรียงตรงกันสวยงาม
    """
    if emoji not in _ICON_CACHE:
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        font = QFont("Segoe UI Emoji")
        font.setPixelSize(int(size * 0.78))
        painter.setFont(font)
        painter.drawText(QRect(0, 0, size, size), Qt.AlignCenter, emoji)
        painter.end()
        _ICON_CACHE[emoji] = QIcon(pixmap)
    return _ICON_CACHE[emoji]


COMBINE_FLAG = "--combine"


def pdf_files_from_argv(argv) -> list[str]:
    """ไฟล์ .pdf ทั้งหมดที่มีอยู่จริงจาก argument (Windows ส่งมาตอนคลิกขวาหลายไฟล์)"""
    files = []
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue          # เป็นสวิตช์ ไม่ใช่ชื่อไฟล์
        candidate = Path(arg)
        if candidate.suffix.lower() == ".pdf" and candidate.exists():
            files.append(str(candidate))
    return files


def initial_file_from_argv(argv) -> str | None:
    """หาไฟล์ .pdf ตัวแรกที่มีอยู่จริงจาก argument (ที่ Windows ส่งมาตอนดับเบิลคลิก)"""
    files = pdf_files_from_argv(argv)
    return files[0] if files else None


def app_version() -> str:
    """อ่านเวอร์ชันจาก version.json (ถูกแพ็กไปกับ .exe ด้วย)"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    try:
        return json.loads((base / "version.json").read_text(encoding="utf-8"))["version"]
    except Exception:
        return "1.0.0"


def app_icon_path() -> Path | None:
    """หาไฟล์ไอคอน — ตอนแพ็กเป็น .exe ไฟล์จะถูกแตะไว้ใน sys._MEIPASS"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    candidate = base / "logo" / "Ballcar PDF.ico"
    return candidate if candidate.exists() else None


# ที่เก็บรูป QR สนับสนุน — รองรับหลายที่/หลายนามสกุล จะได้ไม่ต้องจำว่าวางไว้ตรงไหน
QR_CANDIDATES = [
    ("qr_code", "promptpay2.png"), ("qr_code", "promptpay2.jpg"),
    ("qr_code", "promptpay.png"), ("qr_code", "promptpay.jpg"),
    ("logo", "promptpay.png"), ("logo", "promptpay.jpg"),
]


def promptpay_qr_path() -> Path | None:
    """รูป QR พร้อมเพย์สำหรับสนับสนุนผู้พัฒนา (ไม่มีไฟล์ก็ไม่เป็นไร แค่ไม่แสดงรูป)"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for folder, name in QR_CANDIDATES:
        candidate = base / folder / name
        if candidate.exists():
            return candidate
    return None


# อีเมลรับแจ้งปัญหา/ข้อเสนอแนะ (แสดงในหน้าต่างเกี่ยวกับโปรแกรม)
SUPPORT_EMAIL = "chayakul_b@yahoo.com"

APP_VERSION = app_version()

PDF_FILTER = "ไฟล์ PDF (*.pdf)"


def style_action_bar(bar, name: str, bg: str, border: str) -> None:
    """จัดสไตล์แถบเครื่องมือ (ลายเซ็น/ข้อความ/ไฮไลต์) — ปุ่มพื้นขาวตัวหนังสือเข้ม เห็นชัด

    ต้องกำหนดสไตล์ปุ่มเอง ไม่งั้นพื้นหลังสีของแถบจะตกทอดไปที่ปุ่มจนตัวหนังสือจางมองไม่เห็น
    """
    bar.setObjectName(name)
    bar.setStyleSheet(f"""
        QWidget#{name} {{ background:{bg}; border-bottom:1px solid {border}; }}
        QWidget#{name} QLabel {{ background:transparent; }}
        QWidget#{name} QPushButton {{
            background:#ffffff; color:#1a1a1a; border:1px solid {border};
            border-radius:4px; padding:4px 12px; font-weight:500;
        }}
        QWidget#{name} QPushButton:hover {{ background:#f0f4ff; border-color:#5b9bd5; }}
        QWidget#{name} QPushButton:pressed {{ background:#e0e8f5; }}
    """)
IMAGE_FILTER = "ไฟล์รูป (*.png *.gif *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)"
THUMB_ZOOM = 0.22


def pdf_paths_from_mime(mime) -> list[str]:
    """ไฟล์ .pdf ที่ลากมาจากภายนอก (Explorer) — คืน list ว่างถ้าไม่ใช่ไฟล์ PDF"""
    if not mime or not getattr(mime, "hasUrls", None) or not mime.hasUrls():
        return []      # ไม่ใช่การลากไฟล์ (หรือ mime แปลกจากโปรแกรมอื่น)
    paths = []
    for url in mime.urls():
        local = url.toLocalFile()      # คืนเป็น / ต้องแปลงเป็นรูปแบบ Windows (\)
        if local.lower().endswith(".pdf") and Path(local).exists():
            paths.append(str(Path(local)))
    return paths


TEXT_HISTORY_KEY = "text_history"
TEXT_HISTORY_MAX = 40


def text_history() -> list[str]:
    """ข้อความที่เคยพิมพ์ล่าสุด (ใหม่สุดอยู่หน้า) — เก็บใน settings.json"""
    items = i18n.get_setting(TEXT_HISTORY_KEY, []) or []
    return [str(x) for x in items if str(x).strip()][:TEXT_HISTORY_MAX]


_THAI_MONTHS = ("มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
                "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม")


def date_suggestions() -> list[str]:
    """วันที่วันนี้ในรูปแบบที่ใช้บ่อย — มีให้เลือกตั้งแต่ครั้งแรกที่ใช้ ไม่ต้องรอมีประวัติ"""
    from datetime import date

    today = date.today()
    be = today.year + 543          # พ.ศ.
    return [
        f"{today.day:02d}/{today.month:02d}/{today.year}",
        f"{today.day:02d}/{today.month:02d}/{be}",
        f"{today.day} {_THAI_MONTHS[today.month - 1]} {be}",
        today.strftime("%Y-%m-%d"),
    ]


def remember_text(value: str) -> None:
    """จำข้อความที่พิมพ์ไว้ให้เลือกใช้ครั้งหน้า (ไม่เก็บข้อความหลายบรรทัด/ยาวเกินไป)"""
    value = (value or "").strip()
    if not value or "\n" in value or len(value) > 80:
        return
    items = [x for x in text_history() if x != value]
    items.insert(0, value)
    i18n.set_setting(TEXT_HISTORY_KEY, items[:TEXT_HISTORY_MAX])


class CompletingTextEdit(QPlainTextEdit):
    """ช่องพิมพ์ข้อความที่เดาคำจากสิ่งที่เคยพิมพ์ไว้ (พิมพ์ 03 -> เสนอ 03/08/2026)

    QCompleter ต่อกับ QLineEdit ได้เอง แต่กับ QPlainTextEdit ต้องต่อสายเอง
    ใช้ "ทั้งบรรทัดที่เคอร์เซอร์อยู่" เป็นคำค้น เพราะข้อความจริงมักมีเว้นวรรค
    (วันที่ ชื่อ เลขที่เอกสาร) ถ้าใช้แค่คำเดียวจะเดาไม่ตรง
    """

    def __init__(self, text: str = "", history: list[str] | None = None) -> None:
        super().__init__(text)
        from PySide6.QtWidgets import QCompleter
        from PySide6.QtCore import QStringListModel

        self._completer = QCompleter(self)
        self._completer.setModel(QStringListModel(history or [], self._completer))
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert_completion)

    def _current_line(self) -> str:
        cursor = self.textCursor()
        cursor.select(cursor.SelectionType.LineUnderCursor)
        return cursor.selectedText()

    def _insert_completion(self, completion: str) -> None:
        cursor = self.textCursor()
        cursor.select(cursor.SelectionType.LineUnderCursor)
        cursor.insertText(completion)          # แทนบรรทัดนั้นด้วยข้อความเต็ม
        self.setTextCursor(cursor)

    def keyPressEvent(self, event) -> None:
        popup = self._completer.popup()
        if popup.isVisible() and event.key() in (
                Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab, Qt.Key_Escape):
            if event.key() == Qt.Key_Escape:
                popup.hide()
            else:
                self._completer.activated.emit(self._completer.currentCompletion())
                popup.hide()
            event.accept()
            return
        super().keyPressEvent(event)
        self._update_popup()

    def _update_popup(self) -> None:
        prefix = self._current_line().strip()
        popup = self._completer.popup()
        # ต้องพิมพ์อย่างน้อย 1 ตัว และไม่เสนอถ้าตรงกับที่พิมพ์อยู่แล้วพอดี
        if not prefix:
            popup.hide()
            return
        self._completer.setCompletionPrefix(prefix)
        if (self._completer.completionCount() == 0
                or (self._completer.completionCount() == 1
                    and self._completer.currentCompletion() == prefix)):
            popup.hide()
            return
        popup.setCurrentIndex(self._completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.setWidth(popup.sizeHintForColumn(0)
                      + popup.verticalScrollBar().sizeHint().width() + 12)
        self._completer.complete(rect)


class ThumbList(QListWidget):
    """แถบหน้าย่อ — รองรับทั้งลากสลับลำดับภายใน และลากไฟล์ PDF จาก Explorer มาแทรก"""

    pdfsDropped = Signal(list, int)      # (ไฟล์ที่ลากมา, ตำแหน่งหน้าที่จะแทรก)

    def _drop_row(self, event) -> int:
        """หน้าที่จะแทรก — ปล่อยครึ่งบนของหน้า = แทรกก่อน, ครึ่งล่าง = แทรกหลัง"""
        pos = event.position().toPoint()
        index = self.indexAt(pos)
        if not index.isValid():
            return self.count()          # ปล่อยที่ว่างท้ายรายการ = ต่อท้าย
        row = index.row()
        rect = self.visualRect(index)
        return row + 1 if pos.y() > rect.center().y() else row

    def dragEnterEvent(self, event) -> None:
        if pdf_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)     # ลากสลับลำดับภายใน ทำงานเหมือนเดิม

    def dragMoveEvent(self, event) -> None:
        if pdf_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        paths = pdf_paths_from_mime(event.mimeData())
        if paths:
            row = self._drop_row(event)
            event.acceptProposedAction()
            self.pdfsDropped.emit(paths, row)
            return
        super().dropEvent(event)


class PrintDialog(QDialog):
    """หน้าต่างพิมพ์แบบเดียวจบ — ตั้งค่าซ้าย + ตัวอย่างจริงขวา แล้วกดพิมพ์เลย

    ทำเองเพราะกล่องพิมพ์ของ Windows แสดงตัวอย่างให้โปรแกรม Win32 ไม่ได้
    (ขึ้นว่า "This app doesn't support print preview")
    """

    def __init__(self, window) -> None:
        super().__init__(window)
        from PySide6.QtPrintSupport import (QPrinter, QPrinterInfo, QPrintPreviewWidget)
        from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialogButtonBox, QFormLayout,
                                       QFrame, QRadioButton, QSpinBox, QVBoxLayout)

        self.window_ref = window
        self.total = window.doc.page_count
        self.setWindowTitle(t("print.title"))
        self.resize(1060, 780)

        # เครื่องพิมพ์สำหรับ "ตัวอย่าง" — ตั้งเป็น PDF ในหน่วยความจำ ไม่ผูกกับ driver จริง
        # (ถ้าผูกกับเครื่องที่ปิดอยู่ Qt จะรอ driver ตอบขนาดกระดาษจน UI ค้าง)
        # ใช้ ScreenResolution (~96 DPI) ไม่ใช่ HighResolution (1200 DPI)
        # ไม่งั้นเรนเดอร์ตัวอย่างทุกหน้าใหญ่มาก ช้าจนเหมือนค้างทุกครั้งที่ปรับค่า
        self.printer = QPrinter(QPrinter.ScreenResolution)
        self.printer.setOutputFormat(QPrinter.PdfFormat)
        self.printer.setPageSize(QPageSize(QPageSize.A4))
        self._target_printer = _system_default_printer()

        root = QHBoxLayout(self)

        # ---------- ซ้าย: ตั้งค่า ----------
        side = QVBoxLayout()
        side.setSpacing(10)
        form = QFormLayout()

        self.printer_box = QComboBox()
        for info in QPrinterInfo.availablePrinters():
            self.printer_box.addItem(info.printerName())
        if self.printer_box.count():
            # เลือกเครื่องพิมพ์หลักของ Windows ให้อัตโนมัติ
            # (เดิมไปหาชื่อจาก self.printer ซึ่งเป็น PDF ในหน่วยความจำ ชื่อว่าง -> หาไม่เจอ
            #  เลยตกไปเลือกตัวแรกตามตัวอักษร เช่น "Send To OneNote")
            idx = self.printer_box.findText(self._target_printer)
            self.printer_box.setCurrentIndex(max(0, idx))
            self._target_printer = self.printer_box.currentText()
        form.addRow(t("print.printer"), self.printer_box)

        self.copies = QSpinBox(); self.copies.setRange(1, 99); self.copies.setValue(1)
        form.addRow(t("print.copies"), self.copies)

        self.orientation = QComboBox()
        self.orientation.addItem(t("print.portrait"), QPageLayout.Portrait)
        self.orientation.addItem(t("print.landscape"), QPageLayout.Landscape)
        form.addRow(t("print.orientation"), self.orientation)

        self.color_box = QComboBox()
        self.color_box.addItem(t("print.color"), QPrinter.Color)
        self.color_box.addItem(t("print.grayscale"), QPrinter.GrayScale)
        form.addRow(t("print.color_mode"), self.color_box)
        side.addLayout(form)

        # ช่วงหน้า
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setStyleSheet("color:#888;")
        side.addWidget(line)
        side.addWidget(QLabel(t("print.pages")))
        self.r_all = QRadioButton(t("print.all_pages", n=self.total))
        self.r_all.setChecked(True)
        self.r_current = QRadioButton(t("print.current_page", n=window.viewer.index + 1))
        self.r_range = QRadioButton(t("print.page_range"))
        self.range_edit = QLineEdit(placeholderText=t("split.range_hint"))
        self.range_edit.setEnabled(False)
        side.addWidget(self.r_all)
        side.addWidget(self.r_current)
        side.addWidget(self.r_range)
        side.addWidget(self.range_edit)

        # กรองคี่/คู่ + ย้อนลำดับ (แบบ Adobe)
        self.oddeven = QComboBox()
        self.oddeven.addItem(t("print.oddeven_all"), "all")
        self.oddeven.addItem(t("print.odd"), "odd")
        self.oddeven.addItem(t("print.even"), "even")
        odd_row = QFormLayout()
        odd_row.addRow(t("print.oddeven"), self.oddeven)
        side.addLayout(odd_row)
        self.reverse = QCheckBox(t("print.reverse"))
        side.addWidget(self.reverse)

        # ---------- ขนาด/การจัดวางหน้า ----------
        line2 = QFrame(); line2.setFrameShape(QFrame.HLine); line2.setStyleSheet("color:#888;")
        side.addWidget(line2)
        side.addWidget(QLabel(t("print.sizing")))
        size_form = QFormLayout()
        self.size_mode = QComboBox()
        self.size_mode.addItem(t("print.size_fit"), "fit")
        self.size_mode.addItem(t("print.size_actual"), "actual")
        self.size_mode.addItem(t("print.size_shrink"), "shrink")
        self.size_mode.addItem(t("print.size_custom"), "custom")
        size_form.addRow(t("print.size"), self.size_mode)

        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(10, 400); self.scale_spin.setValue(100)
        self.scale_spin.setSuffix(" %"); self.scale_spin.setEnabled(False)
        size_form.addRow(t("print.scale"), self.scale_spin)

        self.per_sheet = QComboBox()
        for n_up in (1, 2, 4, 6, 9):
            self.per_sheet.addItem(t("print.nup_one") if n_up == 1
                                   else t("print.nup", n=n_up), n_up)
        size_form.addRow(t("print.per_sheet"), self.per_sheet)
        side.addLayout(size_form)

        self.auto_rotate = QCheckBox(t("print.auto_rotate"))
        self.auto_rotate.setChecked(True)
        self.auto_rotate.setToolTip(t("print.auto_rotate_tip"))
        side.addWidget(self.auto_rotate)

        self.duplex = QCheckBox(t("print.duplex"))
        self.duplex.setToolTip(t("print.duplex_tip"))
        side.addWidget(self.duplex)

        hint = QLabel(t("print.hint"))
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        side.addWidget(hint)
        side.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.print_btn = buttons.button(QDialogButtonBox.Ok)
        self.print_btn.setText(t("print.do_print"))
        self.print_btn.setStyleSheet("font-weight:bold; padding:6px 16px;")
        buttons.accepted.connect(self._do_print)
        buttons.rejected.connect(self.reject)
        side.addWidget(buttons)

        left = QWidget(); left.setLayout(side); left.setFixedWidth(300)
        root.addWidget(left)

        # ---------- ขวา: ตัวอย่างจริง ----------
        self.preview = QPrintPreviewWidget(self.printer, self)
        self.preview.paintRequested.connect(window.render_print)
        self.preview.setStyleSheet("background:#666;")
        root.addWidget(self.preview, 1)

        # เลือกเครื่องพิมพ์/จำนวนชุด/สี — ไม่กระทบภาพตัวอย่าง แค่จำค่าไว้ (ไม่ re-render)
        self.printer_box.currentTextChanged.connect(
            lambda name: setattr(self, "_target_printer", name))
        self.color_box.currentIndexChanged.connect(lambda *_: None)
        # เฉพาะแนวกระดาษ/ช่วงหน้า ที่เปลี่ยนภาพตัวอย่างจริง -> ค่อย re-render
        self.orientation.currentIndexChanged.connect(self._apply_and_refresh)
        self.r_all.toggled.connect(self._on_range_toggle)
        self.r_current.toggled.connect(self._on_range_toggle)
        self.r_range.toggled.connect(self._on_range_toggle)
        self.range_edit.textChanged.connect(self._apply_and_refresh)
        for w_ in (self.oddeven, self.size_mode, self.per_sheet):
            w_.currentIndexChanged.connect(self._apply_and_refresh)
        self.scale_spin.valueChanged.connect(self._apply_and_refresh)
        for c_ in (self.reverse, self.auto_rotate):
            c_.toggled.connect(self._apply_and_refresh)
        self.size_mode.currentIndexChanged.connect(
            lambda *_: self.scale_spin.setEnabled(self.size_mode.currentData() == "custom"))
        self._apply_settings()

    # ---------- ตั้งค่า ----------

    def _on_range_toggle(self, _=None) -> None:
        self.range_edit.setEnabled(self.r_range.isChecked())
        self._apply_and_refresh()

    def selected_pages(self) -> list[int]:
        """หน้าที่จะพิมพ์ (index เริ่ม 0) — ว่าง = ช่วงหน้าที่พิมพ์มาไม่ถูกต้อง"""
        if self.r_all.isChecked():
            pages = list(range(self.total))
        elif self.r_current.isChecked():
            pages = [min(self.window_ref.viewer.index, self.total - 1)]
        else:
            try:
                pages = parse_page_ranges(self.range_edit.text(), self.total)
            except ValueError:
                return []
        # กรองคี่/คู่ (นับตามเลขหน้าที่ผู้ใช้เห็น คือ index+1)
        which = self.oddeven.currentData()
        if which == "odd":
            pages = [i for i in pages if (i + 1) % 2 == 1]
        elif which == "even":
            pages = [i for i in pages if (i + 1) % 2 == 0]
        if self.reverse.isChecked():
            pages = list(reversed(pages))
        return pages

    def _apply_settings(self) -> None:
        from PySide6.QtPrintSupport import QPrinter
        # จำชื่อเครื่องพิมพ์ที่เลือก แต่ "ไม่" setPrinterName ใส่ตัวพรีวิว
        # (การ setPrinterName ไปเรียก driver ขอ devmode — ถ้าเครื่องปิดอยู่จะค้าง)
        self._target_printer = self.printer_box.currentText()
        self.printer.setPageOrientation(self.orientation.currentData())
        pages = self.selected_pages()
        default_order = list(range(self.total))
        if pages == default_order:
            self.printer.setPrintRange(QPrinter.AllPages)
        elif pages:
            self.printer.setPrintRange(QPrinter.PageRange)
            self.printer.setFromTo(min(pages) + 1, max(pages) + 1)
        else:
            self.printer.setPrintRange(QPrinter.AllPages)
        # บอกตัววาดว่าจะพิมพ์หน้าไหน ตามลำดับไหน
        # (รองรับช่วงข้ามหน้า 1-3,7 · คี่/คู่ · ย้อนลำดับ ซึ่ง fromTo อธิบายไม่ได้)
        self.window_ref._print_only_pages = None if pages == default_order else pages
        self.window_ref._print_opts = {
            "size_mode": self.size_mode.currentData(),
            "scale": self.scale_spin.value(),
            "per_sheet": self.per_sheet.currentData(),
            "auto_rotate": self.auto_rotate.isChecked(),
        }
        ok = bool(pages)
        self.print_btn.setEnabled(ok)
        self.range_edit.setStyleSheet("" if ok else "border:1px solid #d33;")

    def _apply_and_refresh(self) -> None:
        self._apply_settings()
        self.preview.updatePreview()      # เรนเดอร์บน A4 ไม่แตะ driver -> ไม่ค้าง

    def _do_print(self) -> None:
        from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
        pages = self.selected_pages()
        if not pages:
            return
        if not self._target_printer:
            QMessageBox.warning(self, t("print.title"), t("print.no_printer"))
            return
        # ตรวจว่าเครื่องพิมพ์ยังมีอยู่ในระบบไหม (ถ้าไม่มี/ถูกถอด จะได้ไม่ค้าง)
        names = [p.printerName() for p in QPrinterInfo.availablePrinters()]
        if self._target_printer not in names:
            QMessageBox.warning(self, t("print.title"),
                                t("print.offline", printer=self._target_printer))
            return
        # สร้างเครื่องพิมพ์จริงตอนกดพิมพ์เท่านั้น (คุยกับ driver ครั้งเดียว)
        real = QPrinter(QPrinter.HighResolution)
        real.setPrinterName(self._target_printer)
        # ตั้งชื่องานพิมพ์เป็นชื่อไฟล์ จะได้โชว์ในคิวเครื่องพิมพ์ (ไม่ใช่ "document1")
        doc_path = self.window_ref.doc.path
        real.setDocName(doc_path.name if doc_path else "Ballcar PDF")
        real.setCopyCount(self.copies.value())
        real.setPageOrientation(self.orientation.currentData())
        real.setColorMode(self.color_box.currentData())
        if self.duplex.isChecked():
            real.setDuplex(QPrinter.DuplexAuto)     # เครื่องที่ไม่รองรับจะพิมพ์หน้าเดียวตามเดิม
        if pages != list(range(self.total)):
            real.setPrintRange(QPrinter.PageRange)
            real.setFromTo(min(pages) + 1, max(pages) + 1)
        # หน้า/ลำดับจริงส่งผ่าน _print_only_pages (fromTo บอกลำดับย้อน/คี่-คู่ไม่ได้)
        self.window_ref.render_print(real)
        self.window_ref.statusBar().showMessage(
            t("print.sent", n=len(pages), printer=self._target_printer), 8000)
        self.window_ref._print_only_pages = None
        self.accept()

    def reject(self) -> None:
        self.window_ref._print_only_pages = None
        super().reject()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.doc: PdfDocument | None = None
        self.setWindowTitle("Ballcar PDF")
        self.resize(1280, 860)

        self.viewer = PageViewer()
        self.thumbs = ThumbList()
        self.thumbs.setIconSize(QSize(140, 190))
        self.thumbs.setSelectionMode(QListWidget.ExtendedSelection)
        self.thumbs.setMinimumWidth(80)   # ไม่ล็อกกว้างสูงสุด ให้ลากขยายได้
        self.thumbs.currentRowChanged.connect(self._on_thumb_selected)
        # ลากวางเพื่อสลับลำดับหน้าได้โดยตรง
        self.thumbs.setDragDropMode(QListWidget.InternalMove)
        self.thumbs.setDefaultDropAction(Qt.MoveAction)
        self.thumbs.model().rowsMoved.connect(self._on_rows_moved)
        self.thumbs.pdfsDropped.connect(self._on_pdfs_dropped)
        self.setAcceptDrops(True)      # ลากไฟล์มาปล่อยที่ไหนในหน้าต่างก็ได้
        self._applying_reorder = False
        # คลิกขวาที่หน้า -> เมนูลัด
        self.thumbs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.thumbs.customContextMenuRequested.connect(self._thumb_context_menu)

        self.text_panel = QPlainTextEdit(readOnly=True)
        self.text_panel.setPlaceholderText(t("text.placeholder"))
        self.text_panel.setMinimumWidth(150)   # ลากปรับความกว้างได้
        self.text_panel.hide()

        self._build_bookmark_panel()

        self.thumbs.setToolTip(t("thumb.tip"))
        self.viewer.contextRequested.connect(self._viewer_context_menu)
        self._pending_image: str | None = None

        # แถบยืนยันตอนกำลังวางลายเซ็น (โผล่เหนือวิวเออร์)
        self._placing_bar = QWidget()
        bar_layout = QHBoxLayout(self._placing_bar)
        bar_layout.setContentsMargins(8, 4, 8, 4)
        tip = self._placing_tip = QLabel(t("bar.placing_tip"))
        tip.setStyleSheet("color:#0a58ca; font-weight:bold;")
        ok_btn = self._ok_btn = QPushButton(t("bar.confirm"))
        ok_btn.clicked.connect(self.commit_placement)
        cancel_btn = self._cancel_btn = QPushButton(t("bar.cancel"))
        cancel_btn.clicked.connect(lambda: self.cancel_placement())
        bar_layout.addWidget(tip)
        bar_layout.addStretch(1)
        bar_layout.addWidget(ok_btn)
        bar_layout.addWidget(cancel_btn)
        style_action_bar(self._placing_bar, "placingBar", "#e7f1ff", "#9ec5fe")
        self._placing_bar.hide()

        # แถบที่โผล่เมื่อคลิกเลือกลายเซ็นที่วางไว้แล้ว
        self._stamp_bar = QWidget()
        stamp_layout = QHBoxLayout(self._stamp_bar)
        stamp_layout.setContentsMargins(8, 4, 8, 4)
        stamp_tip = self._stamp_tip = QLabel(t("bar.stamp_selected"))
        stamp_tip.setStyleSheet("color:#664d03; font-weight:bold;")
        move_btn = self._move_btn = QPushButton(t("bar.move_resize"))
        move_btn.clicked.connect(self.edit_selected_stamp)
        del_btn = self._del_stamp_btn = QPushButton(t("bar.delete_stamp"))
        del_btn.clicked.connect(self.delete_selected_stamp)
        save_btn = self._save_lib_btn = QPushButton(t("bar.save_to_library"))
        save_btn.clicked.connect(self.save_stamp_to_library)
        allpages_btn = self._stamp_allpages_btn = QPushButton(t("bar.stamp_all_pages"))
        allpages_btn.clicked.connect(self.stamp_selected_all_pages)
        done_btn = self._done_btn = QPushButton(t("bar.done"))
        done_btn.clicked.connect(self.deselect_stamp)
        stamp_layout.addWidget(stamp_tip)
        stamp_layout.addStretch(1)
        for b in (move_btn, allpages_btn, save_btn, del_btn, done_btn):
            stamp_layout.addWidget(b)
        style_action_bar(self._stamp_bar, "stampBar", "#fff3cd", "#ffcf6b")
        self._stamp_bar.hide()
        self.viewer.stampSelected.connect(self._on_stamp_selected)
        self.viewer.stampEditRequested.connect(self.edit_selected_stamp)

        # ค่าเริ่มต้นของข้อความที่จะเพิ่ม (จำค่าล่าสุดที่ผู้ใช้ตั้ง)
        self._last_font_size = 16.0
        self._last_color = (0.0, 0.0, 0.0)
        self._last_font = ""       # "" = อัตโนมัติตามภาษา
        self._last_bold = False

        # แถบเครื่องมือเมื่อเลือกกล่องข้อความ
        self._text_bar = QWidget()
        text_layout = QHBoxLayout(self._text_bar)
        text_layout.setContentsMargins(8, 4, 8, 4)
        self._text_tip = QLabel(t("text.selected"))
        self._text_tip.setStyleSheet("color:#0f5132; font-weight:bold;")
        self._text_edit_btn = QPushButton(t("text.edit"))
        self._text_edit_btn.clicked.connect(self.edit_selected_textbox)
        self._text_move_btn = QPushButton(t("bar.move_resize"))
        self._text_move_btn.clicked.connect(self.move_selected_textbox)
        self._text_color_btn = QPushButton(t("text.color"))
        self._text_color_btn.clicked.connect(self.color_selected_textbox)
        self._text_all_btn = QPushButton(t("text.all_pages"))
        self._text_all_btn.setToolTip(t("text.all_pages_tip"))
        self._text_all_btn.clicked.connect(self.textbox_selected_all_pages)
        self._text_del_btn = QPushButton(t("text.delete_btn"))
        self._text_del_btn.clicked.connect(self.delete_selected_textbox)
        self._text_done_btn = QPushButton(t("bar.done"))
        self._text_done_btn.clicked.connect(self.deselect_textbox)
        text_layout.addWidget(self._text_tip)
        text_layout.addStretch(1)
        for b in (self._text_edit_btn, self._text_move_btn, self._text_color_btn,
                  self._text_all_btn, self._text_del_btn, self._text_done_btn):
            text_layout.addWidget(b)
        style_action_bar(self._text_bar, "textBar", "#d1e7dd", "#8fc4a8")
        self._text_bar.hide()
        self.viewer.textboxSelected.connect(self._on_textbox_selected)
        self.viewer.textboxEditRequested.connect(self.edit_selected_textbox)
        self.viewer.pointPicked.connect(self._on_point_picked)
        self.viewer.editPointPicked.connect(self._on_edit_point_picked)
        self.viewer.rectDragged.connect(self._on_rect_dragged)
        self.viewer.eraseDragged.connect(self._on_erase_dragged)
        self.viewer.annotDrawn.connect(self._on_annot_drawn)
        self.viewer.pageFlip.connect(self._on_page_flip)
        self.viewer.pageChanged.connect(self._on_page_changed)

        # แถบเครื่องมือไฮไลต์
        self._highlight_color = (1.0, 0.92, 0.23)   # เหลืองเริ่มต้น
        self._highlight_bar = QWidget()
        hl_layout = QHBoxLayout(self._highlight_bar)
        hl_layout.setContentsMargins(8, 4, 8, 4)
        hl_tip = QLabel(t("hl.selected"))
        hl_tip.setStyleSheet("color:#7a5c00; font-weight:bold;")
        self._highlight_swatch = QLabel()
        self._highlight_swatch.setStyleSheet(
            "background:#ffeb3b; border:1px solid #888; min-width:20px; min-height:16px;")
        color_btn = QPushButton(t("hl.color"))
        color_btn.clicked.connect(self._pick_highlight_color)
        clear_btn = QPushButton(t("hl.clear_page"))
        clear_btn.clicked.connect(self.clear_highlights_page)
        hl_done = QPushButton(t("bar.done"))
        hl_done.clicked.connect(self._end_highlight_mode)
        hl_layout.addWidget(hl_tip)
        hl_layout.addWidget(self._highlight_swatch)
        hl_layout.addStretch(1)
        for b in (color_btn, clear_btn, hl_done):
            hl_layout.addWidget(b)
        style_action_bar(self._highlight_bar, "highlightBar", "#fff8e1", "#ffcf40")
        self._highlight_bar.hide()

        # แถบยางลบ/ปิดทับ (สำหรับไฟล์สแกน)
        from PySide6.QtWidgets import QCheckBox
        self._erase_auto_color = True
        self._erase_bar = QWidget()
        er_layout = QHBoxLayout(self._erase_bar)
        er_layout.setContentsMargins(8, 4, 8, 4)
        er_tip = self._erase_tip = QLabel(t("er.selected"))
        er_tip.setStyleSheet("color:#8a2f2f; font-weight:bold;")
        auto_chk = self._erase_auto_chk = QCheckBox(t("er.auto_color"))
        auto_chk.setChecked(True)
        auto_chk.setToolTip(t("er.auto_color_tip"))
        auto_chk.toggled.connect(lambda on: setattr(self, "_erase_auto_color", on))
        er_clear = QPushButton(t("er.clear_page"))
        er_clear.clicked.connect(self.clear_erasers_page)
        er_done = QPushButton(t("bar.done"))
        er_done.clicked.connect(self._end_erase_mode)
        er_layout.addWidget(er_tip)
        er_layout.addStretch(1)
        for wdg in (auto_chk, er_clear, er_done):
            er_layout.addWidget(wdg)
        style_action_bar(self._erase_bar, "eraseBar", "#fdecec", "#e79a9a")
        self._erase_bar.hide()

        # แถบวาด/มาร์กอัป (ปากกา/เส้น/ลูกศร/สี่เหลี่ยม/วงกลม)
        from PySide6.QtWidgets import QComboBox as _QCombo
        self._annot_color = (0.9, 0.1, 0.1)
        self._annot_width = 2.0
        self._annot_bar = QWidget()
        an_layout = QHBoxLayout(self._annot_bar)
        an_layout.setContentsMargins(8, 4, 8, 4)
        an_tip = QLabel(t("an.selected"))
        an_tip.setStyleSheet("color:#1f5c99; font-weight:bold;")
        an_layout.addWidget(an_tip)
        an_layout.addStretch(1)
        self._annot_tool_btns = {}
        for tool, label in (("draw", t("an.draw")), ("line", t("an.line")),
                            ("arrow", t("an.arrow")), ("rect", t("an.rect")),
                            ("circle", t("an.circle"))):
            b = QPushButton(label)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, tk=tool: self._set_annot_tool(tk))
            an_layout.addWidget(b)
            self._annot_tool_btns[tool] = b
        self._annot_tool_btns["draw"].setChecked(True)
        self._annot_width_box = _QCombo()
        for w in ("1", "2", "3", "5", "8"):
            self._annot_width_box.addItem(t("an.width_px", n=w), float(w))
        self._annot_width_box.setCurrentIndex(1) if False else self._annot_width_box.setCurrentIndex(1)
        self._annot_width_box.currentIndexChanged.connect(self._apply_annot_style)
        an_layout.addWidget(self._annot_width_box)
        an_color = QPushButton(t("an.color"))
        an_color.clicked.connect(self._pick_annot_color)
        self._annot_swatch = QLabel("  ")
        self._paint_annot_swatch()
        an_clear = QPushButton(t("an.clear_page"))
        an_clear.clicked.connect(self.clear_annotations_page)
        an_done = QPushButton(t("bar.done"))
        an_done.clicked.connect(self._end_annot_mode)
        for wdg in (an_color, self._annot_swatch, an_clear, an_done):
            an_layout.addWidget(wdg)
        style_action_bar(self._annot_bar, "annotBar", "#e7f1ff", "#9ec5fe")
        self._annot_bar.hide()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        left_layout.addWidget(self.thumbs)
        hint = self._hint_label = QLabel(t("thumb.hint"))
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#888; font-size:11px; padding:2px;")
        left_layout.addWidget(hint)
        # ใช้ความกว้างขั้นต่ำ ไม่ล็อกความกว้างสูงสุด — ไม่งั้นลากเส้นแบ่งขยายไม่ได้
        left.setMinimumWidth(90)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)          # เส้นแบ่งหนาพอให้จับลากได้ง่าย
        splitter.setChildrenCollapsible(False)   # ลากจนหายทั้งแผงไม่ได้ (กันงง)
        splitter.setStyleSheet(
            "QSplitter::handle:horizontal { background:#8a8a8a; margin:0 1px; }"
            "QSplitter::handle:horizontal:hover { background:#4a90d9; }")
        splitter.addWidget(left)
        splitter.addWidget(self._bookmark_panel)

        viewer_area = QWidget()
        viewer_layout = QVBoxLayout(viewer_area)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)
        viewer_layout.addWidget(self._placing_bar)
        viewer_layout.addWidget(self._stamp_bar)
        viewer_layout.addWidget(self._text_bar)
        viewer_layout.addWidget(self._highlight_bar)
        viewer_layout.addWidget(self._erase_bar)
        viewer_layout.addWidget(self._annot_bar)
        viewer_layout.addWidget(self.viewer)
        self._build_selection_popup()
        splitter.addWidget(viewer_area)

        splitter.addWidget(self.text_panel)
        # ให้พื้นที่ที่เหลือไปที่หน้าเอกสาร (index 2 คือ viewer — เดิมใส่ผิดเป็น 1)
        for i, stretch in ((0, 0), (1, 0), (2, 1), (3, 0)):
            splitter.setStretchFactor(i, stretch)
        splitter.setSizes([190, 0, 900, 0])   # ความกว้างเริ่มต้น (ลากปรับได้ทีหลัง)
        self._splitter = splitter
        self.setCentralWidget(splitter)

        # ลากเส้นแบ่งแล้วสร้างภาพย่อใหม่ให้พอดีความกว้าง (หน่วงไว้ ไม่ให้หนักตอนลาก)
        self._thumb_resize_timer = QTimer(self)
        self._thumb_resize_timer.setSingleShot(True)
        self._thumb_resize_timer.setInterval(250)
        self._thumb_resize_timer.timeout.connect(
            lambda: self._rebuild_thumbs(self.viewer.index) if self.doc else None)
        splitter.splitterMoved.connect(lambda *_: self._thumb_resize_timer.start())

        self.setStatusBar(QStatusBar())
        self._build_toolbars()
        self._build_menu()
        self._update_state()

        # สำรองงานอัตโนมัติแบบกู้คืน (Pre-save) — id เฉพาะหน้าต่างนี้
        self._session_id = uuid.uuid4().hex[:8]
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(60_000)   # ทุก 60 วินาที
        self._autosave_timer.timeout.connect(self._autosave_tick)
        self._autosave_timer.start()

    def _autosave_tick(self) -> None:
        """แอบเซฟสำเนากู้คืน ถ้ามีงานที่ยังไม่บันทึก (ไม่แตะไฟล์ต้นฉบับ)"""
        if not self.doc or not self.doc.dirty:
            return
        try:
            with self.doc.flattened() as flat:
                data = flat.tobytes()
            autosave.write_recovery(
                data, str(self.doc.path) if self.doc.path else None, self._session_id)
        except Exception:
            pass   # สำรองล้มเหลวไม่ควรทำให้โปรแกรมสะดุด

    def _clear_autosave(self) -> None:
        autosave.clear_recovery(
            str(self.doc.path) if (self.doc and self.doc.path) else None, self._session_id)

    def offer_recovery(self) -> None:
        """เปิดโปรแกรมแล้วเจองานค้างจากครั้งก่อน — ถามว่าจะกู้ไหม"""
        pending = autosave.pending_recoveries()
        if not pending:
            return
        rec = pending[0]
        name = Path(rec["original"]).name if rec["original"] else t("recover.untitled")
        when = time.strftime("%d/%m/%Y %H:%M", time.localtime(rec["saved_at"]))
        answer = QMessageBox.question(
            self, t("recover.title"), t("recover.prompt", name=name, when=when),
            QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            try:
                self.doc = PdfDocument(rec["pdf_path"])
                self.doc.path = Path(rec["original"]) if rec["original"] else None
                self.doc.dirty = True    # เป็นงานที่ยังไม่บันทึกลงไฟล์จริง
                self.viewer.set_document(self.doc)
                self._refresh_all(keep_row=0)
                self.viewer.fit_width()
                self.statusBar().showMessage(t("recover.done"), 8000)
            except Exception as exc:
                QMessageBox.warning(self, t("recover.title"), str(exc))
        # ไม่ว่าจะกู้หรือไม่ ถือว่าจัดการงานค้างนี้แล้ว
        autosave.discard_recovery(rec["meta_path"])

    # ---------------- แถบเครื่องมือ / เมนู ----------------

    def _act(self, text: str, slot, shortcut: str | None = None, tip: str | None = None,
             icon: str | None = None) -> QAction:
        action = QAction(text, self)
        # QAction.triggered ส่ง checked (bool) มาเป็นอาร์กิวเมนต์แรกเสมอ
        # ถ้าต่อตรงเข้า slot ที่มีพารามิเตอร์ค่าเริ่มต้น ค่านั้นจะถูกยัดด้วย False โดยไม่ตั้งใจ
        # (เคยทำให้ "แทรกไฟล์ต่อท้าย" กลายเป็น at=False = แทรกที่หน้า 1) — ตัดทิ้งให้หมด
        action.triggered.connect(lambda *_: slot())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setToolTip(tip or text)
        if icon:
            action.setIcon(emoji_icon(icon))
            action.setIconVisibleInMenu(True)
        return action

    def _build_toolbars(self) -> None:
        bar = QToolBar("main")
        # ปุ่มที่ใช้บ่อยเป็นไอคอน (มี tooltip) ให้แถบกระชับ พอดีทุกจอ
        # เมนูบนด้านบนยังมีข้อความครบทุกคำสั่งสำหรับคนที่ไม่คุ้นไอคอน
        bar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        bar.setIconSize(QSize(22, 22))
        self.addToolBar(bar)
        self._toolbar = bar

        self.act_open = self._act(t("file.open"), self.open_file, "Ctrl+O", icon="📂")
        self.act_save = self._act(t("file.save"), self.save_file, "Ctrl+S", icon="💾")
        self.act_save_as = self._act(t("file.save_as"), self.save_file_as, "Ctrl+Shift+S", icon="📝")
        self.act_print = self._act(t("file.print"), self.print_document, "Ctrl+P", icon="🖨")
        for a in (self.act_open, self.act_save, self.act_save_as, self.act_print):
            bar.addAction(a)

        bar.addSeparator()
        self.act_undo = self._act("↶ " + t("edit.undo"), self.undo, "Ctrl+Z", icon="↩️")
        self.act_redo = self._act("↷ " + t("edit.redo"), self.redo, "Ctrl+Y", icon="↪️")
        bar.addAction(self.act_undo)
        bar.addAction(self.act_redo)

        bar.addSeparator()
        self.act_prev = self._act(t("tb.prev"), lambda: self.goto_page(self.viewer.index - 1),
                                  "PgUp", icon="◀️")
        self.act_next = self._act(t("tb.next"), lambda: self.goto_page(self.viewer.index + 1),
                                  "PgDown", icon="▶️")
        bar.addAction(self.act_prev)
        bar.addAction(self.act_next)

        self.page_box = QLineEdit(maximumWidth=60, alignment=Qt.AlignCenter)
        self.page_box.returnPressed.connect(self._on_page_box)
        bar.addWidget(self.page_box)
        self.page_label = QLabel(" / 0   ")
        bar.addWidget(self.page_label)

        bar.addSeparator()
        bar.addAction(self._act(t("tb.zoom_out"),
                                lambda: self.viewer.set_zoom(self.viewer.zoom / 1.25),
                                "Ctrl+-", icon="➖"))
        bar.addAction(self._act(t("tb.zoom_in"),
                                lambda: self.viewer.set_zoom(self.viewer.zoom * 1.25),
                                "Ctrl+=", icon="➕"))
        bar.addAction(self._act(t("tb.fit_width"), self.viewer.fit_width, icon="↔️"))

        bar.addSeparator()
        previous_search = getattr(self, "search_box", None)
        self.search_box = QLineEdit(placeholderText=t("tb.search_placeholder"), maximumWidth=220)
        if previous_search is not None:
            self.search_box.setText(previous_search.text())   # เปลี่ยนภาษาแล้วคำค้นไม่หาย
        self.search_box.returnPressed.connect(self.search_next)
        bar.addWidget(self.search_box)
        self.act_find = self._act(t("tb.find_next"), self.search_next, "F3", icon="🔎")
        bar.addAction(self.act_find)
        self.act_clear_find = self._act(t("tb.clear_find"), self.clear_search, icon="🧹")
        bar.addAction(self.act_clear_find)

        bar.addSeparator()
        # รวมเครื่องมือแก้ไขทั้งหมดไว้ในปุ่มเดียว (มีเมนูย่อย) — กันปุ่มล้นแถบตอนจอไม่เต็ม
        self.act_add_text = self._act(t("tb.add_text"), self.add_text_dialog, icon="🔤")
        self.act_edit_text = self._act(t("tb.edit_text"), self.edit_text_dialog, icon="✏️")
        self.act_highlight = self._act(t("tb.highlight"), self.toggle_highlight_mode, icon="🖍")
        self.act_markup = self._act(t("tb.markup"), self.toggle_annot_mode, icon="🖊")
        self.act_erase = self._act(t("tb.erase"), self.toggle_erase_mode, icon="🩹")
        self.act_assistant = self._act(t("tb.assistant"), self.assistant_dialog, icon="🤖")

        self.tools_button = QToolButton()
        self.tools_button.setText(t("tb.tools"))
        self.tools_button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.tools_button.setPopupMode(QToolButton.InstantPopup)
        self.tools_button.setStyleSheet(
            "QToolButton { font-weight:bold; padding:2px 10px; }"
            "QToolButton::menu-indicator { subcontrol-position: right center; }")
        tools_menu = QMenu(self)
        for a in (self.act_add_text, self.act_edit_text, self.act_highlight,
                  self.act_markup, self.act_erase):
            tools_menu.addAction(a)
        tools_menu.addSeparator()
        # ลายเซ็น = เมนูย่อยซ้อน (คลังลายเซ็นสร้างตอนกางเมนู)
        self.sig_menu = QMenu(t("tb.signature"), self)
        self.sig_menu.setIcon(emoji_icon("✒️"))
        self.sig_menu.aboutToShow.connect(self._build_signature_menu)
        tools_menu.addMenu(self.sig_menu)
        tools_menu.addSeparator()
        tools_menu.addAction(self.act_assistant)
        self.tools_button.setMenu(tools_menu)
        bar.addWidget(self.tools_button)

    def _build_menu(self) -> None:
        menu = self.menuBar()
        menu.clear()   # เปลี่ยนภาษาแล้วสร้างใหม่ทั้งแถบ

        m_file = menu.addMenu(t("menu.file"))
        for a in (self.act_open, self.act_save, self.act_save_as):
            m_file.addAction(a)
        m_file.addSeparator()
        m_file.addAction(self.act_print)
        m_file.addSeparator()
        m_file.addAction(self._act(t("file.exit"), self.close, "Ctrl+Q", icon="🚪"))

        m_edit = menu.addMenu(t("menu.edit"))
        m_edit.addAction(self.act_undo)
        m_edit.addAction(self.act_redo)

        m_page = menu.addMenu(t("menu.pages"))
        self.page_actions = [
            self._act(t("pages.insert_blank"), self.insert_blank, icon="📄"),
            self._act(t("pages.insert_pdf"), self.insert_pdf_file, icon="📑"),
            self._act(t("pages.delete"), self.delete_selected, "Delete", icon="🗑"),
            self._act(t("pages.move_up"), lambda: self.move_selected(-1), "Ctrl+Shift+Up",
                      icon="⬆"),
            self._act(t("pages.move_down"), lambda: self.move_selected(1), "Ctrl+Shift+Down",
                      icon="⬇"),
            # ต้องใช้อิโมจิจริง (มีสี) ไม่ใช่ตัวอักษรลูกศร ↺↻ ที่บางจนแทบมองไม่เห็นในเมนู
            self._act(t("pages.rotate_left"), lambda: self.rotate_selected(-90), icon="🔄"),
            self._act(t("pages.rotate_right"), lambda: self.rotate_selected(90), icon="🔃"),
            self._act(t("pages.rotate_180"), lambda: self.rotate_selected(180), icon="↕️"),
            self._act(t("pages.crop"), self.crop_dialog, icon="🖼"),
        ]
        for a in self.page_actions:
            m_page.addAction(a)

        m_tools = menu.addMenu(t("menu.tools"))
        self.tool_actions = [
            self._act(t("tools.add_text"), self.add_text_dialog, icon="🔤"),
            self._act(t("tools.edit_text"), self.edit_text_dialog, icon="✏️"),
            self._act(t("tools.fill_form"), self.fill_form_dialog, icon="🗒"),
            self._act(t("tools.password"), self.password_dialog, icon="🔒"),
            self._act(t("tools.batch"), self.batch_dialog, icon="⚙️"),
            self._act(t("tools.merge"), self.merge_dialog, icon="🔗"),
            self._act(t("tools.split"), self.split_dialog, icon="✂️"),
            self._act(t("tools.compress"), self.compress_dialog, icon="🗜"),
            self._act(t("tools.page_numbers"), self.add_numbers_dialog, icon="🔢"),
            self._act(t("tools.save_images"), self.export_images_dialog, icon="🖼"),
            self._act(t("tools.extract_text"), self.extract_all_text, icon="📃"),
            self._act(t("tools.ocr"), self.ocr_dialog, icon="🔍"),
            self._act(t("tools.to_word"), self.export_word, icon="📘"),
            self._act(t("tools.to_excel"), self.export_excel, icon="📊"),
            self._act(t("tools.extract_images"), self.export_embedded_images, icon="🏞"),
            self._act(t("tools.watermark_text"), self.watermark_dialog, icon="💧"),
            self._act(t("tools.watermark_image"), self.image_watermark_dialog, icon="🌊"),
            self._act(t("tools.signature"), self.signature_dialog, icon="✒️"),
            self._act(t("tools.insert_image"), self.insert_image_dialog, icon="🖼"),
        ]
        for a in self.tool_actions:
            m_tools.addAction(a)

        m_view = menu.addMenu(t("menu.view"))
        toggle_text = QAction(emoji_icon("📃"), t("view.show_text"), self, checkable=True)
        toggle_text.setChecked(self.text_panel.isVisible())
        toggle_text.toggled.connect(self._toggle_text_panel)
        m_view.addAction(toggle_text)

        toggle_bm = QAction(emoji_icon("🔖"), t("view.show_bookmarks"), self, checkable=True)
        toggle_bm.setChecked(self._bookmark_panel.isVisible())
        toggle_bm.toggled.connect(self._toggle_bookmark_panel)
        m_view.addAction(toggle_bm)

        m_lang = menu.addMenu(t("menu.language"))
        for code, key in (("th", "lang.thai"), ("en", "lang.english")):
            action = QAction(emoji_icon("🇹🇭" if code == "th" else "🇬🇧"), t(key), self,
                             checkable=True)
            action.setChecked(i18n.current() == code)
            action.triggered.connect(lambda _=False, c=code: self.change_language(c))
            m_lang.addAction(action)

        m_help = menu.addMenu(t("menu.help"))
        m_help.addAction(self._act(t("upd.check_now"), lambda: self.check_updates(quiet=False),
                                   icon="🔄"))
        m_help.addAction(self._act(t("upd.set_server"), self.set_update_server, icon="🌐"))
        m_help.addSeparator()
        m_help.addAction(self._act(t("help.about"), self.show_about, icon="ℹ️"))

    def change_language(self, code: str) -> None:
        if code == i18n.current():
            return
        i18n.save_language(code)
        self.removeToolBar(self._toolbar)
        self._toolbar.setParent(None)   # ตัดขาดทันที ไม่รอ deleteLater ไม่งั้นแถบเก่าค้าง
        self._toolbar.deleteLater()
        self._build_toolbars()
        self._build_menu()
        self._retranslate()
        self._update_state()
        self.statusBar().showMessage(t("lang.changed"), 4000)

    def _retranslate(self) -> None:
        """เปลี่ยนข้อความของส่วนที่ไม่ได้สร้างใหม่ตอนเปลี่ยนภาษา"""
        self.thumbs.setToolTip(t("thumb.tip"))
        self._hint_label.setText(t("thumb.hint"))
        self.text_panel.setPlaceholderText(t("text.placeholder"))
        self._placing_tip.setText(t("bar.placing_tip"))
        self._ok_btn.setText(t("bar.confirm"))
        self._cancel_btn.setText(t("bar.cancel"))
        self._stamp_tip.setText(t("bar.stamp_selected"))
        self._move_btn.setText(t("bar.move_resize"))
        self._save_lib_btn.setText(t("bar.save_to_library"))
        self._del_stamp_btn.setText(t("bar.delete_stamp"))
        self._done_btn.setText(t("bar.done"))
        self._text_tip.setText(t("text.selected"))
        self._text_edit_btn.setText(t("text.edit"))
        self._text_move_btn.setText(t("bar.move_resize"))
        self._text_color_btn.setText(t("text.color"))
        self._text_del_btn.setText(t("text.delete_btn"))
        self._text_done_btn.setText(t("bar.done"))
        self._rebuild_thumbs()
        self.viewer.refresh()

    def show_about(self) -> None:
        """หน้าต่างเกี่ยวกับโปรแกรม — ลิขสิทธิ์ + ช่องทางแจ้งปัญหา + ช่องทางสนับสนุน

        ทำเองแทน QMessageBox.about เพราะต้องใส่รูป QR และอีเมลที่คลิกได้
        """
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFrame, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle(t("help.about_title"))
        root = QHBoxLayout(dialog)
        root.setContentsMargins(18, 18, 18, 14)
        root.setSpacing(16)

        # ---- โลโก้ด้านซ้าย ----
        icon = app_icon_path()
        if icon:
            logo = QLabel()
            logo.setPixmap(QPixmap(str(icon)).scaled(
                96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            root.addWidget(logo, 0, Qt.AlignTop)

        # ---- เนื้อหาด้านขวา ----
        body = QVBoxLayout()
        body.setSpacing(2)

        name = QLabel(APP_NAME)
        name.setStyleSheet("font-size:17px; font-weight:bold;")
        body.addWidget(name)
        body.addWidget(QLabel(t("about.version", version=APP_VERSION)))
        body.addSpacing(8)
        body.addWidget(QLabel(t("about.tagline")))
        body.addSpacing(8)
        for key in ("about.copyright", "about.license"):
            body.addWidget(QLabel(t(key)))
        warranty = QLabel(t("about.warranty"))
        warranty.setWordWrap(True)
        warranty.setStyleSheet("color:#888; font-size:11px;")
        body.addSpacing(4)
        body.addWidget(warranty)

        def divider() -> QFrame:
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("color:#888;")
            return line

        # ---- แจ้งปัญหา / เสนอแนะ (บรรทัดเดียว ให้หน้าต่างกะทัดรัด) ----
        body.addSpacing(10)
        body.addWidget(divider())
        body.addSpacing(8)
        mail = QLabel(
            f'{t("about.contact")} '
            f'<a href="mailto:{SUPPORT_EMAIL}?subject=Ballcar%20PDF%20{APP_VERSION}">'
            f'{SUPPORT_EMAIL}</a>'
        )
        mail.setOpenExternalLinks(True)          # คลิกแล้วเปิดโปรแกรมอีเมลให้เลย
        mail.setTextInteractionFlags(Qt.TextBrowserInteraction)
        mail.setWordWrap(True)
        body.addWidget(mail)
        hint = QLabel(t("about.contact_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888; font-size:11px;")
        body.addWidget(hint)

        # ---- แถวปุ่ม: สนับสนุน (ซ้าย) + OK (ขวา) ----
        # ไม่โชว์ QR ตรงนี้ ให้กดปุ่มแล้วค่อยเด้งหน้าต่างเล็กขึ้นมา หน้าต่างหลักจะได้ไม่ยาว
        body.addSpacing(12)
        row = QHBoxLayout()
        donate = QPushButton(t("about.support_btn"))
        donate.setCursor(Qt.PointingHandCursor)
        donate.clicked.connect(self.show_support)
        row.addWidget(donate)
        row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        row.addWidget(buttons)
        body.addLayout(row)

        root.addLayout(body)
        dialog.exec()

    def show_support(self) -> None:
        """ป๊อปอัปเล็กๆ แสดง QR พร้อมเพย์ (เปิดจากปุ่มในหน้าต่างเกี่ยวกับโปรแกรม)"""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle(t("support.title"))
        box = QVBoxLayout(dialog)
        box.setContentsMargins(20, 18, 20, 14)
        box.setSpacing(10)

        thanks = QLabel(t("support.thanks"))
        thanks.setAlignment(Qt.AlignCenter)
        box.addWidget(thanks)

        qr = promptpay_qr_path()
        if qr:
            pic = QLabel()
            pic.setPixmap(QPixmap(str(qr)).scaled(
                260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            pic.setAlignment(Qt.AlignCenter)
            box.addWidget(pic)
        else:
            missing = QLabel(t("about.qr_missing"))
            missing.setAlignment(Qt.AlignCenter)
            missing.setWordWrap(True)
            missing.setStyleSheet("color:#888; font-size:11px;")
            box.addWidget(missing)

        who = QLabel(t("support.promptpay"))
        who.setAlignment(Qt.AlignCenter)
        box.addWidget(who)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText(t("support.close"))
        buttons.rejected.connect(dialog.reject)
        box.addWidget(buttons)
        dialog.exec()

    # ---------------- อัปเดตโปรแกรม (ดึงจากเซิร์ฟเวอร์ภายใน) ----------------

    def set_update_server(self) -> None:
        """ตั้งที่อยู่เครื่องแม่ (เครื่องพี่ที่ปล่อยอัปเดต) — ทำครั้งเดียวต่อเครื่อง"""
        current = i18n.get_setting("update_url", "") or updater.DEFAULT_UPDATE_URL
        url, ok = QInputDialog.getText(
            self, t("upd.set_server"), t("upd.set_prompt"), text=current)
        if not ok:
            return
        i18n.set_setting("update_url", updater.normalize_base_url(url))
        self.statusBar().showMessage(t("upd.server_saved"), 5000)

    def check_updates(self, quiet: bool = True) -> None:
        """ตรวจอัปเดตจากเซิร์ฟเวอร์ · quiet=True (ตอนเปิดโปรแกรม) ไม่ขึ้นอะไรถ้าไม่มี/ต่อไม่ได้"""
        # ที่ผู้ใช้ตั้งเองมาก่อน แล้วไล่ลองค่าเริ่มต้น/ตัวสำรอง (IP กับชื่อเครื่อง)
        # เผื่อเครื่องลูกบางเครื่องแปลชื่อเครื่องไม่ออก หรือ IP เครื่องแม่เปลี่ยนตาม DHCP
        info = updater.check_for_update_any(
            i18n.get_setting("update_url", ""), APP_VERSION)
        if info is None:
            if not quiet:
                QMessageBox.information(self, t("upd.title"),
                                        t("upd.up_to_date", version=APP_VERSION))
            return

        msg = t("upd.found", new=info["version"], cur=APP_VERSION)
        if info.get("notes"):
            msg += "\n\n" + info["notes"]
        if QMessageBox.question(self, t("upd.title"), msg,
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._download_and_apply(info)

    def _download_and_apply(self, info: dict) -> None:
        from PySide6.QtWidgets import QProgressDialog
        progress = QProgressDialog(t("upd.downloading"), t("bar.cancel"), 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        cancelled = {"v": False}
        progress.canceled.connect(lambda: cancelled.update(v=True))

        def report(done, total):
            if total > 0:
                progress.setValue(int(done * 100 / total))
            QApplication.processEvents()
            if cancelled["v"]:
                raise RuntimeError("cancelled")

        try:
            path = updater.download_installer(info["url"], progress=report)
        except RuntimeError:
            return          # ผู้ใช้ยกเลิก
        except Exception as exc:
            QMessageBox.critical(self, t("upd.title"), t("upd.download_failed") + f"\n{exc}")
            return
        finally:
            progress.close()

        # เตือนถ้ามีงานยังไม่บันทึก (installer จะปิดโปรแกรม)
        if not self._confirm_discard():
            return
        QMessageBox.information(self, t("upd.title"), t("upd.installing"))
        self._clear_autosave()
        updater.apply_update(path)
        QApplication.quit()       # ปิดตัวเองให้ installer เขียนทับไฟล์ได้

    # ---------------- สถานะ / รีเฟรช ----------------

    def _update_state(self) -> None:
        has = self.doc is not None and self.doc.page_count > 0
        for a in (self.act_save, self.act_save_as, self.act_print, self.act_prev,
                  self.act_next, self.act_find, self.act_clear_find,
                  *self.page_actions, *self.tool_actions):
            a.setEnabled(has)

        self.act_undo.setEnabled(bool(self.doc and self.doc.can_undo))
        self.act_redo.setEnabled(bool(self.doc and self.doc.can_redo))

        total = self.doc.page_count if self.doc else 0
        self.page_label.setText(f" / {total}   ")
        self.page_box.setText(str(self.viewer.index + 1) if has else "")

        name = self.doc.path.name if (self.doc and self.doc.path) else t("title.no_file")
        mark = " *" if (self.doc and self.doc.dirty) else ""
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — {name}{mark}")

    def _thumb_width(self) -> int:
        """ความกว้างเป้าหมายของภาพย่อ (พิกเซล) — โตตามความกว้างแผงที่ผู้ใช้ลาก"""
        width = self.thumbs.viewport().width()
        if not self.isVisible() or width <= 0:
            return 120             # ยังไม่ได้ layout จริง ใช้ค่าเริ่มต้นก่อน
        # เผื่อ scrollbar + ที่สำหรับป้าย "หน้า N" ที่อยู่ข้างภาพ
        # และจำกัดไม่ให้ใหญ่เกิน ~200px ไม่งั้นภาพสูงจนเห็นทีละหน้า ใช้งานยาก
        return max(60, min(width - 70, 200))

    def _thumb_zoom(self) -> float:
        """ซูมของภาพย่อสำหรับหน้าปัจจุบัน (เก็บไว้เพื่อความเข้ากันได้)"""
        if not self.doc or not self.doc.page_count:
            return THUMB_ZOOM
        try:
            page_w = self.doc.doc.load_page(self.viewer.index).rect.width or 595
        except Exception:
            page_w = 595
        return max(0.10, min(1.0, self._thumb_width() / page_w))

    def _rebuild_thumbs(self, keep_row: int | None = None) -> None:
        row = self.thumbs.currentRow() if keep_row is None else keep_row
        target = self._thumb_width()
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        if self.doc:
            pixmaps = []
            for i in range(self.doc.page_count):
                # ซูมแยกรายหน้า ให้ภาพย่อทุกหน้ากว้างเท่ากันแม้ขนาดหน้าไม่เท่ากัน
                # (ใช้ซูมค่าเดียวทั้งเล่มไม่ได้ — หน้าที่ใหญ่กว่าจะล้นกรอบจนดูเหมือนหน้าว่าง)
                page_w = self.doc.doc.load_page(i).rect.width or 595
                zoom = max(0.05, min(1.0, target / page_w))
                pixmaps.append(QPixmap.fromImage(pixmap_to_qimage(self.doc.render_page(i, zoom))))
            # ตั้งขนาดไอคอนครั้งเดียวให้พอดีกับหน้าที่สูงที่สุด (เป็นค่าของทั้งลิสต์)
            tallest = max((p.height() for p in pixmaps), default=1)
            self.thumbs.setIconSize(QSize(target, tallest))
            for i, pix in enumerate(pixmaps):
                item = QListWidgetItem(QIcon(pix), t("thumb.page", n=i + 1))
                item.setData(Qt.UserRole, i)  # ใช้อ้างลำดับเดิมตอนลากวาง
                self.thumbs.addItem(item)
        self.thumbs.blockSignals(False)
        if self.doc and self.doc.page_count:
            self.thumbs.setCurrentRow(max(0, min(row, self.doc.page_count - 1)))

    def _refresh_all(self, keep_row: int | None = None) -> None:
        # รีเฟรชวิวเออร์ก่อน — เพราะ _rebuild_thumbs จะเลือกแถวแล้วเรียก show_page() กลับเข้ามา
        # ถ้าวิวเออร์ยังคำนวณหน้าไม่เสร็จ (เช่นเพิ่งแทรก/ลบหน้า) จะเลื่อนไปตำแหน่งผิด
        self.viewer.refresh()
        self._rebuild_thumbs(keep_row)
        self._update_text_panel()
        if self._bookmark_panel.isVisible():
            self._refresh_bookmarks()
        self._update_state()

    def _selected_rows(self) -> list[int]:
        rows = sorted(i.row() for i in self.thumbs.selectedIndexes())
        return rows or ([self.viewer.index] if self.doc and self.doc.page_count else [])

    def _on_thumb_selected(self, row: int) -> None:
        if row >= 0:
            self.viewer.show_page(row)
            self._update_text_panel()
            self._update_state()

    def undo(self) -> None:
        if self.doc and self.doc.undo():
            self._refresh_all()
            self.statusBar().showMessage("ย้อนกลับแล้ว", 4000)

    def redo(self) -> None:
        if self.doc and self.doc.redo():
            self._refresh_all()
            self.statusBar().showMessage("ทำซ้ำแล้ว", 4000)

    def _thumb_context_menu(self, pos) -> None:
        menu = self.build_thumb_menu(pos)
        if menu:
            menu.exec(self.thumbs.viewport().mapToGlobal(pos))

    def _viewer_context_menu(self, pos) -> None:
        menu = self.build_viewer_menu()
        if menu:
            menu.exec(self.viewer.mapToGlobal(pos))

    def build_thumb_menu(self, pos) -> QMenu | None:
        """เมนูคลิกขวาบน thumbnail — ทำงานกับหน้าที่เลือกไว้ (หรือหน้าที่คลิก)"""
        if not self.doc or not self.doc.page_count:
            return None
        clicked = self.thumbs.itemAt(pos)
        if clicked is not None and not clicked.isSelected():
            self.thumbs.setCurrentItem(clicked)  # คลิกขวานอกหน้าที่เลือก -> สลับมาหน้านั้น

        rows = self._selected_rows()
        if not rows:
            return None
        n = len(rows)
        label = f"{n} หน้าที่เลือก" if n > 1 else f"หน้า {rows[0] + 1}"

        menu = QMenu(self)
        if self.doc.can_undo:
            menu.addAction("↶ ย้อนกลับ", self.undo)
            menu.addSeparator()
        menu.addAction(f"↺ หมุนซ้าย 90°   ({label})", lambda: self.rotate_selected(-90))
        menu.addAction(f"↻ หมุนขวา 90°   ({label})", lambda: self.rotate_selected(90))
        menu.addAction(f"⟲ หมุน 180°   ({label})", lambda: self.rotate_selected(180))
        menu.addSeparator()
        menu.addAction("แทรกหน้าว่างก่อนหน้านี้", self.insert_blank)
        menu.addAction("แทรกหน้าว่างหลังหน้านี้", lambda: self._insert_blank_at(rows[-1] + 1))
        menu.addAction("แทรกไฟล์ PDF อื่นตรงนี้…", lambda: self.insert_pdf_file(rows[0]))
        menu.addSeparator()
        menu.addAction(f"บันทึก {label} เป็นไฟล์ PDF ใหม่…", self.split_selected)
        menu.addAction(t("menu.split_each", label=label), self.split_selected_each_page)
        menu.addAction(f"บันทึก {label} เป็นรูป…", self.export_images_dialog)
        menu.addSeparator()
        menu.addAction(f"🗑 ลบ {label}", self.delete_selected)
        return menu

    def build_viewer_menu(self) -> QMenu | None:
        """คลิกขวาบนหน้าที่กำลังดู — ทำงานกับหน้านั้นหน้าเดียว"""
        if not self.doc or not self.doc.page_count:
            return None
        self.thumbs.setCurrentRow(self.viewer.index)
        menu = QMenu(self)
        if self.viewer.selected_text:      # มีข้อความที่ลากเลือกไว้ -> ให้คัดลอกได้เลย
            menu.addAction(t("sel.copy"), self.copy_selected_text)
            menu.addAction(t("sel.highlight"), self.highlight_selected_text)
            menu.addSeparator()
        menu.addAction(t("sel.select_all"), self.select_all_text)
        menu.addSeparator()
        menu.addAction("↺ หมุนซ้าย 90°", lambda: self.rotate_selected(-90))
        menu.addAction("↻ หมุนขวา 90°", lambda: self.rotate_selected(90))
        menu.addAction("⟲ หมุน 180°", lambda: self.rotate_selected(180))
        menu.addSeparator()
        menu.addAction("บันทึกหน้านี้เป็นรูป…", self.export_images_dialog)
        menu.addSeparator()
        menu.addAction("🗑 ลบหน้านี้", self.delete_selected)
        return menu

    def _insert_blank_at(self, at: int) -> None:
        self.doc.insert_blank_page(at)
        self._refresh_all(keep_row=at)

    def split_selected_each_page(self) -> None:
        """แยกหน้าที่เลือกออกเป็นไฟล์ละหน้า (เลือก 8 หน้า = 8 ไฟล์)"""
        rows = self._selected_rows()
        if not rows or not self.doc:
            return
        folder = QFileDialog.getExistingDirectory(self, t("split.pick_folder"))
        if not folder:
            return
        from PySide6.QtWidgets import QProgressDialog
        progress = QProgressDialog(t("split.working"), t("bar.cancel"), 0, len(rows), self)
        progress.setWindowModality(Qt.WindowModal)
        cancelled = {"v": False}
        progress.canceled.connect(lambda: cancelled.update(v=True))

        def report(done, count):
            progress.setMaximum(count)
            progress.setValue(done)
            QApplication.processEvents()
            if cancelled["v"]:
                raise RuntimeError(t("split.cancelled"))

        try:
            written = self.doc.split_to_files(folder, per_file=1, indexes=rows, progress=report)
        except RuntimeError as exc:
            self.statusBar().showMessage(str(exc), 5000)
            return
        except Exception as exc:
            QMessageBox.critical(self, t("split.failed"), str(exc))
            return
        finally:
            progress.close()
        QMessageBox.information(self, t("split.title"),
                                t("split.done_many", n=len(written), folder=folder))

    def split_selected(self) -> None:
        """บันทึกเฉพาะหน้าที่เลือกออกเป็นไฟล์ใหม่ (ไม่ต้องพิมพ์ช่วงหน้า)"""
        rows = self._selected_rows()
        if not rows:
            return
        target, _ = QFileDialog.getSaveFileName(
            self, f"บันทึก {len(rows)} หน้าเป็นไฟล์ใหม่", "หน้าที่เลือก.pdf", PDF_FILTER
        )
        if not target:
            return
        try:
            self.doc.extract_to(rows, target)
        except Exception as exc:
            QMessageBox.critical(self, "บันทึกไม่สำเร็จ", str(exc))
            return
        self.statusBar().showMessage(f"บันทึก {len(rows)} หน้าไปที่ {target}", 6000)

    def _on_rows_moved(self, *_args) -> None:
        """ผู้ใช้ลากวางสลับหน้าใน thumbnail — เอาลำดับใหม่ไปเรียงในเอกสารจริง"""
        if self._applying_reorder or not self.doc:
            return
        order = [self.thumbs.item(r).data(Qt.UserRole) for r in range(self.thumbs.count())]
        if len(order) != self.doc.page_count or None in order:
            return

        dropped_at = order.index(order[self.thumbs.currentRow()]) if self.thumbs.currentRow() >= 0 else 0
        self._applying_reorder = True
        try:
            self.doc.reorder_pages(order)
        except ValueError:
            return
        finally:
            self._applying_reorder = False

        self._refresh_all(keep_row=dropped_at)
        self.statusBar().showMessage("ย้ายลำดับหน้าแล้ว — อย่าลืมบันทึก", 5000)

    def _on_page_box(self) -> None:
        try:
            self.goto_page(int(self.page_box.text()) - 1)
        except ValueError:
            self._update_state()

    def goto_page(self, index: int) -> None:
        if self.doc and 0 <= index < self.doc.page_count:
            self.thumbs.setCurrentRow(index)

    def _on_page_changed(self, index: int) -> None:
        """เลื่อน scroll จนหน้าที่มองเห็นเปลี่ยน — อัปเดตเลขหน้า + ไฮไลต์ภาพย่อ (ไม่เลื่อนซ้ำ)"""
        if not self.doc:
            return
        self.page_box.setText(str(index + 1))
        self.thumbs.blockSignals(True)
        self.thumbs.setCurrentRow(index)
        self.thumbs.blockSignals(False)
        self._update_text_panel()

    def _on_page_flip(self, index: int, to_bottom: bool) -> None:
        """หมุนล้อเลยขอบหน้า -> เปลี่ยนหน้า แล้ววาง scroll ให้ต่อเนื่อง
        (ไปหน้าถัดไป = เริ่มบนสุด, ย้อนหน้า = เริ่มล่างสุด)"""
        if not self.doc or not (0 <= index < self.doc.page_count):
            return
        self.goto_page(index)
        vbar = self.viewer.verticalScrollBar()
        vbar.setValue(vbar.maximum() if to_bottom else vbar.minimum())

    def _give_panel_width(self, index: int, width: int) -> None:
        """เปิดแผงข้างแล้วให้ความกว้างเริ่มต้น (ลากปรับได้ทีหลัง)"""
        sizes = self._splitter.sizes()
        if index < len(sizes) and sizes[index] < 20:
            sizes[index] = width
            sizes[2] = max(200, sizes[2] - width)    # เอาพื้นที่จากหน้าเอกสาร
            self._splitter.setSizes(sizes)

    def _toggle_text_panel(self, on: bool) -> None:
        self.text_panel.setVisible(on)
        if on:
            self._give_panel_width(3, 320)
        self._update_text_panel()

    def _update_text_panel(self) -> None:
        if self.text_panel.isVisible() and self.doc and self.doc.page_count:
            self.text_panel.setPlainText(self.doc.page_text(self.viewer.index))

    # ---------------- เปิด / บันทึก / พิมพ์ ----------------

    def _confirm_discard(self) -> bool:
        """ถามก่อนทิ้งงานที่ยังไม่ได้บันทึก — คืน True ถ้าไปต่อได้"""
        if not (self.doc and self.doc.dirty):
            return True
        choice = QMessageBox.question(
            self, "ยังไม่ได้บันทึก",
            "มีการแก้ไขที่ยังไม่ได้บันทึก ต้องการบันทึกก่อนไหม?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if choice == QMessageBox.Cancel:
            return False
        if choice == QMessageBox.Save:
            return self.save_file()
        return True

    def _open_document(self, path: str) -> PdfDocument | None:
        """เปิดไฟล์ + ถามรหัสผ่านถ้าไฟล์เข้ารหัส (คืน None ถ้าเปิดไม่ได้/ยกเลิก)"""
        from app.pdfops import PasswordRequired

        password = None
        while True:
            try:
                return PdfDocument(path, password=password)
            except PasswordRequired as exc:
                prompt = t("pw.wrong") if exc.wrong else t("pw.prompt", name=Path(path).name)
                password, ok = QInputDialog.getText(
                    self, t("pw.title"), prompt, QLineEdit.Password
                )
                if not ok:
                    return None   # ผู้ใช้กดยกเลิก
            except Exception as exc:
                QMessageBox.critical(self, "เปิดไฟล์ไม่สำเร็จ", str(exc))
                return None

    def open_file(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "เปิดไฟล์ PDF", "", PDF_FILTER)
        if not path:
            return
        new_doc = self._open_document(path)
        if new_doc is None:
            return
        if self.doc:
            self.doc.close()
        self.doc = new_doc
        self.viewer.set_document(new_doc)
        self._refresh_all(keep_row=0)
        self.viewer.fit_width()
        self.statusBar().showMessage(f"เปิด {Path(path).name} ({new_doc.page_count} หน้า)", 5000)

    def save_file(self) -> bool:
        if not self.doc:
            return False
        if not self.doc.path:
            return self.save_file_as()
        try:
            self.doc.save()
        except Exception as exc:
            QMessageBox.critical(self, "บันทึกไม่สำเร็จ", str(exc))
            return False
        self._clear_autosave()   # บันทึกจริงแล้ว ลบไฟล์กู้คืนทิ้ง
        self._update_state()
        self.statusBar().showMessage(f"บันทึกแล้ว: {self.doc.path}", 5000)
        return True

    def save_file_as(self) -> bool:
        if not self.doc:
            return False
        suggested = str(self.doc.path) if self.doc.path else "เอกสาร.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "บันทึกเป็น", suggested, PDF_FILTER)
        if not path:
            return False
        try:
            self.doc.save(path)
        except Exception as exc:
            QMessageBox.critical(self, "บันทึกไม่สำเร็จ", str(exc))
            return False
        self._clear_autosave()   # บันทึกจริงแล้ว ลบไฟล์กู้คืนทิ้ง
        self._update_state()
        self.statusBar().showMessage(f"บันทึกแล้ว: {path}", 5000)
        return True

    def _print_pages(self, printer) -> list[int]:
        """หน้าที่จะพิมพ์ตามที่ตั้งไว้ (ทั้งหมด / ช่วงหน้า / รายการหน้าที่ระบุเอง)"""
        total = self.doc.page_count if self.doc else 0
        # หน้าที่หน้าต่างพิมพ์ระบุมา (รองรับช่วงข้ามหน้า เช่น 1-3,7)
        explicit = getattr(self, "_print_only_pages", None)
        if explicit:
            return [i for i in explicit if 0 <= i < total]
        if printer.printRange() == QPrinter.PageRange:
            first = max(1, printer.fromPage())
            last = printer.toPage() or total
            return [i for i in range(first - 1, min(last, total))]
        return list(range(total))

    # จำนวนหน้าต่อแผ่น -> (คอลัมน์, แถว)
    NUP_GRID = {1: (1, 1), 2: (1, 2), 4: (2, 2), 6: (2, 3), 9: (3, 3)}

    def render_print(self, printer) -> None:
        """วาดเอกสารลงเครื่องพิมพ์ (ใช้ทั้งตอนดูตัวอย่างและตอนพิมพ์จริง)

        รองรับการย่อ/ขยาย (พอดีหน้า / ขนาดจริง / ย่อเฉพาะที่ใหญ่เกิน / กำหนด %)
        และวางหลายหน้าต่อแผ่น (2/4/6/9 หน้า)
        """
        if not self.doc or not self.doc.page_count:
            return
        pages = self._print_pages(printer)
        if not pages:
            return
        opts = getattr(self, "_print_opts", None) or {}
        mode = opts.get("size_mode", "fit")
        scale_pct = max(1, int(opts.get("scale", 100))) / 100
        per_sheet = opts.get("per_sheet", 1)
        cols, rows = self.NUP_GRID.get(per_sheet, (1, 1))
        gap = 8 if per_sheet > 1 else 0        # ช่องว่างระหว่างหน้าบนแผ่นเดียวกัน

        painter = QPainter()
        if not painter.begin(printer):
            return
        try:
            dpi = printer.resolution()
            max_zoom = dpi / 72                 # ความละเอียดสูงสุดที่เครื่องพิมพ์ใช้ได้
            sheets = [pages[i:i + per_sheet] for i in range(0, len(pages), per_sheet)]
            # ต้องพิมพ์จากสำเนาที่ฝังข้อความ/ลายเซ็น/ลายน้ำที่ยังลอยอยู่แล้ว
            # ไม่งั้นสิ่งที่เพิ่มไว้จะไม่ออกมาในงานพิมพ์
            with self.doc.flattened() as flat:
                for s, sheet in enumerate(sheets):
                    if s:
                        printer.newPage()
                    view = painter.viewport()
                    cell_w = (view.width() - gap * (cols - 1)) / cols
                    cell_h = (view.height() - gap * (rows - 1)) / rows
                    for k, i in enumerate(sheet):
                        cx = (k % cols) * (cell_w + gap)
                        cy = (k // cols) * (cell_h + gap)
                        page = flat.load_page(i)
                        pw, ph = page.rect.width, page.rect.height
                        if pw <= 0 or ph <= 0:
                            continue
                        # หมุนอัตโนมัติเมื่อหน้ากับช่องวางคนละแนว — ได้ขนาดใหญ่กว่ามาก
                        turn = (opts.get("auto_rotate", True) and mode in ("fit", "shrink")
                                and (pw > ph) != (cell_w > cell_h))
                        if turn:
                            pw, ph = ph, pw
                        # ขนาดที่จะวาดจริง (พิกเซลของเครื่องพิมพ์)
                        fit = min(cell_w / (pw * max_zoom), cell_h / (ph * max_zoom))
                        if mode == "actual":
                            factor = 1.0
                        elif mode == "shrink":
                            factor = min(1.0, fit)     # ย่อเฉพาะหน้าที่ใหญ่เกินกระดาษ
                        elif mode == "custom":
                            factor = scale_pct
                        else:
                            factor = fit               # พอดีหน้ากระดาษ
                        # เรนเดอร์ที่ความละเอียดเท่าที่จะวาดจริง (ไม่เกินของเครื่องพิมพ์)
                        # ทำให้พิกเซลตรง 1:1 คมชัด และไม่กินแรมเกินจำเป็นตอนวางหลายหน้า
                        zoom = min(max_zoom, max_zoom * factor)
                        image = pixmap_to_qimage(
                            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)))
                        if turn:
                            image = image.transformed(QTransform().rotate(90))
                        draw_w = pw * max_zoom * factor
                        draw_h = ph * max_zoom * factor
                        if image.width() != int(draw_w) and draw_w > 0:
                            image = image.scaled(int(draw_w), int(draw_h),
                                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        # จัดกึ่งกลางช่องของมัน (ขนาดจริง/กำหนด % ที่ล้นช่องจะถูกตัดขอบ)
                        x = cx + (cell_w - image.width()) / 2
                        y = cy + (cell_h - image.height()) / 2
                        painter.drawImage(int(x), int(y), image)
        finally:
            painter.end()

    def print_document(self) -> None:
        """หน้าต่างพิมพ์แบบเดียวจบ — ตั้งค่าด้านซ้าย ตัวอย่างด้านขวา (แบบ Chrome/Edge)"""
        if not self.doc or not self.doc.page_count:
            return
        dialog = PrintDialog(self)
        dialog.exec()
        self.statusBar().showMessage(t("print.closed"), 4000)

    # ---------------- ค้นหา ----------------

    def search_next(self) -> None:
        if not self.doc:
            return
        needle = self.search_box.text().strip()
        if not needle:
            return

        if not self.viewer.highlights or getattr(self, "_last_needle", None) != needle:
            self.viewer.highlights = self.doc.search(needle)
            self._last_needle = needle
            self._hit_index = -1
            if not self.viewer.highlights:
                self.statusBar().showMessage(f"ไม่พบคำว่า “{needle}”", 5000)
                self.viewer.refresh()
                return
            self.statusBar().showMessage(f"พบ {len(self.viewer.highlights)} จุด", 5000)

        self._hit_index = (self._hit_index + 1) % len(self.viewer.highlights)
        hit = self.viewer.highlights[self._hit_index]
        self.goto_page(hit.page)
        self.viewer.refresh()
        self.statusBar().showMessage(
            f"จุดที่ {self._hit_index + 1}/{len(self.viewer.highlights)} — หน้า {hit.page + 1}", 5000
        )

    def clear_search(self) -> None:
        self.viewer.highlights = []
        self._last_needle = None
        self.viewer.refresh()

    # ---------------- จัดการหน้า ----------------

    def insert_blank(self) -> None:
        rows = self._selected_rows()
        at = rows[0] if rows else 0
        self.doc.insert_blank_page(at)
        self._refresh_all(keep_row=at)

    def insert_pdf_file(self, at: int | None = None) -> None:
        """แทรกไฟล์ PDF — เลือกได้หลายไฟล์พร้อมกัน (Ctrl/Shift คลิก)

        at=None (เมนูปกติ) = ต่อท้ายหน้าสุดท้าย · ระบุ at = แทรกตรงตำแหน่งนั้น (คลิกขวา)
        """
        # กันค่า checked (bool) ที่ Qt อาจส่งมาแทนตำแหน่ง — bool เป็น int ใน Python
        # ถ้าไม่กัน False จะกลายเป็นตำแหน่ง 0 = แทรกที่หน้า 1 แทนที่จะต่อท้าย
        if not isinstance(at, int) or isinstance(at, bool):
            at = None
        paths, _ = QFileDialog.getOpenFileNames(
            self, t("ins.pick"), "", PDF_FILTER)
        if not paths:
            return
        at = self.doc.page_count if at is None else max(0, min(at, self.doc.page_count))
        # ขนาดหน้าไม่เท่ากัน -> ถามว่าจะปรับให้เท่าเอกสารนี้ไหม (ไม่ถามถ้าขนาดเท่ากันอยู่แล้ว)
        fit = False
        if self.doc.sizes_differ_from(paths, at):
            here = self.doc.describe_size(min(at, self.doc.page_count - 1))
            incoming = self.doc.describe_source_sizes(paths)
            answer = QMessageBox.question(
                self, t("ins.size_title"),
                t("ins.size_ask", here=here, incoming=incoming),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if answer == QMessageBox.Cancel:
                return
            fit = answer == QMessageBox.Yes
        try:
            added = self.doc.insert_pdfs(at, paths, fit_to_page=fit)
        except Exception as exc:
            QMessageBox.critical(self, t("ins.failed"), str(exc))
            return
        self._refresh_all(keep_row=at)
        msg = t("ins.done", files=len(paths), pages=added, at=at + 1)
        if fit and self.doc.fit_failed_pages:
            # บางหน้าโครงสร้างไฟล์ผิดปกติจนปรับขนาดไม่ได้ — ใส่ขนาดเดิมไปแทน ไม่ให้ล้มทั้งงาน
            msg = t("ins.fit_partial", n=self.doc.fit_failed_pages) + " · " + msg
        self.statusBar().showMessage(msg, 9000)

    def delete_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        # ลบหน้าเดียวไม่ต้องถาม (ยังไม่เขียนลงไฟล์จนกว่าจะกดบันทึก) — หลายหน้าค่อยยืนยัน
        if len(rows) > 1 and QMessageBox.question(
            self, "ยืนยันการลบ", f"ลบ {len(rows)} หน้าที่เลือกใช่ไหม?"
        ) != QMessageBox.Yes:
            return
        try:
            self.doc.delete_pages(rows)
        except ValueError as exc:
            QMessageBox.warning(self, "ลบไม่ได้", str(exc))
            return
        self._refresh_all(keep_row=max(0, rows[0] - 1))
        self.statusBar().showMessage(f"ลบ {len(rows)} หน้าแล้ว — ยังไม่ได้บันทึกลงไฟล์", 6000)

    def move_selected(self, delta: int) -> None:
        rows = self._selected_rows()
        if len(rows) != 1:
            QMessageBox.information(self, "ย้ายหน้า", "เลือกทีละ 1 หน้าสำหรับการย้าย")
            return
        src = rows[0]
        dest = src + delta
        if not (0 <= dest < self.doc.page_count):
            return
        # move_page ใส่หน้าไว้ "ก่อน" ตำแหน่ง dest — ตอนเลื่อนลงต้องเผื่ออีก 1
        self.doc.move_page(src, dest + 1 if delta > 0 else dest)
        self._refresh_all(keep_row=dest)

    def rotate_selected(self, degrees: int) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        self.doc.rotate_pages(rows, degrees)
        self._refresh_all(keep_row=rows[0])

    # ---------------- เครื่องมือ ----------------

    def add_merge_files(self, paths: list[str]) -> None:
        """เติมไฟล์เข้าหน้าต่างรวมไฟล์ที่เปิดอยู่ (มาจากตัวอื่นที่ Windows เรียกพร้อมกัน)"""
        lw = getattr(self, "_merge_list", None)
        if lw is None:
            return
        existing = {lw.item(i).text() for i in range(lw.count())}
        for p in paths:
            if p not in existing and Path(p).exists():
                lw.addItem(p)
                existing.add(p)
        lw.sortItems()      # เรียงตามชื่อไฟล์ (ลำดับที่มาถึงไม่แน่นอน)

    def merge_dialog(self, preset_files: list[str] | None = None) -> None:
        """รวมหลายไฟล์เป็นไฟล์เดียว — เลือกหลายไฟล์, จัดลำดับได้ (ไม่ต้องบันทึกไฟล์ปัจจุบันก่อน)

        preset_files = รายการไฟล์ที่ใส่ไว้ให้เลย (ใช้ตอนคลิกขวาหลายไฟล์ใน Explorer)
        """
        from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QListWidget as QLW,
                                       QVBoxLayout)

        dialog = QDialog(self)
        dialog.setWindowTitle(t("mrg.title"))
        dialog.resize(600, 460)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(t("mrg.files")))

        file_list = QLW()
        file_list.setSelectionMode(QLW.ExtendedSelection)
        file_list.setDragDropMode(QLW.InternalMove)     # ลากสลับลำดับได้
        layout.addWidget(file_list)
        # เปิดให้ตัวอื่นที่ Windows เรียกพร้อมกันเติมไฟล์เข้ามาได้ (คลิกขวาหลายไฟล์)
        self._merge_list = file_list

        if preset_files:
            # มาจากคลิกขวาใน Explorer — ใส่ไฟล์ที่เลือกไว้ทั้งหมดตามลำดับชื่อ
            for p in preset_files:
                file_list.addItem(str(p))
        elif self.doc and self.doc.path and self.doc.path.exists():
            # ใส่เอกสารที่เปิดอยู่ให้เป็นตัวแรก (ถ้ามีและบันทึกแล้ว)
            file_list.addItem(str(self.doc.path))

        row = QHBoxLayout()
        add_btn = QPushButton(t("mrg.add"))
        up_btn = QPushButton("▲")
        down_btn = QPushButton("▼")
        del_btn = QPushButton(t("mrg.remove"))
        for b in (add_btn, up_btn, down_btn, del_btn):
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)

        def add_files():
            paths, _ = QFileDialog.getOpenFileNames(dialog, t("mrg.add"), "", PDF_FILTER)
            existing = {file_list.item(i).text() for i in range(file_list.count())}
            for p in paths:
                if p not in existing:
                    file_list.addItem(p)

        def move(delta):
            r = file_list.currentRow()
            if r < 0 or not (0 <= r + delta < file_list.count()):
                return
            item = file_list.takeItem(r)
            file_list.insertItem(r + delta, item)
            file_list.setCurrentRow(r + delta)

        def remove_sel():
            for item in file_list.selectedItems():
                file_list.takeItem(file_list.row(item))

        add_btn.clicked.connect(add_files)
        up_btn.clicked.connect(lambda: move(-1))
        down_btn.clicked.connect(lambda: move(1))
        del_btn.clicked.connect(remove_sel)

        hint = QLabel(t("mrg.hint"))
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("mrg.run"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        try:
            accepted = dialog.exec() == QDialog.Accepted
        finally:
            self._merge_list = None      # ปิดหน้าต่างแล้ว ไม่รับไฟล์เพิ่มอีก
        if not accepted:
            return
        sources = [file_list.item(i).text() for i in range(file_list.count())]
        if len(sources) < 2:
            QMessageBox.information(self, t("mrg.title"), t("mrg.need_two"))
            return

        target, _ = QFileDialog.getSaveFileName(self, t("mrg.save_as"), "รวมไฟล์.pdf", PDF_FILTER)
        if not target:
            return
        self._busy(t("mrg.working"))
        try:
            merge_files(sources, target)
        except Exception as exc:
            QMessageBox.critical(self, t("mrg.failed"), str(exc))
            return
        finally:
            self._done_busy()

        # ถามว่าจะเปิดไฟล์ที่รวมแล้วเลยไหม (คนส่วนใหญ่อยากดูผลทันที)
        if QMessageBox.question(self, t("mrg.title"),
                                t("mrg.done_open", n=len(sources), target=target),
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._open_path(target)
        else:
            self.statusBar().showMessage(t("mrg.done", n=len(sources), target=target), 8000)

    def split_dialog(self) -> None:
        """แยกไฟล์ — หน้าละไฟล์ / ทุก N หน้า / ช่วงหน้าเป็นไฟล์เดียว"""
        if not self.doc or not self.doc.page_count:
            return
        from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QProgressDialog,
                                       QRadioButton, QSpinBox, QVBoxLayout)

        total = self.doc.page_count
        dialog = QDialog(self)
        dialog.setWindowTitle(t("split.title"))
        dialog.resize(460, 260)
        layout = QVBoxLayout(dialog)

        r_each = QRadioButton(t("split.each_page", n=total))
        r_every = QRadioButton(t("split.every_n"))
        r_range = QRadioButton(t("split.range"))
        r_each.setChecked(True)
        layout.addWidget(r_each)

        every_row = QHBoxLayout()
        every_row.addWidget(r_every)
        n_spin = QSpinBox(); n_spin.setRange(2, max(2, total)); n_spin.setValue(2)
        n_spin.setSuffix(" " + t("split.pages_unit"))
        every_row.addWidget(n_spin); every_row.addStretch(1)
        layout.addLayout(every_row)

        layout.addWidget(r_range)
        range_edit = QLineEdit(placeholderText=t("split.range_hint"))
        layout.addWidget(range_edit)

        def sync():
            n_spin.setEnabled(r_every.isChecked())
            range_edit.setEnabled(r_range.isChecked())
        for r in (r_each, r_every, r_range):
            r.toggled.connect(sync)
        sync()

        hint = QLabel(t("split.hint"))
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return

        # ---- ช่วงหน้า -> ไฟล์เดียว (แบบเดิม) ----
        if r_range.isChecked():
            try:
                indexes = parse_page_ranges(range_edit.text(), total)
            except ValueError as exc:
                QMessageBox.warning(self, t("split.bad_range"), str(exc))
                return
            default = str(self.doc.path.with_stem(self.doc.path.stem + "-แยก")) \
                if self.doc.path else "แยกหน้า.pdf"
            target, _ = QFileDialog.getSaveFileName(self, t("split.title"), default, PDF_FILTER)
            if not target:
                return
            try:
                self.doc.extract_to(indexes, target)
            except Exception as exc:
                QMessageBox.critical(self, t("split.failed"), str(exc))
                return
            self.statusBar().showMessage(t("split.done_one", n=len(indexes), target=target), 8000)
            return

        # ---- หน้าละไฟล์ / ทุก N หน้า -> หลายไฟล์ในโฟลเดอร์ ----
        per_file = 1 if r_each.isChecked() else n_spin.value()
        folder = QFileDialog.getExistingDirectory(self, t("split.pick_folder"))
        if not folder:
            return
        expected = (total + per_file - 1) // per_file
        progress = QProgressDialog(t("split.working"), t("bar.cancel"), 0, expected, self)
        progress.setWindowModality(Qt.WindowModal)
        cancelled = {"v": False}
        progress.canceled.connect(lambda: cancelled.update(v=True))

        def report(done, count):
            progress.setMaximum(count)
            progress.setValue(done)
            QApplication.processEvents()
            if cancelled["v"]:
                raise RuntimeError(t("split.cancelled"))

        try:
            written = self.doc.split_to_files(folder, per_file=per_file, progress=report)
        except RuntimeError as exc:
            self.statusBar().showMessage(str(exc), 5000)
            return
        except Exception as exc:
            QMessageBox.critical(self, t("split.failed"), str(exc))
            return
        finally:
            progress.close()

        QMessageBox.information(self, t("split.title"),
                                t("split.done_many", n=len(written), folder=folder))

    def add_numbers_dialog(self) -> None:
        """เพิ่มเลขหน้า — เลือกตำแหน่ง รูปแบบ หน้าที่เริ่มใส่ และเลขเริ่มต้นในหน้าต่างเดียว

        เริ่มใส่ที่หน้าไหนก็ได้ เช่น หน้า 8 ได้เลข 1 (ข้ามหน้าปก/สารบัญ)
        """
        if not self.doc or not self.doc.page_count:
            return
        from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                                       QSpinBox, QVBoxLayout)

        positions = [
            (t("num.bottom_center"), "bottom-center"), (t("num.bottom_right"), "bottom-right"),
            (t("num.bottom_left"), "bottom-left"), (t("num.top_center"), "top-center"),
            (t("num.top_right"), "top-right"), (t("num.top_left"), "top-left"),
        ]
        total = self.doc.page_count

        dialog = QDialog(self)
        dialog.setWindowTitle(t("num.title"))
        dialog.setMinimumWidth(340)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        pos_box = QComboBox()
        for label, key in positions:
            pos_box.addItem(label, key)
        form.addRow(t("num.position"), pos_box)

        fmt_box = QComboBox()
        fmt_box.setEditable(True)   # พิมพ์รูปแบบเองได้ เช่น "Page {page} of {total}"
        fmt_box.addItems(["{page}/{total}", "{page}", "หน้า {page}", "- {page} -"])
        form.addRow(t("num.format"), fmt_box)

        first_spin = QSpinBox(); first_spin.setRange(1, total); first_spin.setValue(1)
        first_spin.setSuffix(t("num.of_total", n=total))
        form.addRow(t("num.first_page"), first_spin)

        start_spin = QSpinBox(); start_spin.setRange(0, 9999); start_spin.setValue(1)
        form.addRow(t("num.start_at"), start_spin)
        layout.addLayout(form)

        hint = QLabel()
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        def update_hint() -> None:
            first, start = first_spin.value(), start_spin.value()
            last = start + (total - first)
            skipped = t("num.hint_skip", n=first - 1) if first > 1 else ""
            hint.setText(t("num.hint", first=first, start=start, end=total, last=last) + skipped)

        first_spin.valueChanged.connect(update_hint)
        start_spin.valueChanged.connect(update_hint)
        update_hint()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return

        fmt = fmt_box.currentText().strip() or "{page}"
        try:
            self.doc.add_page_numbers(fmt=fmt, position=pos_box.currentData(),
                                      start_at=start_spin.value(),
                                      first_page=first_spin.value() - 1)
        except (KeyError, IndexError, ValueError) as exc:
            # รูปแบบพิมพ์ผิด เช่น {pages} หรือวงเล็บไม่ครบ
            QMessageBox.warning(self, t("num.title"), t("num.bad_format", err=exc))
            return
        except RuntimeError as exc:   # ไม่พบฟอนต์ไทย
            QMessageBox.warning(self, t("num.title"), str(exc))
            return
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("num.done"), 6000)

    def export_images_dialog(self) -> None:
        rows = self._selected_rows()
        scope, ok = QInputDialog.getItem(
            self, "บันทึกเป็นรูป", "ขอบเขต:",
            [f"เฉพาะหน้าที่เลือก ({len(rows)} หน้า)", f"ทุกหน้า ({self.doc.page_count} หน้า)"], 0, False,
        )
        if not ok:
            return
        indexes = rows if scope.startswith("เฉพาะ") else list(range(self.doc.page_count))

        fmt, ok = QInputDialog.getItem(self, "บันทึกเป็นรูป", "นามสกุลไฟล์:", ["jpg", "png"], 0, False)
        if not ok:
            return
        dpi, ok = QInputDialog.getInt(self, "บันทึกเป็นรูป", "ความละเอียด (DPI):", 150, 72, 600, 1)
        if not ok:
            return
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์ปลายทาง")
        if not folder:
            return
        try:
            written = self.doc.export_images(indexes, folder, dpi=dpi, fmt=fmt)
        except Exception as exc:
            QMessageBox.critical(self, "บันทึกรูปไม่สำเร็จ", str(exc))
            return
        self.statusBar().showMessage(f"บันทึก {len(written)} รูปไปที่ {folder}", 6000)

    def _ask_scope(self, title: str) -> list[int] | None:
        """ถามว่าจะทำกับหน้าไหน — ทุกหน้า / หน้าที่เลือก / หน้าปัจจุบัน / ระบุช่วงเอง"""
        rows = self._selected_rows()
        total = self.doc.page_count
        current = self.viewer.index

        opt_all = t("scope.all", n=total)
        opt_current = t("scope.current", n=current + 1)
        opt_selected = t("scope.selected", n=len(rows))
        opt_range = t("scope.range")

        options = [opt_all, opt_current]
        # เสนอ "หน้าที่เลือก" เฉพาะเมื่อเลือกไว้มากกว่า 1 หน้า (ไม่งั้นซ้ำกับหน้าปัจจุบัน)
        if len(rows) > 1:
            options.append(opt_selected)
        options.append(opt_range)

        choice, ok = QInputDialog.getItem(self, title, t("scope.which"), options, 0, False)
        if not ok:
            return None
        if choice == opt_all:
            return list(range(total))
        if choice == opt_current:
            return [current]
        if choice == opt_selected:
            return rows
        # ระบุช่วงหน้าเอง เช่น 3 หรือ 2-5,8
        spec, ok = QInputDialog.getText(
            self, title, t("scope.range_prompt", n=total), text=str(current + 1))
        if not ok:
            return None
        try:
            return parse_page_ranges(spec, total)
        except ValueError as exc:
            QMessageBox.warning(self, title, str(exc))
            return None

    def compress_dialog(self) -> None:
        """บีบอัดลดขนาดไฟล์ PDF"""
        if not self.doc or not self.doc.page_count:
            return
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QComboBox, QVBoxLayout

        dialog = QDialog(self)
        dialog.setWindowTitle(t("cmp.title"))
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        level = QComboBox()
        # (label, quality, dpi)
        levels = [
            (t("cmp.low"), 75, 150),
            (t("cmp.medium"), 60, 120),
            (t("cmp.high"), 40, 96),
        ]
        for label, _, _ in levels:
            level.addItem(label)
        level.setCurrentIndex(1)
        form.addRow(t("cmp.level"), level)
        layout.addLayout(form)
        hint = QLabel(t("cmp.hint"))
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("cmp.run"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return

        _, quality, dpi = levels[level.currentIndex()]
        default = str(self.doc.path.with_stem(self.doc.path.stem + "-compressed")) \
            if self.doc.path else "compressed.pdf"
        target, _ = QFileDialog.getSaveFileName(self, t("cmp.title"), default, PDF_FILTER)
        if not target:
            return
        self._busy(t("cmp.working"))
        try:
            old, new = self.doc.compress(target, image_quality=quality, downsample_dpi=dpi)
        except Exception as exc:
            QMessageBox.critical(self, t("cmp.title"), str(exc))
            return
        finally:
            self._done_busy()
        pct = 100 - new * 100 // old if old else 0
        QMessageBox.information(
            self, t("cmp.done_title"),
            t("cmp.done", old=self._fmt_size(old), new=self._fmt_size(new), pct=pct, target=target))

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ("B", "KB", "MB"):
            if n < 1024 or unit == "MB":
                return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
            n /= 1024
        return f"{n:.1f} MB"

    def crop_dialog(self) -> None:
        """ครอบตัดหน้า — ระบุระยะขอบที่จะตัดออก (%)"""
        if not self.doc or not self.doc.page_count:
            return
        from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QSpinBox,
                                       QVBoxLayout)

        indexes = self._ask_scope(t("crop.title"))
        if indexes is None:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(t("crop.title"))
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        spins = {}
        for key, label in (("top", t("crop.top")), ("bottom", t("crop.bottom")),
                           ("left", t("crop.left")), ("right", t("crop.right"))):
            sp = QSpinBox(); sp.setRange(0, 45); sp.setSuffix(" %")
            form.addRow(label, sp)
            spins[key] = sp
        layout.addLayout(form)
        hint = QLabel(t("crop.hint"))
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return

        margins = (spins["left"].value() / 100, spins["top"].value() / 100,
                   spins["right"].value() / 100, spins["bottom"].value() / 100)
        if not any(margins):
            return
        self.doc.crop_pages(indexes, margins)
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("crop.done", n=len(indexes)), 6000)

    def watermark_dialog(self) -> None:
        """ใส่/แก้ลายน้ำข้อความ — ปรับได้ทุกค่าพร้อมดูตัวอย่างสดๆ

        ลายน้ำเก็บเป็นวัตถุลอย ยังแก้ไขได้เรื่อยๆ จนกว่าจะกดบันทึก (เหมือนลายเซ็น/ข้อความ)
        """
        if not self.doc or not self.doc.page_count:
            return
        from PySide6.QtWidgets import (QCheckBox, QColorDialog, QDialog, QDialogButtonBox,
                                       QFormLayout, QSlider, QSpinBox, QVBoxLayout)

        existing = self.doc.watermark
        editing = existing is not None
        original = existing.copy() if existing else None   # ไว้คืนค่าถ้ากดยกเลิก

        # หน้าที่จะใส่ (ถามเฉพาะตอนเพิ่มใหม่ ตอนแก้ใช้ของเดิม)
        if editing:
            indexes = None if original.indexes is None else list(original.indexes)
        else:
            indexes = self._ask_scope(t("wm.title_add"))
            if indexes is None:
                return
            if len(indexes) == self.doc.page_count:
                indexes = None      # ทุกหน้า

        dialog = QDialog(self)
        dialog.setWindowTitle(t("wm.title_edit") if editing else t("wm.title_add"))
        dialog.resize(420, 300)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        text_edit = QLineEdit(original.text if editing else "สำเนา")
        form.addRow(t("wm.text"), text_edit)

        opacity = QSlider(Qt.Horizontal)
        opacity.setRange(5, 100)
        opacity.setValue(int((original.opacity if editing else 0.18) * 100))
        op_label = QLabel(f"{opacity.value()}%")
        op_row = QHBoxLayout(); op_row.addWidget(opacity); op_row.addWidget(op_label)
        form.addRow(t("wm.opacity"), op_row)

        angle = QSlider(Qt.Horizontal)
        angle.setRange(-90, 90)
        angle.setValue(int(original.angle if editing else 45))
        ang_label = QLabel(f"{angle.value()}°")
        ang_row = QHBoxLayout(); ang_row.addWidget(angle); ang_row.addWidget(ang_label)
        form.addRow(t("wm.angle"), ang_row)

        auto_size = QCheckBox(t("wm.auto_size"))
        auto_size.setChecked(not editing or original.font_size is None)
        size_spin = QSpinBox()
        size_spin.setRange(8, 400)
        size_spin.setValue(int(original.font_size) if (editing and original.font_size) else 72)
        size_spin.setEnabled(not auto_size.isChecked())
        size_row = QHBoxLayout(); size_row.addWidget(auto_size); size_row.addWidget(size_spin)
        form.addRow(t("wm.size"), size_row)

        chosen = {"color": original.color if editing else (0.5, 0.5, 0.5)}
        color_btn = QPushButton(t("wm.color_pick"))
        swatch = QLabel("      ")

        def paint_swatch():
            r, g, b = chosen["color"]
            swatch.setStyleSheet(
                f"background:rgb({int(r*255)},{int(g*255)},{int(b*255)}); border:1px solid #888;")
        paint_swatch()
        col_row = QHBoxLayout(); col_row.addWidget(color_btn); col_row.addWidget(swatch)
        col_row.addStretch(1)
        form.addRow(t("wm.color"), col_row)
        layout.addLayout(form)

        hint = QLabel(t("wm.hint"))
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        if editing:
            remove_btn = buttons.addButton(t("wm.remove"), QDialogButtonBox.DestructiveRole)
            remove_btn.clicked.connect(lambda: (dialog.done(2)))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # ---- ตัวอย่างสด: เปลี่ยนค่าแล้วเห็นบนหน้าจอทันที (ยังไม่ push undo) ----
        def preview():
            op_label.setText(f"{opacity.value()}%")
            ang_label.setText(f"{angle.value()}°")
            size_spin.setEnabled(not auto_size.isChecked())
            body = text_edit.text().strip()
            if not body:
                self.doc.watermark = None
            else:
                self.doc.watermark = pdfops.Watermark(
                    text=body, indexes=indexes,
                    opacity=opacity.value() / 100, angle=float(angle.value()),
                    color=chosen["color"],
                    font_size=None if auto_size.isChecked() else float(size_spin.value()),
                )
            self.viewer.refresh()

        def pick_color():
            r, g, b = chosen["color"]
            col = QColorDialog.getColor(
                QColor(int(r * 255), int(g * 255), int(b * 255)), dialog, t("wm.color_pick"))
            if col.isValid():
                chosen["color"] = (col.redF(), col.greenF(), col.blueF())
                paint_swatch()
                preview()

        color_btn.clicked.connect(pick_color)
        text_edit.textChanged.connect(preview)
        opacity.valueChanged.connect(preview)
        angle.valueChanged.connect(preview)
        size_spin.valueChanged.connect(preview)
        auto_size.toggled.connect(preview)
        preview()

        result = dialog.exec()
        settings = self.doc.watermark.copy() if self.doc.watermark else None
        self.doc.watermark = original          # คืนค่าเดิมก่อน แล้วค่อยลงจริงผ่าน undo
        self.viewer.refresh()

        if result == 2:                         # กดลบลายน้ำ
            self.doc.remove_watermark()
            self._refresh_all(keep_row=self.viewer.index)
            self.statusBar().showMessage(t("wm.removed"), 6000)
            return
        if result != QDialog.Accepted or settings is None:
            return

        try:
            if editing:
                self.doc.update_watermark(
                    text=settings.text, opacity=settings.opacity, angle=settings.angle,
                    color=settings.color, font_size=settings.font_size)
            else:
                self.doc.set_watermark(
                    settings.text, indexes, opacity=settings.opacity, angle=settings.angle,
                    color=settings.color, font_size=settings.font_size)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, t("wm.title_add"), str(exc))
            return
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("wm.applied"), 7000)

    def image_watermark_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "เลือกรูปลายน้ำ", "", IMAGE_FILTER)
        if not path:
            return
        indexes = self._ask_scope("ใส่ลายน้ำจากรูป")
        if indexes is None:
            return
        try:
            path = PdfDocument.prepare_image(path)
        except Exception as exc:
            QMessageBox.critical(self, "เปิดไฟล์รูปไม่สำเร็จ", str(exc))
            return
        percent, ok = QInputDialog.getInt(
            self, "ใส่ลายน้ำจากรูป", "ขนาดเทียบกับความกว้างหน้า (%):", 50, 5, 100, 5
        )
        if not ok:
            return
        try:
            self.doc.add_image_watermark(path, indexes, scale=percent / 100)
        except Exception as exc:
            QMessageBox.critical(self, "ใส่ลายน้ำไม่สำเร็จ", str(exc))
            return
        self._refresh_all()
        self.statusBar().showMessage(f"ใส่ลายน้ำรูป {len(indexes)} หน้าแล้ว", 7000)

    # ---------------- แปลงไฟล์ ----------------

    def _busy(self, message: str) -> None:
        self.statusBar().showMessage(message, 0)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()

    def _done_busy(self) -> None:
        QApplication.restoreOverrideCursor()

    def ocr_dialog(self) -> None:
        """ทำ OCR — ได้ทั้งไฟล์ PDF ที่ค้นหาได้ หรือดึงเป็นข้อความอย่างเดียว"""
        try:
            pdfops.ensure_tesseract()
        except RuntimeError as exc:
            QMessageBox.warning(self, "ยังทำ OCR ไม่ได้", str(exc))
            return

        indexes = self._ask_scope("OCR อ่านข้อความ")
        if indexes is None:
            return

        scanned = sum(1 for i in indexes if self.doc.needs_ocr(i))
        if scanned == 0 and QMessageBox.question(
            self, "หน้าเหล่านี้มีข้อความอยู่แล้ว",
            "หน้าที่เลือกมีข้อความที่คัดลอกได้อยู่แล้ว (ไม่น่าใช่ไฟล์สแกน)\n"
            "ยังต้องการทำ OCR อยู่ไหม?",
        ) != QMessageBox.Yes:
            return

        langs = pdfops.ocr_languages()
        options = []
        if "tha" in langs and "eng" in langs:
            options.append("ไทย + อังกฤษ")
        if "tha" in langs:
            options.append("ไทยอย่างเดียว")
        if "eng" in langs:
            options.append("อังกฤษอย่างเดียว")
        choice, ok = QInputDialog.getItem(self, "OCR", "ภาษาในเอกสาร:", options, 0, False)
        if not ok:
            return
        language = {
            "ไทย + อังกฤษ": "tha+eng", "ไทยอย่างเดียว": "tha", "อังกฤษอย่างเดียว": "eng",
        }[choice]

        mode, ok = QInputDialog.getItem(
            self, "OCR", "ต้องการผลลัพธ์แบบไหน:",
            ["สร้าง PDF ที่ค้นหา/คัดลอกข้อความได้", "ดึงเป็นไฟล์ข้อความ (.txt)"], 0, False,
        )
        if not ok:
            return

        if mode.startswith("ดึงเป็นไฟล์ข้อความ"):
            target, _ = QFileDialog.getSaveFileName(
                self, "บันทึกข้อความเป็น", "ข้อความ-ocr.txt", "ไฟล์ข้อความ (*.txt)")
            if not target:
                return
            self._busy("กำลังอ่านข้อความ… (หน้าละไม่กี่วินาที)")
            try:
                chunks = []
                for order, i in enumerate(indexes, start=1):
                    self.statusBar().showMessage(
                        f"กำลังอ่านหน้า {i + 1} ({order}/{len(indexes)})…", 0)
                    QApplication.processEvents()
                    chunks.append(f"--- หน้า {i + 1} ---\n{self.doc.ocr_text(i, language)}")
                Path(target).write_text("\n\n".join(chunks), encoding="utf-8")
            except Exception as exc:
                QMessageBox.critical(self, "OCR ไม่สำเร็จ", str(exc))
                return
            finally:
                self._done_busy()
            self.statusBar().showMessage(f"บันทึกข้อความไปที่ {target}", 8000)
            return

        default = str(self.doc.path.with_stem(self.doc.path.stem + "-ocr")) \
            if self.doc.path else "เอกสาร-ocr.pdf"
        target, _ = QFileDialog.getSaveFileName(self, "บันทึก PDF ที่ค้นหาได้เป็น", default, PDF_FILTER)
        if not target:
            return

        self._busy("กำลังทำ OCR…")
        try:
            def report(done: int, total: int) -> None:
                self.statusBar().showMessage(f"กำลังทำ OCR หน้า {done}/{total}…", 0)
                QApplication.processEvents()

            self.doc.ocr_to_searchable(target, indexes, language, progress=report)
        except Exception as exc:
            QMessageBox.critical(self, "OCR ไม่สำเร็จ", str(exc))
            return
        finally:
            self._done_busy()

        self.statusBar().showMessage(f"ทำ OCR เสร็จแล้ว: {target}", 9000)
        if QMessageBox.question(
            self, "เสร็จแล้ว", f"สร้างไฟล์ที่ค้นหาข้อความได้แล้ว\n{target}\n\nเปิดไฟล์นี้เลยไหม?"
        ) == QMessageBox.Yes:
            self._open_path(target)

    def _open_path(self, path: str) -> None:
        if not self._confirm_discard():
            return
        new_doc = self._open_document(path)
        if new_doc is None:
            return
        if self.doc:
            self.doc.close()
        self.doc = new_doc
        self.viewer.set_document(new_doc)
        self._refresh_all(keep_row=0)
        self.viewer.fit_width()
        # ไฟล์เสียแล้วโปรแกรมซ่อมให้ — บอกผู้ใช้ว่าต้องกดบันทึกเพื่อเก็บผลการซ่อม
        if getattr(new_doc, "repaired_on_open", False):
            QMessageBox.information(
                self, t("repair.title"), t("repair.done", n=new_doc.page_count))
            self.statusBar().showMessage(t("repair.hint"), 0)

    def export_word(self) -> None:
        indexes = self._ask_scope("แปลงเป็น Word")
        if indexes is None:
            return
        default = str(self.doc.path.with_suffix(".docx")) if self.doc.path else "เอกสาร.docx"
        target, _ = QFileDialog.getSaveFileName(
            self, "บันทึกเป็น Word", default, "ไฟล์ Word (*.docx)")
        if not target:
            return

        self._busy("กำลังแปลงเป็น Word… (ไฟล์ใหญ่อาจใช้เวลาสักครู่)")
        try:
            self.doc.to_word(target, indexes)
        except Exception as exc:
            QMessageBox.critical(self, "แปลงไม่สำเร็จ", str(exc))
            return
        finally:
            self._done_busy()
        self.statusBar().showMessage(f"แปลงเป็น Word แล้ว: {target}", 8000)

    def export_excel(self) -> None:
        indexes = self._ask_scope("ดึงตารางเป็น Excel")
        if indexes is None:
            return
        default = str(self.doc.path.with_suffix(".xlsx")) if self.doc.path else "ตาราง.xlsx"
        target, _ = QFileDialog.getSaveFileName(
            self, "บันทึกเป็น Excel", default, "ไฟล์ Excel (*.xlsx)")
        if not target:
            return

        self._busy("กำลังดึงตาราง…")
        try:
            count = self.doc.to_excel(target, indexes)
        except ValueError as exc:
            QMessageBox.information(self, "ไม่พบตาราง", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "ดึงตารางไม่สำเร็จ", str(exc))
            return
        finally:
            self._done_busy()
        self.statusBar().showMessage(f"ดึง {count} ตารางไปที่ {target}", 8000)

    def export_embedded_images(self) -> None:
        indexes = self._ask_scope("ดึงรูปภาพในไฟล์")
        if indexes is None:
            return
        folder = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์ปลายทาง")
        if not folder:
            return

        self._busy("กำลังดึงรูปภาพ…")
        try:
            written = self.doc.extract_images(indexes, folder)
        except Exception as exc:
            QMessageBox.critical(self, "ดึงรูปไม่สำเร็จ", str(exc))
            return
        finally:
            self._done_busy()

        if not written:
            QMessageBox.information(
                self, "ไม่พบรูปภาพ",
                "ไม่พบรูปที่ฝังอยู่ในหน้าที่เลือก\n"
                "(ถ้าอยากได้ภาพของทั้งหน้า ให้ใช้ 'บันทึกหน้าเป็นรูป' แทน)",
            )
            return
        self.statusBar().showMessage(f"ดึง {len(written)} รูปไปที่ {folder}", 8000)

    # ---------------- คลังลายเซ็น ----------------

    def _build_signature_menu(self) -> None:
        """สร้างเมนูลายเซ็นใหม่ทุกครั้งที่เปิด (คลังอาจเปลี่ยน)"""
        self.sig_menu.clear()
        saved = library.list_signatures()
        has_doc = self.doc is not None and self.doc.page_count > 0

        if saved:
            for path in saved:
                action = self.sig_menu.addAction(QIcon(str(path)), path.stem)
                action.setEnabled(has_doc)
                action.triggered.connect(lambda _=False, p=path: self.use_saved_signature(p))
            self.sig_menu.addSeparator()
        else:
            empty = self.sig_menu.addAction(t("lib.empty"))
            empty.setEnabled(False)
            self.sig_menu.addSeparator()

        add = self.sig_menu.addAction(t("lib.add"))
        add.triggered.connect(self.add_signature_to_library)
        once = self.sig_menu.addAction(t("lib.use_once"))
        once.setEnabled(has_doc)
        once.triggered.connect(self.signature_dialog)
        if saved:
            manage = self.sig_menu.addAction(t("lib.manage"))
            manage.triggered.connect(self.manage_signatures)

    def use_saved_signature(self, path) -> None:
        """คลิกลายเซ็นจากคลัง = เข้าโหมดวางทันที (รูปเตรียมไว้แล้วตอนบันทึกเข้าคลัง)"""
        if not self.doc:
            return
        self.deselect_stamp()
        self._pending_image = str(path)
        self.viewer.start_placing(str(path))
        self.viewer.overlay.committed.connect(self.commit_placement)
        self._placing_bar.show()
        self.statusBar().showMessage(
            f"กำลังวาง “{Path(path).stem}” — ลากย้าย/ลากมุมย่อขยาย แล้วกด Enter", 0
        )

    def add_signature_to_library(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "เลือกไฟล์ลายเซ็นที่จะเก็บเข้าคลัง", "", IMAGE_FILTER
        )
        if not path:
            return
        name, ok = QInputDialog.getText(
            self, "ตั้งชื่อลายเซ็น", "ชื่อที่จะใช้เรียก:", text=Path(path).stem
        )
        if not ok or not name.strip():
            return
        try:
            prepared = PdfDocument.prepare_image(path)   # ลบพื้นหลังก่อนเก็บ
            saved = library.save_signature(prepared, name)
        except Exception as exc:
            QMessageBox.critical(self, "บันทึกลายเซ็นไม่สำเร็จ", str(exc))
            return
        self.statusBar().showMessage(
            f"เก็บ “{saved.stem}” เข้าคลังแล้ว — เรียกใช้จากปุ่ม ✒ ลายเซ็น", 7000
        )

    def manage_signatures(self) -> None:
        saved = library.list_signatures()
        if not saved:
            return
        names = [p.stem for p in saved]
        choice, ok = QInputDialog.getItem(
            self, "จัดการคลังลายเซ็น", "เลือกลายเซ็น:", names, 0, False
        )
        if not ok:
            return
        target = saved[names.index(choice)]

        action, ok = QInputDialog.getItem(
            self, "จัดการคลังลายเซ็น", f"จะทำอะไรกับ “{choice}”:",
            ["เปลี่ยนชื่อ", "ลบออกจากคลัง"], 0, False,
        )
        if not ok:
            return

        if action == "เปลี่ยนชื่อ":
            new_name, ok = QInputDialog.getText(self, "เปลี่ยนชื่อ", "ชื่อใหม่:", text=choice)
            if not ok or not new_name.strip():
                return
            try:
                library.rename_signature(target, new_name)
            except ValueError as exc:
                QMessageBox.warning(self, "เปลี่ยนชื่อไม่ได้", str(exc))
                return
            self.statusBar().showMessage(f"เปลี่ยนชื่อเป็น “{new_name}” แล้ว", 5000)
        else:
            if QMessageBox.question(
                self, "ยืนยันการลบ", f"ลบ “{choice}” ออกจากคลังใช่ไหม?"
            ) != QMessageBox.Yes:
                return
            library.delete_signature(target)
            self.statusBar().showMessage(f"ลบ “{choice}” ออกจากคลังแล้ว", 5000)

    def insert_image_dialog(self) -> None:
        """แทรกรูปภาพลงหน้า แล้วลากย้าย/ย่อขยายได้ (คงพื้นหลังเดิมของรูป)

        ต่างจาก "ใส่ลายเซ็น" ที่ลบพื้นหลังขาวออกให้ — รูปถ่าย/สกรีนช็อตต้องคงพื้นหลังไว้
        ไม่งั้นส่วนที่เป็นสีขาวในรูปจะกลายเป็นรูโปร่งใส
        """
        path, _ = QFileDialog.getOpenFileName(
            self, t("img.pick"), "", IMAGE_FILTER)
        if not path:
            return
        try:
            # remove_background=False = คงรูปตามเดิม (ไฟล์ png/jpg ใช้ไฟล์เดิมได้เลย)
            path = PdfDocument.prepare_image(path, remove_background=False)
        except Exception as exc:
            QMessageBox.critical(self, t("img.failed"), str(exc))
            return
        self._start_image_placement(path, t("img.placing"))

    def signature_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "เลือกไฟล์ลายเซ็น / ตราประทับ (แนะนำ PNG พื้นหลังใส)", "", IMAGE_FILTER
        )
        if not path:
            return
        try:
            path = PdfDocument.prepare_image(path)   # .gif/.webp/.tif -> PNG
        except Exception as exc:
            QMessageBox.critical(self, "เปิดไฟล์รูปไม่สำเร็จ", str(exc))
            return
        self._start_image_placement(
            path,
            "ลากตรงกลางเพื่อย้าย · ลากมุมเพื่อย่อ/ขยาย · Enter หรือดับเบิลคลิก = ยืนยัน · Esc = ยกเลิก")

    def _start_image_placement(self, path: str, hint: str) -> None:
        """เข้าโหมดวางรูป (ใช้ร่วมกันทั้งลายเซ็นและรูปภาพทั่วไป)"""
        self.deselect_stamp()
        self._pending_image = path
        self.viewer.start_placing(path)
        self.viewer.overlay.committed.connect(self.commit_placement)
        self._placing_bar.show()
        self.statusBar().showMessage(hint, 0)

    def commit_placement(self) -> None:
        """ยืนยันตำแหน่ง/ขนาดที่ปรับไว้"""
        rect = self.viewer.placement_rect()
        image = self._pending_image
        editing = self.viewer.editing_stamp
        editing_tb = self.viewer.editing_textbox
        page_index = self.viewer.index
        self.cancel_placement(quiet=True)
        if rect is None or not self.doc:
            return

        if editing_tb is not None:      # ย้าย/ปรับขนาดกล่องข้อความ
            old = editing_tb.rect
            # ย่อ/ขยายกล่อง = ปรับขนาดตัวอักษรตามส่วนสูงด้วย (ไม่งั้นตัวอักษรไม่เปลี่ยน)
            new_size = None
            if old.height > 1 and abs(rect.height - old.height) > 0.5:
                new_size = max(4.0, editing_tb.font_size * (rect.height / old.height))
            self.doc.update_textbox_rect(editing_tb, rect, font_size=new_size)
            self.viewer.selected_textbox = editing_tb
            self._refresh_all(keep_row=page_index)
            self._text_bar.show()
            self.statusBar().showMessage(t("text.moved"), 6000)
            return

        try:
            if editing is not None:
                self.doc.update_stamp(editing, rect)
                self.viewer.selected_stamp = editing
                message = "ย้าย/ปรับขนาดรูปแล้ว"
            else:
                if not image:
                    return
                stamp = self.doc.add_stamp(page_index, image, rect)
                self.viewer.selected_stamp = stamp
                message = "วางรูปแล้ว — คลิกที่รูปเพื่อย้าย/ปรับขนาดได้อีก"
        except Exception as exc:
            QMessageBox.critical(self, "วางรูปไม่สำเร็จ", str(exc))
            return
        self._refresh_all(keep_row=page_index)
        self.statusBar().showMessage(message, 7000)

    def _on_stamp_selected(self) -> None:
        """คลิกโดนลายเซ็นที่วางไว้ — โชว์แถบให้ย้าย/ปรับขนาด/ลบ"""
        self._stamp_bar.show()
        self.viewer.refresh()
        self.statusBar().showMessage(
            "เลือกรูป/ลายเซ็นแล้ว — กด 'ย้าย/ปรับขนาด' หรือ Delete เพื่อลบ", 6000
        )

    def edit_selected_stamp(self) -> None:
        stamp = self.viewer.selected_stamp
        if stamp is None:
            return
        self._stamp_bar.hide()
        self.viewer.start_editing(stamp)
        self.viewer.overlay.committed.connect(self.commit_placement)
        self._placing_bar.show()

    def stamp_selected_all_pages(self) -> None:
        """วางลายเซ็นที่เลือกอยู่ ตำแหน่งเดิม ทุกหน้า (หรือหน้าที่เลือกไว้)"""
        stamp = self.viewer.selected_stamp
        if stamp is None or not self.doc:
            return
        indexes = self._ask_scope(t("bar.stamp_all_pages"))
        if indexes is None:
            return
        # ไม่ต้องวางซ้ำหน้าที่มีลายเซ็นตำแหน่งเดียวกันอยู่แล้ว
        targets = [i for i in indexes
                   if not any(s.image_path == stamp.image_path and s.rect == stamp.rect
                              for s in self.doc.stamps_on(i))]
        if not targets:
            return
        n = self.doc.add_stamp_all_pages(stamp.image_path, stamp.rect, targets)
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("bar.stamped_all", n=n), 6000)

    def save_stamp_to_library(self) -> None:
        """เก็บลายเซ็นที่เลือกอยู่เข้าคลัง"""
        stamp = self.viewer.selected_stamp
        if stamp is None:
            return
        name, ok = QInputDialog.getText(
            self, "เก็บลายเซ็นเข้าคลัง", "ชื่อที่จะใช้เรียก:",
            text=Path(stamp.image_path).stem.replace("pdftool-sig-", "ลายเซ็น"),
        )
        if not ok or not name.strip():
            return
        try:
            saved = library.save_signature(stamp.image_path, name)
        except Exception as exc:
            QMessageBox.critical(self, "เก็บเข้าคลังไม่สำเร็จ", str(exc))
            return
        self.statusBar().showMessage(
            f"เก็บ “{saved.stem}” เข้าคลังแล้ว — ครั้งหน้าเรียกจากปุ่ม ✒ ลายเซ็น ได้เลย", 7000
        )

    def delete_selected_stamp(self) -> None:
        stamp = self.viewer.selected_stamp
        if stamp is None or not self.doc:
            return
        self.doc.remove_stamp(stamp)
        self.viewer.selected_stamp = None
        self._stamp_bar.hide()
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage("ลบรูปแล้ว — Ctrl+Z เพื่อเอากลับ", 6000)

    def cancel_placement(self, quiet: bool = False) -> None:
        self.viewer.cancel_placing()
        self._pending_image = None
        self._placing_bar.hide()
        if not quiet:
            self.statusBar().showMessage("ยกเลิกการวางรูปแล้ว", 4000)

    # ---------------- กรอกแบบฟอร์ม PDF ----------------

    def fill_form_dialog(self) -> None:
        if not self.doc or not self.doc.page_count:
            return
        if not self.doc.is_form():
            QMessageBox.information(self, t("form.none_title"), t("form.none"))
            return
        fields = [f for f in self.doc.form_fields() if f["name"]]
        if not fields:
            QMessageBox.information(self, t("form.none_title"), t("form.none"))
            return

        from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                                       QFormLayout, QLineEdit, QScrollArea, QVBoxLayout)

        dialog = QDialog(self)
        dialog.setWindowTitle(t("form.title"))
        dialog.resize(480, 560)
        outer = QVBoxLayout(dialog)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        editors = []   # (field, getter)
        has_thai_text = False
        for f in fields:
            label = f"{f['name']}  (หน้า {f['page'] + 1})"
            ftype = f["type"]
            if ftype == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                cb = QCheckBox()
                cb.setChecked(f["value"] not in ("Off", "", None, False))
                form.addRow(label, cb)
                editors.append((f, lambda cb=cb: cb.isChecked()))
            elif ftype in (fitz.PDF_WIDGET_TYPE_COMBOBOX, fitz.PDF_WIDGET_TYPE_LISTBOX) and f["choices"]:
                combo = QComboBox()
                combo.addItems(f["choices"])
                if f["value"] in f["choices"]:
                    combo.setCurrentText(f["value"])
                form.addRow(label, combo)
                editors.append((f, lambda combo=combo: combo.currentText()))
            else:
                edit = QLineEdit(str(f["value"] or ""))
                form.addRow(label, edit)
                editors.append((f, lambda edit=edit: edit.text()))

        tip = QLabel(t("form.thai_tip"))
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#664d03;")
        outer.addWidget(tip)

        buttons = QDialogButtonBox()
        editable_btn = buttons.addButton(t("form.fill_editable"), QDialogButtonBox.AcceptRole)
        flatten_btn = buttons.addButton(t("form.fill_flatten"), QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        mode = {"flatten": False}
        editable_btn.clicked.connect(lambda: (mode.update(flatten=False), dialog.accept()))
        flatten_btn.clicked.connect(lambda: (mode.update(flatten=True), dialog.accept()))
        buttons.rejected.connect(dialog.reject)
        outer.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        updates = [(f["page"], f["xref"], getter()) for f, getter in editors]
        try:
            if mode["flatten"]:
                n = self.doc.fill_form_flatten(updates)
            else:
                n = self.doc.set_form_fields(updates)
        except Exception as exc:
            QMessageBox.critical(self, t("form.fill_failed"), str(exc))
            return
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("form.filled", n=n), 8000)

    # ---------------- ผู้ช่วยพิมพ์คำสั่ง ----------------

    def assistant_dialog(self) -> None:
        if not self.doc or not self.doc.page_count:
            return
        examples = "\n".join(f"•  {e}" for e in assistant.EXAMPLES)
        command, ok = QInputDialog.getText(
            self, t("ai.title"),
            t("ai.prompt") + "\n\n" + t("ai.examples") + "\n" + examples)
        if not ok or not command.strip():
            return
        self.run_assistant_command(command)

    def run_assistant_command(self, command: str) -> None:
        intent = assistant.parse(command)
        if intent is None:
            examples = "\n".join(f"•  {e}" for e in assistant.EXAMPLES)
            QMessageBox.information(
                self, t("ai.title"),
                t("ai.not_understood") + "\n\n" + t("ai.examples") + "\n" + examples)
            return
        if intent.needs_online_ai:
            QMessageBox.information(self, t("ai.title"),
                                   intent.preview + "\n\n" + t("ai.no_ai"))
            return

        # ยืนยันก่อนทำ (แสดงว่าจะทำอะไร)
        if QMessageBox.question(
            self, t("ai.confirm_title"),
            t("ai.will_do", what=intent.preview),
        ) != QMessageBox.Yes:
            return

        try:
            msg = self._execute_intent(intent)
        except Exception as exc:
            QMessageBox.critical(self, t("ai.title"), str(exc))
            return
        self._refresh_all(keep_row=min(self.viewer.index, self.doc.page_count - 1))
        self.statusBar().showMessage(msg, 8000)

    def _execute_intent(self, intent) -> str:
        """ลงมือทำตาม intent คืนข้อความสรุปผล"""
        a, p = intent.action, intent.params

        if a == "delete_blank":
            n = self.doc.delete_blank_pages()
            return t("ai.done_blank", n=n) if n else t("ai.no_blank")

        if a == "redact_pii":
            n = self.doc.redact_personal_info()
            return t("ai.done_pii", n=n) if n else t("ai.no_pii")

        if a == "orientation":
            n = self.doc.set_orientation(list(range(self.doc.page_count)), p["orientation"])
            return t("ai.done_rotate", n=n)

        if a == "rotate":
            self.doc.rotate_pages(list(range(self.doc.page_count)), p["degrees"])
            return t("ai.done_rotate", n=self.doc.page_count)

        if a == "page_numbers":
            self.doc.add_page_numbers(fmt="{page}", numeral=p.get("numeral", "arabic"))
            return t("ai.done_numbers")

        if a == "keep_matching":
            matches = self.doc.pages_matching(p["keyword"])
            if not matches:
                return t("ai.no_match", kw=p["keyword"])
            self.doc.keep_only_pages(matches)
            return t("ai.done_keep", n=len(matches), kw=p["keyword"])

        if a == "watermark":
            self.doc.add_text_watermark(p["text"])
            return t("ai.done_watermark")

        if a == "text_after_label":
            label = p["label"]
            text = p.get("text") or date_suggestions()[0]
            n, missing = self.doc.add_textbox_after_label(label, text)
            if not n:
                raise RuntimeError(t("ai.label_not_found", label=label))
            remember_text(text)
            msg = t("ai.done_after_label", n=n, label=label, text=text)
            if missing:
                msg += "  " + t("ai.label_missing", n=len(missing))
            return msg

        if a == "text_all_pages":
            # ต้องมีข้อความต้นแบบที่เลือกอยู่ เพื่อรู้ว่าจะวางตรงช่องไหน
            box = self.viewer.selected_textbox
            if box is None:
                raise RuntimeError(t("ai.need_textbox"))
            text = p.get("text") or date_suggestions()[0]
            template = box.copy()
            template.text = text
            n = self.doc.add_textbox_all_pages(template)
            if not n:
                return t("text.all_pages_none")
            remember_text(text)
            return t("text.all_pages_done", n=n)

        if a == "ocr":
            try:
                pdfops.ensure_tesseract()
            except RuntimeError as exc:
                raise RuntimeError(str(exc))
            # OCR สร้างไฟล์ใหม่ — ให้ผู้ใช้เลือกที่บันทึก
            default = str(self.doc.path.with_stem(self.doc.path.stem + "-ocr")) \
                if self.doc.path else "เอกสาร-ocr.pdf"
            target, _ = QFileDialog.getSaveFileName(self, t("tools.ocr"), default, PDF_FILTER)
            if not target:
                return t("ai.cancelled")
            self._busy(t("batch.running"))
            try:
                self.doc.ocr_to_searchable(target, list(range(self.doc.page_count)))
            finally:
                self._done_busy()
            return t("ai.done_ocr", target=target)

        return t("ai.not_understood")

    # ---------------- Batch Processing (ประมวลผลหลายไฟล์) ----------------

    def batch_dialog(self) -> None:
        from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QListWidget as QLW,
                                       QProgressDialog, QVBoxLayout)

        dialog = QDialog(self)
        dialog.setWindowTitle(t("batch.title"))
        dialog.resize(560, 480)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel(t("batch.files")))
        file_list = QLW()
        file_list.setSelectionMode(QLW.ExtendedSelection)
        layout.addWidget(file_list)

        file_btns = QHBoxLayout()
        add_btn = QPushButton(t("batch.add_files"))
        clear_btn = QPushButton(t("batch.clear"))
        file_btns.addWidget(add_btn)
        file_btns.addWidget(clear_btn)
        file_btns.addStretch(1)
        layout.addLayout(file_btns)

        def add_files():
            paths, _ = QFileDialog.getOpenFileNames(dialog, t("batch.add_files"), "", PDF_FILTER)
            existing = {file_list.item(i).text() for i in range(file_list.count())}
            for p in paths:
                if p not in existing:
                    file_list.addItem(p)
        add_btn.clicked.connect(add_files)
        clear_btn.clicked.connect(file_list.clear)

        layout.addWidget(QLabel(t("batch.operation")))
        op_combo = QComboBox()
        # (label, key) — merge เป็นงานพิเศษ
        ops = [
            (t("batch.op.watermark"), "watermark_text"),
            (t("batch.op.ocr"), "ocr"),
            (t("batch.op.word"), "to_word"),
            (t("batch.op.excel"), "to_excel"),
            (t("batch.op.images"), "to_images"),
            (t("batch.op.numbers"), "page_numbers"),
            (t("batch.op.setpw"), "set_password"),
            (t("batch.op.removepw"), "remove_password"),
            (t("batch.op.merge"), "merge"),
        ]
        for label, key in ops:
            op_combo.addItem(label, key)
        layout.addWidget(op_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(t("batch.run"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return
        files = [file_list.item(i).text() for i in range(file_list.count())]
        if not files:
            QMessageBox.information(self, t("batch.title"), t("batch.no_files"))
            return
        operation = op_combo.currentData()

        # ---- งานพิเศษ: รวมไฟล์ ----
        if operation == "merge":
            target, _ = QFileDialog.getSaveFileName(
                self, t("batch.op.merge"), "รวมไฟล์.pdf", PDF_FILTER)
            if not target:
                return
            self._busy(t("batch.running"))
            try:
                batch.run_merge(files, target)
            except Exception as exc:
                QMessageBox.critical(self, t("batch.title"), str(exc))
                return
            finally:
                self._done_busy()
            self.statusBar().showMessage(t("batch.merged", n=len(files), target=target), 9000)
            return

        # ---- พารามิเตอร์เฉพาะงาน ----
        params = self._batch_params(operation)
        if params is None:
            return

        out_dir = QFileDialog.getExistingDirectory(self, t("batch.out_dir"))
        if not out_dir:
            return

        progress = QProgressDialog(t("batch.running"), t("bar.cancel"), 0, len(files), self)
        progress.setWindowModality(Qt.WindowModal)
        cancelled = {"v": False}
        progress.canceled.connect(lambda: cancelled.update(v=True))

        def report(done, total, name):
            progress.setValue(done)
            if name:
                progress.setLabelText(t("batch.processing", name=name, done=done + 1, total=total))
            QApplication.processEvents()

        original = batch.OPERATIONS[operation]

        def guarded_op(src, out, p):
            if cancelled["v"]:
                raise RuntimeError(t("batch.cancelled"))
            return original(src, out, p)   # เรียกตัวจริง ไม่ใช่ตัวที่ห่อไว้

        # ห่อ operation เพื่อให้หยุดกลางคันได้
        batch.OPERATIONS[operation] = guarded_op
        try:
            results = batch.run_batch(files, out_dir, operation, params, progress=report)
        finally:
            batch.OPERATIONS[operation] = original
            progress.close()

        ok = sum(1 for r in results if r["ok"])
        fail = [r for r in results if not r["ok"]]
        summary = t("batch.summary", ok=ok, fail=len(fail), out=out_dir)
        if fail:
            detail = "\n".join(f"• {r['file'].name}: {r['error']}" for r in fail[:10])
            summary += "\n\n" + t("batch.failed_files") + "\n" + detail
        QMessageBox.information(self, t("batch.done_title"), summary)
        self.statusBar().showMessage(t("batch.summary_short", ok=ok, fail=len(fail)), 9000)

    def _batch_params(self, operation: str) -> dict | None:
        """ถามพารามิเตอร์ที่งานนั้นต้องใช้ (คืน None ถ้ายกเลิก)"""
        if operation == "watermark_text":
            text, ok = QInputDialog.getText(self, t("tools.watermark_text"),
                                            t("batch.wm_text"), text="สำเนา")
            if not ok or not text.strip():
                return None
            return {"text": text}
        if operation == "ocr":
            try:
                pdfops.ensure_tesseract()
            except RuntimeError as exc:
                QMessageBox.warning(self, t("edit.cant_title"), str(exc))
                return None
            langs = pdfops.ocr_languages()
            options, keys = [], []
            if "tha" in langs and "eng" in langs:
                options.append("ไทย + อังกฤษ"); keys.append("tha+eng")
            if "tha" in langs:
                options.append("ไทยอย่างเดียว"); keys.append("tha")
            if "eng" in langs:
                options.append("อังกฤษอย่างเดียว"); keys.append("eng")
            choice, ok = QInputDialog.getItem(self, "OCR", "ภาษา:", options, 0, False)
            if not ok:
                return None
            return {"language": keys[options.index(choice)]}
        if operation == "set_password":
            pw, ok = QInputDialog.getText(self, t("tools.password"), t("pwset.pw1"),
                                          QLineEdit.Password)
            if not ok or not pw:
                return None
            return {"password": pw}
        # to_word / to_excel / to_images / page_numbers / remove_password ไม่ต้องถามอะไร
        return {}

    # ---------------- Bookmarks (สารบัญ) ----------------

    def _build_bookmark_panel(self) -> None:
        self._bookmark_panel = QWidget()
        self._bookmark_panel.setMinimumWidth(160)   # ลากปรับความกว้างได้
        layout = QVBoxLayout(self._bookmark_panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel(t("bm.title"))
        header.setStyleSheet("font-weight:bold; padding:2px;")
        layout.addWidget(header)

        self._bookmark_tree = QTreeWidget()
        self._bookmark_tree.setHeaderHidden(True)
        self._bookmark_tree.itemClicked.connect(self._on_bookmark_clicked)
        self._bookmark_tree.itemDoubleClicked.connect(lambda *_: self.rename_bookmark())
        layout.addWidget(self._bookmark_tree)

        btn_row = QHBoxLayout()
        for label, slot in (
            (t("bm.add"), self.add_bookmark_current),
            (t("bm.rename"), self.rename_bookmark),
            (t("bm.remove"), self.remove_bookmark),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        indent_row = QHBoxLayout()
        out_btn = QPushButton("◀ " + t("bm.outdent"))
        out_btn.clicked.connect(lambda: self._change_bookmark_level(-1))
        in_btn = QPushButton(t("bm.indent") + " ▶")
        in_btn.clicked.connect(lambda: self._change_bookmark_level(+1))
        indent_row.addWidget(out_btn)
        indent_row.addWidget(in_btn)
        layout.addLayout(indent_row)

        self._bookmark_panel.hide()

    def _toggle_bookmark_panel(self, on: bool) -> None:
        self._bookmark_panel.setVisible(on)
        if on:
            self._give_panel_width(1, 240)
            self._refresh_bookmarks()

    def _refresh_bookmarks(self) -> None:
        if not hasattr(self, "_bookmark_tree"):
            return
        self._bookmark_tree.clear()
        if not self.doc:
            return
        parents_by_level: dict[int, QTreeWidgetItem] = {}
        for idx, bm in enumerate(self.doc.get_bookmarks()):
            item = QTreeWidgetItem([f"{bm['title']}  (น.{bm['page'] + 1})"])
            item.setData(0, Qt.UserRole, idx)
            level = bm["level"]
            parent = parents_by_level.get(level - 1)
            if level > 1 and parent is not None:
                parent.addChild(item)
            else:
                self._bookmark_tree.addTopLevelItem(item)
            parents_by_level[level] = item
            # ลูกที่ลึกกว่านี้ถือว่าไม่มีแล้ว
            for deeper in list(parents_by_level):
                if deeper > level:
                    del parents_by_level[deeper]
        self._bookmark_tree.expandAll()

    def _selected_bookmark_index(self) -> int | None:
        item = self._bookmark_tree.currentItem()
        if item is None:
            return None
        return item.data(0, Qt.UserRole)

    def _on_bookmark_clicked(self, item, _col) -> None:
        idx = item.data(0, Qt.UserRole)
        bms = self.doc.get_bookmarks()
        if idx is not None and 0 <= idx < len(bms):
            self.goto_page(bms[idx]["page"])

    def add_bookmark_current(self) -> None:
        if not self.doc:
            return
        default = self.doc.page_text(self.viewer.index).strip().split("\n")[0][:60]
        title, ok = QInputDialog.getText(
            self, t("bm.add_title"), t("bm.add_prompt", n=self.viewer.index + 1),
            text=default or f"หน้า {self.viewer.index + 1}")
        if not ok or not title.strip():
            return
        after = self._selected_bookmark_index()
        self.doc.add_bookmark(title.strip(), self.viewer.index, after=after)
        self._refresh_bookmarks()
        self._update_state()
        self.statusBar().showMessage(t("bm.added"), 5000)

    def rename_bookmark(self) -> None:
        idx = self._selected_bookmark_index()
        if idx is None:
            return
        current = self.doc.get_bookmarks()[idx]["title"]
        title, ok = QInputDialog.getText(self, t("bm.rename"), t("bm.rename_prompt"), text=current)
        if not ok or not title.strip():
            return
        self.doc.rename_bookmark(idx, title.strip())
        self._refresh_bookmarks()

    def remove_bookmark(self) -> None:
        idx = self._selected_bookmark_index()
        if idx is None:
            return
        self.doc.remove_bookmark(idx)
        self._refresh_bookmarks()
        self._update_state()
        self.statusBar().showMessage(t("bm.removed"), 5000)

    def _change_bookmark_level(self, delta: int) -> None:
        idx = self._selected_bookmark_index()
        if idx is None:
            return
        self.doc.move_bookmark_level(idx, delta)
        self._refresh_bookmarks()

    # ---------------- ไฮไลต์ข้อความ ----------------

    def toggle_highlight_mode(self) -> None:
        if not self.doc or not self.doc.page_count:
            return
        if self.viewer._highlighting:
            self._end_highlight_mode()
        else:
            self.deselect_stamp()
            self.deselect_textbox()
            self.viewer.start_highlight_drag()
            self._highlight_bar.show()
            self.statusBar().showMessage(t("hl.hint"), 0)

    def _end_highlight_mode(self) -> None:
        self.viewer.stop_highlight_drag()
        self._highlight_bar.hide()
        self.statusBar().clearMessage()

    # ---------------- ยางลบ / ปิดทับ (ใช้กับไฟล์สแกน) ----------------

    def toggle_erase_mode(self) -> None:
        if not self.doc or not self.doc.page_count:
            return
        if self.viewer._erasing:
            self._end_erase_mode()
        else:
            self.deselect_stamp()
            self.deselect_textbox()
            if self.viewer._highlighting:
                self._end_highlight_mode()
            self.viewer.start_erase_drag()
            self._erase_bar.show()
            self.statusBar().showMessage(t("er.hint"), 0)

    def _end_erase_mode(self) -> None:
        self.viewer.stop_erase_drag()
        self._erase_bar.hide()
        self.statusBar().clearMessage()

    # ---------------- วาด / มาร์กอัป ----------------

    def _paint_annot_swatch(self) -> None:
        r, g, b = self._annot_color
        self._annot_swatch.setStyleSheet(
            f"background:rgb({int(r*255)},{int(g*255)},{int(b*255)}); "
            "border:1px solid #888; min-width:22px; min-height:16px;")

    def _current_annot_tool(self) -> str:
        for tool, btn in self._annot_tool_btns.items():
            if btn.isChecked():
                return tool
        return "draw"

    def _set_annot_tool(self, tool: str) -> None:
        for tk, btn in self._annot_tool_btns.items():
            btn.setChecked(tk == tool)
        self.viewer.set_annot_tool(tool)

    def _apply_annot_style(self, *_) -> None:
        self._annot_width = self._annot_width_box.currentData() or 2.0
        self.viewer.set_annot_style(self._annot_color, self._annot_width)

    def _pick_annot_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog
        r, g, b = self._annot_color
        col = QColorDialog.getColor(QColor(int(r*255), int(g*255), int(b*255)), self,
                                    t("an.color"))
        if col.isValid():
            self._annot_color = (col.redF(), col.greenF(), col.blueF())
            self._paint_annot_swatch()
            self.viewer.set_annot_style(self._annot_color, self._annot_width)

    def toggle_annot_mode(self) -> None:
        if not self.doc or not self.doc.page_count:
            return
        if self.viewer._annotating:
            self._end_annot_mode()
        else:
            self.deselect_stamp()
            self.deselect_textbox()
            if self.viewer._highlighting:
                self._end_highlight_mode()
            if self.viewer._erasing:
                self._end_erase_mode()
            self._annot_width = self._annot_width_box.currentData() or 2.0
            self.viewer.start_annotate(self._current_annot_tool(),
                                       self._annot_color, self._annot_width)
            self._annot_bar.show()
            self.statusBar().showMessage(t("an.hint"), 0)

    def _end_annot_mode(self) -> None:
        self.viewer.stop_annotate()
        self._annot_bar.hide()
        self.statusBar().clearMessage()

    def _on_annot_drawn(self, page_index: int, data: dict) -> None:
        self.doc.add_annotation(page_index, data["kind"], data["points"],
                                self._annot_color, self._annot_width)
        self._refresh_all(keep_row=page_index)

    def clear_annotations_page(self) -> None:
        if not self.doc:
            return
        n = self.doc.clear_annotations(self.viewer.index)
        if n:
            self._refresh_all(keep_row=self.viewer.index)
            self.statusBar().showMessage(t("an.cleared", n=n), 5000)

    def clear_erasers_page(self) -> None:
        """เอาแผ่นปิดทับทั้งหมดในหน้านี้ออก"""
        if not self.doc:
            return
        on_page = self.doc.erasers_on(self.viewer.index)
        if not on_page:
            return
        self.doc.push_undo()
        for eraser in on_page:
            self.doc.erasers.remove(eraser)
        self.doc.dirty = True
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("er.cleared", n=len(on_page)), 5000)

    def _on_erase_dragged(self, page_index: int, rect) -> None:
        """ลากกรอบเสร็จ = ปิดทับตรงนั้น แล้วถามว่าจะพิมพ์ข้อความใหม่ทับเลยไหม"""
        if rect.width < 3 or rect.height < 3:
            # คลิกเฉยๆ บนแผ่นที่ปิดไว้ = เอาแผ่นนั้นออก
            hit = self.doc.eraser_at(page_index, fitz.Point(rect.x0, rect.y0))
            if hit is not None:
                self.doc.remove_eraser(hit)
                self._refresh_all(keep_row=page_index)
                self.statusBar().showMessage(t("er.removed"), 5000)
            return

        color = None if self._erase_auto_color else (1.0, 1.0, 1.0)
        self.doc.add_eraser(page_index, rect, color=color)
        self._refresh_all(keep_row=page_index)

        # ถามต่อเลยว่าจะพิมพ์ข้อความใหม่ตรงนี้ไหม (เป็นงานที่ทำต่อกันเสมอ)
        if QMessageBox.question(self, t("er.title"), t("er.add_text_now"),
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._end_erase_mode()
            text, font_key, bold, ok = self._ask_text_content(t("text.new_title"), "")
            if ok and text.strip():
                size = self._last_font_size
                box = self.doc.add_textbox(page_index, fitz.Rect(rect), text, font_size=size,
                                           color=self._last_color, font=font_key, bold=bold)
                self.viewer.selected_textbox = box
                self._refresh_all(keep_row=page_index)
                self._text_bar.show()
                self.statusBar().showMessage(t("text.added"), 7000)
        else:
            self.statusBar().showMessage(t("er.hint"), 0)

    def _on_rect_dragged(self, page_index: int, rect) -> None:
        # กรอบเล็กมาก = ตั้งใจคลิกเพื่อลบไฮไลต์ตรงนั้น
        if rect.width < 4 and rect.height < 4:
            center = fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
            if self.doc.remove_highlight_at(page_index, center):
                self._refresh_all(keep_row=page_index)
                self.statusBar().showMessage(t("hl.removed"), 4000)
            return
        n = self.doc.highlight_rect(page_index, rect, color=self._highlight_color)
        if n:
            self._refresh_all(keep_row=page_index)
            self.statusBar().showMessage(t("hl.done", n=n), 4000)
        else:
            self.viewer.refresh()

    def _pick_highlight_color(self) -> None:
        from PySide6.QtWidgets import QColorDialog

        r, g, b = self._highlight_color
        chosen = QColorDialog.getColor(
            QColor(int(r * 255), int(g * 255), int(b * 255)), self, t("hl.pick_color"))
        if chosen.isValid():
            self._highlight_color = (chosen.redF(), chosen.greenF(), chosen.blueF())
            self._highlight_swatch.setStyleSheet(
                f"background:{chosen.name()}; border:1px solid #888; min-width:20px; min-height:16px;")

    def clear_highlights_page(self) -> None:
        if not self.doc:
            return
        n = self.doc.clear_highlights(self.viewer.index)
        if n:
            self._refresh_all(keep_row=self.viewer.index)
            self.statusBar().showMessage(t("hl.cleared", n=n), 4000)

    # ---------------- รหัสผ่าน PDF ----------------

    def password_dialog(self) -> None:
        if not self.doc or not self.doc.page_count:
            return

        from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel as QLbl,
                                       QLineEdit as QLE, QRadioButton, QVBoxLayout)

        dialog = QDialog(self)
        dialog.setWindowTitle(t("pwset.title"))
        dialog.resize(400, 260)
        layout = QVBoxLayout(dialog)

        info = QLbl(t("pwset.current_locked") if self.doc.is_encrypted else t("pwset.current_open"))
        info.setWordWrap(True)
        layout.addWidget(info)

        set_radio = QRadioButton(t("pwset.mode_set"))
        remove_radio = QRadioButton(t("pwset.mode_remove"))
        set_radio.setChecked(True)
        layout.addWidget(set_radio)

        pw1 = QLE(); pw1.setEchoMode(QLE.Password); pw1.setPlaceholderText(t("pwset.pw1"))
        pw2 = QLE(); pw2.setEchoMode(QLE.Password); pw2.setPlaceholderText(t("pwset.pw2"))
        layout.addWidget(pw1)
        layout.addWidget(pw2)
        layout.addWidget(remove_radio)

        def sync_enabled():
            on = set_radio.isChecked()
            pw1.setEnabled(on)
            pw2.setEnabled(on)
        set_radio.toggled.connect(sync_enabled)
        # ไฟล์ที่ไม่มีรหัสอยู่แล้ว ไม่ต้องมีตัวเลือก "ลบรหัส"
        remove_radio.setVisible(self.doc.is_encrypted)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        remove = remove_radio.isChecked()
        if not remove:
            if not pw1.text():
                QMessageBox.warning(self, t("pwset.title"), t("pwset.empty"))
                return
            if pw1.text() != pw2.text():
                QMessageBox.warning(self, t("pwset.title"), t("pwset.mismatch"))
                return

        default = str(self.doc.path) if self.doc.path else "เอกสาร.pdf"
        target, _ = QFileDialog.getSaveFileName(self, t("pwset.save_as"), default, PDF_FILTER)
        if not target:
            return
        try:
            self.doc.save_with_password(target, "" if remove else pw1.text())
        except Exception as exc:
            QMessageBox.critical(self, t("pwset.failed"), str(exc))
            return
        msg = t("pwset.removed") if remove else t("pwset.done")
        self.statusBar().showMessage(f"{msg}: {target}", 8000)
        QMessageBox.information(self, t("pwset.title"), f"{msg}\n{target}")

    # ---------------- เพิ่ม / แก้ไขข้อความ ----------------

    def add_text_dialog(self) -> None:
        """เข้าโหมดรอผู้ใช้คลิกจุดบนหน้าเพื่อวางข้อความ"""
        if not self.doc or not self.doc.page_count:
            return
        self.deselect_stamp()
        self.deselect_textbox()
        self.viewer.start_point_pick()
        self.statusBar().showMessage(t("text.click_point"), 0)

    def edit_text_dialog(self) -> None:
        """เข้าโหมดรอผู้ใช้คลิกข้อความเดิมที่จะแก้"""
        if not self.doc or not self.doc.page_count:
            return
        if self.doc.needs_ocr(self.viewer.index):
            QMessageBox.information(self, t("edit.cant_title"), t("edit.scanned"))
            return
        self.deselect_stamp()
        self.deselect_textbox()
        self.viewer.start_point_pick(mode="edit")
        self.statusBar().showMessage(t("edit.click_text"), 0)

    def _on_edit_point_picked(self, page_index: int, px: float, py: float) -> None:
        box = self.doc.start_edit_existing_text(page_index, fitz.Point(px, py))
        if box is None:
            self.statusBar().showMessage(t("edit.no_text_here"), 5000)
            return
        # เปิดกล่องแก้คำทันที เติมคำเดิมไว้ให้
        text, font_key, bold, ok = self._ask_text_content(
            t("edit.edit_title"), box.text, cur_font=box.font, cur_bold=box.bold)
        if ok:
            self.doc.update_textbox_content(box, text=text, font=font_key, bold=bold)
        self.viewer.selected_textbox = box
        self._refresh_all(keep_row=page_index)
        self._text_bar.show()
        self.statusBar().showMessage(t("edit.done_hint"), 7000)

    def _on_point_picked(self, page_index: int, px: float, py: float) -> None:
        text, font_key, bold, ok = self._ask_text_content(t("text.new_title"), "")
        if not ok or not text.strip():
            self.statusBar().clearMessage()
            return
        size = self._last_font_size
        # กล่องเริ่มต้น: กว้างพอสมควร สูงตามขนาดฟอนต์ (ปรับภายหลังได้)
        page = self.doc.doc.load_page(page_index)
        width = min(page.rect.width - px - 10, max(200, len(text) * size * 0.6))
        rect = fitz.Rect(px, py, px + width, py + size * 1.8)
        box = self.doc.add_textbox(page_index, rect, text, font_size=size,
                                   color=self._last_color, font=font_key, bold=bold)
        self.viewer.selected_textbox = box
        self._refresh_all(keep_row=page_index)
        self._text_bar.show()
        self.statusBar().showMessage(t("text.added"), 7000)

    def _ask_text_content(self, title: str, initial: str,
                          cur_font: str | None = None,
                          cur_bold: bool = False) -> tuple[str, str, bool, bool]:
        """กล่องกรอกข้อความ (หลายบรรทัด) + ฟอนต์ + ตัวหนา + ขนาด
        คืน (ข้อความ, font_key, bold, ok)
        """
        from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                                       QFormLayout, QHBoxLayout as HBox, QVBoxLayout)

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(440, 320)
        layout = QVBoxLayout(dialog)

        # ประวัติที่พิมพ์ไว้ + วันที่วันนี้ (ให้เดาคำได้ตั้งแต่ครั้งแรก ยังไม่มีประวัติก็ใช้ได้)
        history = text_history()
        history += [d for d in date_suggestions() if d not in history]
        editor = CompletingTextEdit(initial, history)
        editor.setPlaceholderText(t("text.placeholder_input"))
        layout.addWidget(editor)
        if history:
            hint = QLabel(t("text.history_hint"))
            hint.setStyleSheet("color:#666; font-size:11px;")
            layout.addWidget(hint)

        form = QFormLayout()

        # ฟอนต์
        font_box = QComboBox()
        font_box.addItem(t("text.font_auto"), "")     # อัตโนมัติตามภาษา
        for f in pdfops.available_fonts():
            label = f["name"] + ("" if f["thai"] else "  (อังกฤษ)")
            font_box.addItem(label, f["key"])
        want = self._last_font if cur_font is None else cur_font
        idx = font_box.findData(want)
        font_box.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow(t("text.font"), font_box)

        # ขนาด + ตัวหนา
        size_box = QComboBox()
        size_box.addItems(["4", "6", "8", "10", "12", "14", "16", "18", "20", "24", "28",
                           "36", "48"])
        size_box.setEditable(True)
        size_box.setCurrentText(str(int(self._last_font_size)))
        bold_chk = QCheckBox(t("text.bold"))
        bold_chk.setChecked(cur_bold if cur_font is not None else self._last_bold)
        size_row = HBox(); size_row.addWidget(size_box, 1); size_row.addWidget(bold_chk)
        form.addRow(t("text.font_size"), size_row)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        editor.setFocus()

        if dialog.exec() != QDialog.Accepted:
            return "", "", False, False
        try:
            self._last_font_size = max(4.0, float(size_box.currentText()))
        except ValueError:
            pass
        font_key = font_box.currentData() or ""
        bold = bold_chk.isChecked()
        self._last_font = font_key
        self._last_bold = bold
        value = editor.toPlainText()
        remember_text(value)        # จำไว้ให้เดาคำครั้งหน้า
        return value, font_key, bold, True

    def textbox_selected_all_pages(self) -> None:
        """วางข้อความที่เลือกอยู่ ตำแหน่งเดิม ทุกหน้า (เช่นลงวันที่ตรงช่องเดียวกันทุกหน้า)"""
        box = self.viewer.selected_textbox
        if box is None or not self.doc:
            return
        indexes = self._ask_scope(t("text.all_pages"))
        if indexes is None:
            return
        n = self.doc.add_textbox_all_pages(box, indexes)
        if not n:
            self.statusBar().showMessage(t("text.all_pages_none"), 5000)
            return
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("text.all_pages_done", n=n), 7000)

    # ---------------- เลือกข้อความบนหน้า (ลากเลือก -> คัดลอก) ----------------

    def _build_selection_popup(self) -> None:
        """แถบลอยเล็กๆ ที่โผล่ข้างข้อความที่ลากเลือก (แบบโปรแกรมอ่าน PDF ทั่วไป)"""
        self._sel_popup = QWidget(self.viewer)
        self._sel_popup.setObjectName("selPopup")
        row = QHBoxLayout(self._sel_popup)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(4)
        for key, slot in (("sel.copy", self.copy_selected_text),
                          ("sel.highlight", self.highlight_selected_text),
                          ("sel.search", self.search_selected_text)):
            btn = QPushButton(t(key))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        self._sel_popup.setStyleSheet(
            "#selPopup { background:#2b2f33; border:1px solid #555; border-radius:6px; }"
            "#selPopup QPushButton { color:#f0f0f0; background:transparent; border:none;"
            " padding:4px 10px; }"
            "#selPopup QPushButton:hover { background:#3d444b; border-radius:4px; }")
        self._sel_popup.hide()

        # คีย์ลัดมาตรฐาน — คัดลอกข้อความที่เลือก / เลือกทั้งหน้า
        from PySide6.QtGui import QShortcut
        copy_sc = QShortcut(QKeySequence.Copy, self)
        copy_sc.activated.connect(self.copy_selected_text)
        all_sc = QShortcut(QKeySequence.SelectAll, self)
        all_sc.activated.connect(self.select_all_text)

        self.viewer.textSelected.connect(self._on_text_selected)
        self.viewer.selectionCleared.connect(lambda: self._sel_popup.hide())
        # เลื่อนจอแล้วให้แถบตามข้อความไปด้วย (ไม่ค้างลอยผิดที่)
        self.viewer.verticalScrollBar().valueChanged.connect(self._reposition_sel_popup)
        self.viewer.horizontalScrollBar().valueChanged.connect(self._reposition_sel_popup)

    def _on_text_selected(self, text: str, page: int, rect) -> None:
        self._sel_anchor = (page, rect)
        words = len(text.split())
        self.statusBar().showMessage(t("sel.picked", n=len(text), w=words), 6000)
        # ต้อง show ก่อนแล้วค่อยจัดตำแหน่ง — _reposition ข้ามการทำงานถ้าแถบยังไม่แสดง
        self._sel_popup.show()
        self._sel_popup.raise_()
        self._reposition_sel_popup()

    def _reposition_sel_popup(self) -> None:
        anchor = getattr(self, "_sel_anchor", None)
        if anchor is None or not self._sel_popup.isVisible():
            return
        page, rect = anchor
        pos = self.viewer.page_point_to_viewer(page, rect.x0, rect.y1)
        self._sel_popup.adjustSize()
        w, h = self._sel_popup.width(), self._sel_popup.height()
        x = max(4, min(pos.x(), self.viewer.width() - w - 4))
        y = pos.y() + 6
        if y + h > self.viewer.height() - 4:          # ล้นขอบล่าง -> ย้ายไปอยู่เหนือข้อความ
            y = max(4, pos.y() - h - int(rect.height * self.viewer.zoom) - 6)
        self._sel_popup.move(x, y)

    def copy_selected_text(self) -> None:
        text = self.viewer.selected_text
        if not text:
            return
        QApplication.clipboard().setText(text)
        self._sel_popup.hide()
        self.statusBar().showMessage(t("sel.copied", n=len(text)), 5000)

    def highlight_selected_text(self) -> None:
        """ไฮไลต์ข้อความที่เลือกไว้ (ใช้แถบที่เลือกเป็นกรอบ)"""
        if not self.viewer.selected_text or not self.doc:
            return
        page = self.viewer._sel_page
        total = 0
        for rect in self.viewer._sel_rects:
            total += self.doc.highlight_rect(page, rect, color=self._highlight_color)
        self.viewer.clear_selection()
        self._sel_popup.hide()
        if total:
            self._refresh_all(keep_row=page)
            self.statusBar().showMessage(t("hl.done", n=total), 5000)

    def search_selected_text(self) -> None:
        """เอาข้อความที่เลือกไปค้นในเอกสาร"""
        text = (self.viewer.selected_text or "").strip().split("\n")[0][:80]
        if not text:
            return
        self._sel_popup.hide()
        self.viewer.clear_selection()
        self.search_box.setText(text)
        self.search_next()

    def select_all_text(self) -> None:
        if self.doc:
            self.viewer.select_all_on_page()

    def _on_textbox_selected(self) -> None:
        self._text_bar.show()
        self.viewer.refresh()
        self.statusBar().showMessage(t("text.selected_hint"), 6000)

    def edit_selected_textbox(self) -> None:
        """แก้คำในกล่องข้อความที่เลือก"""
        box = self.viewer.selected_textbox
        if box is None:
            return
        text, font_key, bold, ok = self._ask_text_content(
            t("text.edit_title"), box.text, cur_font=box.font, cur_bold=box.bold)
        if not ok:
            return
        self.doc.update_textbox_content(box, text=text, font_size=self._last_font_size,
                                        font=font_key, bold=bold)
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("text.updated"), 6000)

    def move_selected_textbox(self) -> None:
        box = self.viewer.selected_textbox
        if box is None:
            return
        self._text_bar.hide()
        self.viewer.start_editing_textbox(box)
        self.viewer.overlay.committed.connect(self.commit_placement)
        self._placing_bar.show()

    def color_selected_textbox(self) -> None:
        from PySide6.QtWidgets import QColorDialog

        box = self.viewer.selected_textbox
        if box is None:
            return
        r, g, b = box.color
        chosen = QColorDialog.getColor(
            QColor(int(r * 255), int(g * 255), int(b * 255)), self, t("text.pick_color"))
        if not chosen.isValid():
            return
        self._last_color = (chosen.redF(), chosen.greenF(), chosen.blueF())
        self.doc.update_textbox_content(box, color=self._last_color)
        self._refresh_all(keep_row=self.viewer.index)

    def delete_selected_textbox(self) -> None:
        box = self.viewer.selected_textbox
        if box is None or not self.doc:
            return
        self.doc.remove_textbox(box)
        self.viewer.selected_textbox = None
        self._text_bar.hide()
        self._refresh_all(keep_row=self.viewer.index)
        self.statusBar().showMessage(t("text.deleted"), 6000)

    def deselect_textbox(self) -> None:
        self.viewer.selected_textbox = None
        self._text_bar.hide()
        self.viewer.refresh()

    def extract_all_text(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self, "บันทึกข้อความเป็น", "ข้อความ.txt", "ไฟล์ข้อความ (*.txt)"
        )
        if not target:
            return
        Path(target).write_text(self.doc.all_text(), encoding="utf-8")
        self.statusBar().showMessage(f"บันทึกข้อความไปที่ {target}", 6000)

    # ---------------- ปิดโปรแกรม ----------------

    def deselect_stamp(self) -> None:
        self.viewer.selected_stamp = None
        self._stamp_bar.hide()
        self.viewer.refresh()

    def keyPressEvent(self, event) -> None:
        # ยกเลิกโหมดรอคลิกจุดวางข้อความ
        if getattr(self.viewer, "_picking_point", False) and event.key() == Qt.Key_Escape:
            self.viewer.stop_point_pick()
            self.statusBar().clearMessage()
            return
        # ออกจากโหมดไฮไลต์ด้วย Esc
        if self.viewer._highlighting and event.key() == Qt.Key_Escape:
            self._end_highlight_mode()
            return
        # ออกจากโหมดยางลบด้วย Esc
        if self.viewer._erasing and event.key() == Qt.Key_Escape:
            self._end_erase_mode()
            return
        # ออกจากโหมดวาดมาร์กอัปด้วย Esc
        if self.viewer._annotating and event.key() == Qt.Key_Escape:
            self._end_annot_mode()
            return
        # กด Delete ตอนเลือกลายเซ็นอยู่ = ลบลายเซ็น (ไม่ใช่ลบหน้า)
        if self.viewer.selected_stamp is not None and not self.viewer.placing:
            if event.key() == Qt.Key_Delete:
                self.delete_selected_stamp()
                return
            if event.key() == Qt.Key_Escape:
                self.deselect_stamp()
                return
        # Delete/Esc ตอนเลือกกล่องข้อความ
        if self.viewer.selected_textbox is not None and not self.viewer.placing:
            if event.key() == Qt.Key_Delete:
                self.delete_selected_textbox()
                return
            if event.key() == Qt.Key_Escape:
                self.deselect_textbox()
                return
        if self.viewer.placing:
            if event.key() == Qt.Key_Escape:
                self.cancel_placement()
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.commit_placement()
                return
        super().keyPressEvent(event)

    # ---------------- ลากไฟล์ PDF จาก Explorer มาปล่อย ----------------

    def dragEnterEvent(self, event) -> None:
        if pdf_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if pdf_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        """ปล่อยไฟล์นอกแถบหน้าย่อ — ยังไม่เปิดไฟล์ก็เปิดให้, เปิดอยู่แล้วก็ต่อท้าย"""
        paths = pdf_paths_from_mime(event.mimeData())
        if not paths:
            return
        event.acceptProposedAction()
        at = self.doc.page_count if self.doc else 0
        self._on_pdfs_dropped(paths, at)

    def _on_pdfs_dropped(self, paths: list[str], at: int) -> None:
        if not paths:
            return
        # ยังไม่ได้เปิดไฟล์ -> เปิดไฟล์แรก ที่เหลือแทรกต่อท้าย
        if not self.doc or not self.doc.page_count:
            self._open_path(paths[0])
            if len(paths) > 1 and self.doc:
                try:
                    self.doc.insert_pdfs(self.doc.page_count, paths[1:])
                except Exception as exc:
                    QMessageBox.critical(self, t("ins.failed"), str(exc))
                    return
                self._refresh_all(keep_row=0)
            return

        at = max(0, min(at, self.doc.page_count))
        try:
            added = self.doc.insert_pdfs(at, paths)
        except Exception as exc:
            QMessageBox.critical(self, t("ins.failed"), str(exc))
            return
        self._refresh_all(keep_row=at)
        self.statusBar().showMessage(
            t("ins.done", files=len(paths), pages=added, at=at + 1), 7000)

    def showEvent(self, event) -> None:
        """หน้าต่างแสดงจริงแล้ว (รู้ความกว้างจริง) — สร้างภาพย่อให้พอดีแผงอีกครั้ง"""
        super().showEvent(event)
        if self.doc and not getattr(self, "_thumbs_sized", False):
            self._thumbs_sized = True
            self._thumb_resize_timer.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.doc:
            self._thumb_resize_timer.start()   # หน่วงไว้ ไม่เรนเดอร์ถี่ตอนลากขอบหน้าต่าง

    def bring_to_front(self) -> None:
        """ดึงหน้าต่างขึ้นมาอยู่หน้าสุด (เปิดไฟล์จาก Explorer/Outlook หรือเผลอเปิดซ้ำ)"""
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()
        _force_foreground(self)

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            self._clear_autosave()   # ปิดปกติ (เลือกทิ้ง/บันทึกแล้ว) ไม่ต้องเก็บงานค้าง
            event.accept()
        else:
            event.ignore()



def _system_default_printer() -> str:
    """ชื่อเครื่องพิมพ์หลัก (Default) ที่ตั้งไว้ใน Windows — ไม่มีคืน ""

    ถามจาก Windows ตรงๆ ก่อน (GetDefaultPrinterW) เพราะได้ค่าล่าสุดเสมอ
    แม้ผู้ใช้เปลี่ยนเครื่องหลักหลังเปิดโปรแกรม หรือเปิด "ให้ Windows จัดการเครื่องพิมพ์หลัก"
    ถ้าไม่ได้ค่อยถาม Qt
    """
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            size = wintypes.DWORD(0)
            winspool = ctypes.windll.winspool.drv
            winspool.GetDefaultPrinterW(None, ctypes.byref(size))
            if size.value:
                buf = ctypes.create_unicode_buffer(size.value)
                if winspool.GetDefaultPrinterW(buf, ctypes.byref(size)):
                    return buf.value
        except Exception:
            pass
    try:
        from PySide6.QtPrintSupport import QPrinterInfo
        default = QPrinterInfo.defaultPrinter()
        return "" if default.isNull() else default.printerName()
    except Exception:
        return ""

_SINGLE_INSTANCE_KEY = "BallcarPDF-single-instance"
_COMBINE_KEY = "BallcarPDF-combine"


def _force_foreground(window) -> bool:
    """บังคับให้หน้าต่างขึ้นมาอยู่หน้าสุดจริงๆ บน Windows — คืน True ถ้าทำได้

    Windows ห้ามโปรเซสที่ "ไม่ได้อยู่หน้า" เรียก SetForegroundWindow ตรงๆ (กันแอปแย่ง
    โฟกัสผู้ใช้) raise_()/activateWindow() ของ Qt จึงได้แค่กะพริบที่ taskbar
    เปิดไฟล์ PDF จาก Outlook/Explorer แล้วโปรแกรมไปโผล่ข้างหลังเพราะเหตุนี้

    วิธีที่ใช้ (ทุกขั้นตอนไม่บล็อก):
      1. คลายจากย่อเก็บ (ถ้าถูกย่อไว้)
      2. SetForegroundWindow ตรงๆ — สำเร็จเมื่อเรามีสิทธิ์อยู่แล้ว เช่น เพิ่งถูกผู้ใช้สั่งเปิด
         หรือตัวที่เปิดซ้ำเรียก AllowSetForegroundWindow ยกสิทธิ์มาให้
      3. ถ้าไม่สำเร็จ: ยกเป็น topmost แวบหนึ่งแล้วปลด + กะพริบที่ taskbar เรียกสายตา

    ⚠️ ห้ามใช้ AttachThreadInput ผูกกับเธรดของโปรเซสอื่นเด็ดขาด — มันรอจนกว่าเธรดนั้น
    จะปั๊มข้อความ ถ้าหน้าต่างที่อยู่หน้าจอกำลังค้าง/ไม่ตอบสนอง โปรแกรมเราจะค้างตามไปด้วย
    (เคยทำให้ค้างจริงมาแล้ว) การเด้งไม่ขึ้นหน้าสุดเป็นแค่ความไม่สะดวก แต่ค้างคือใช้งานไม่ได้
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = int(window.winId())

        SW_RESTORE = 9
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)

        fg = user32.GetForegroundWindow()
        if fg == hwnd:
            return True

        # ปลดล็อก foreground: Windows ยอมให้ตั้งหน้าต่างหน้าสุดได้ ถ้าโปรเซสเรา "รับ input ล่าสุด"
        # จึงจำลองกดแป้นเปล่า (keycode 0 ไม่มีผลกับโปรแกรมใด) ก่อนเรียก SetForegroundWindow
        # ไม่บล็อก และไม่ต้องผูกเธรดกับโปรเซสอื่น (ซึ่งเคยทำให้ค้าง)
        # จำเป็นตอนเปิดจาก Outlook: สิทธิ์ขึ้นหน้าสุดถูกใช้ไปกับ splash ตอนเปิดโปรแกรม
        # พอ splash ปิด โฟกัสกลับไปที่ Outlook แล้วหน้าต่างหลักขึ้นหน้าสุดไม่ได้อีก
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(0, 0, 0, 0)
        user32.keybd_event(0, 0, KEYEVENTF_KEYUP, 0)

        user32.ShowWindow(hwnd, 5)          # SW_SHOW
        user32.BringWindowToTop(hwnd)
        ok = bool(user32.SetForegroundWindow(hwnd))
        if ok:
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)

        if not ok:
            # แผนสำรอง (ไม่บล็อก): ยกเป็น topmost แวบหนึ่งแล้วปลด — ไม่ค้างเป็นหน้าต่างลอย
            HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
            SWP = 0x0001 | 0x0002 | 0x0010     # NOSIZE | NOMOVE | NOACTIVATE
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP)

            # กะพริบที่ taskbar เรียกสายตา เผื่อ Windows ยังไม่ยอมให้ขึ้นหน้าสุด
            class FLASHWINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND),
                            ("dwFlags", wintypes.DWORD), ("uCount", wintypes.UINT),
                            ("dwTimeout", wintypes.DWORD)]
            FLASHW_ALL, FLASHW_TIMERNOFG = 0x3, 0xC
            fi = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd,
                            FLASHW_ALL | FLASHW_TIMERNOFG, 3, 0)
            user32.FlashWindowEx(ctypes.byref(fi))
        return True
    except Exception:
        return False      # ไม่ใช่เรื่องคอขาดบาดตาย เปิดโปรแกรมต่อได้


def _send_to_combine_collector(files: list[str], timeout_ms: int = 500) -> bool:
    """ส่งไฟล์ให้ตัวที่กำลังเปิดหน้าต่างรวมไฟล์อยู่ — คืน True ถ้าส่งได้ (ตัวนี้ควรออก)

    Windows เรียกโปรแกรมทีละไฟล์ตอนคลิกขวาหลายไฟล์ ตัวแรกจะเป็น "ตัวรวบ"
    ตัวที่เหลือส่งชื่อไฟล์มาให้แล้วปิดตัวเอง จะได้เห็นหน้าต่างรวมไฟล์อันเดียว
    """
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(_COMBINE_KEY)
    if not sock.waitForConnected(timeout_ms):
        return False
    # ต้องปล่อยให้ฝั่งรับ accept connection ก่อน ไม่งั้นข้อมูลที่เขียนหลุดหาย
    QApplication.processEvents()
    sock.write("\n".join(files).encode("utf-8"))
    sock.flush()
    for _ in range(20):                  # รอให้ส่งจบจริงก่อนปิด
        if sock.bytesToWrite() == 0:
            break
        QApplication.processEvents()
        sock.waitForBytesWritten(50)
    sock.disconnectFromServer()
    sock.waitForDisconnected(timeout_ms)
    return True


_combine_lock_handle = None       # ต้องถือไว้ตลอดอายุโปรเซส ไม่งั้น mutex หลุด


def _try_become_collector():
    """ชิงเป็น "ตัวรวบไฟล์" — คืน server ถ้าได้, None ถ้ามีตัวอื่นเป็นอยู่แล้ว

    ใช้ named mutex ของ Windows ชิงสิทธิ์ — ห้ามใช้ QLocalServer.listen() ชิง
    เพราะบน Windows เป็น named pipe ที่เปิดชื่อเดียวกันได้หลายตัว (listen สำเร็จหมด
    ทุกโปรเซส) สุดท้ายกลายเป็นตัวรวบทุกตัว = เห็นหลายหน้าต่าง
    """
    global _combine_lock_handle
    ERROR_ALREADY_EXISTS = 183
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        handle = kernel32.CreateMutexW(None, False, "BallcarPDF-combine-collector")
        if handle and kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return None                  # มีตัวรวบอยู่แล้ว
        _combine_lock_handle = handle    # เราเป็นตัวรวบ ถือ mutex ไว้
    except Exception:
        pass       # ไม่ใช่ Windows หรือเรียกไม่ได้ — ถือว่าเป็นตัวรวบ

    from PySide6.QtNetwork import QLocalServer
    QLocalServer.removeServer(_COMBINE_KEY)    # ล้างช่องค้างจากรอบก่อน
    server = QLocalServer()
    server.listen(_COMBINE_KEY)
    return server


def _attach_combine_handler(server, window) -> None:
    """ผูกตัวรับไฟล์เข้ากับ server (เรียกหลังมีหน้าต่างแล้ว)"""

    def on_connection():
        conn = server.nextPendingConnection()
        if not conn:
            return
        buffer = bytearray()

        def on_ready():
            # รออ่านผ่านสัญญาณ ไม่อ่านทันที (ตัวส่งอาจยังไม่ได้เขียนข้อมูล)
            buffer.extend(bytes(conn.readAll()))
            paths = [p for p in buffer.decode("utf-8", errors="ignore").split("\n") if p.strip()]
            if paths:
                window.add_merge_files(paths)

        conn.readyRead.connect(on_ready)
        conn.disconnected.connect(on_ready)   # เผื่อข้อมูลมาพร้อมการปิด
        conn.disconnected.connect(conn.deleteLater)

    server.newConnection.connect(on_connection)
    # ตัวที่ส่งมาก่อนหน้าต่างพร้อม จะค้างอยู่ในคิว — ดึงมาจัดการด้วย
    while server.hasPendingConnections():
        on_connection()


def _notify_running_instance() -> bool:
    """ถ้ามีโปรแกรมเปิดอยู่แล้ว บอกให้มันเด้งขึ้นมาหน้าสุด แล้วคืน True (ตัวใหม่ควรออก)"""
    from PySide6.QtNetwork import QLocalSocket
    sock = QLocalSocket()
    sock.connectToServer(_SINGLE_INSTANCE_KEY)
    if sock.waitForConnected(400):
        # ยกสิทธิ์ "ตั้งหน้าต่างหน้าสุด" ให้โปรเซสที่เปิดอยู่ ไม่งั้นมันเด้งขึ้นมาไม่ได้
        # (สิทธิ์นี้เป็นของตัวที่เพิ่งถูกผู้ใช้สั่งเปิด ซึ่งก็คือตัวเราที่กำลังจะปิดตัวเอง)
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(-1)   # ASFW_ANY
            except Exception:
                pass
        sock.write(b"RAISE")
        sock.flush()
        sock.waitForBytesWritten(400)
        sock.disconnectFromServer()
        return True
    return False


def _listen_single_instance(window) -> object:
    """เปิด local server ให้ตัวที่เผลอเปิดซ้ำติดต่อเข้ามาเพื่อสั่งเด้งหน้าต่างนี้"""
    from PySide6.QtNetwork import QLocalServer
    QLocalServer.removeServer(_SINGLE_INSTANCE_KEY)   # กัน socket ค้างจากรอบก่อน
    server = QLocalServer()
    server.listen(_SINGLE_INSTANCE_KEY)

    def on_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(200)
            conn.readAll()
            window.bring_to_front()
            conn.disconnectFromServer()

    server.newConnection.connect(on_connection)
    return server   # ต้องเก็บ reference ไว้ ไม่งั้นถูกเก็บขยะ


def _close_splash() -> None:
    """ปิด splash ของ PyInstaller (ถ้ามี) หลังหน้าต่างพร้อม"""
    try:
        import pyi_splash   # มีเฉพาะตอนรันเป็น .exe ที่ build พร้อม splash
        pyi_splash.close()
    except Exception:
        pass


def main() -> None:
    i18n.load_language()   # ต้องโหลดก่อนสร้างหน้าต่าง ไม่งั้นเมนูเป็นภาษาเริ่มต้น

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    errorlog.setup_logging(APP_VERSION)

    icon = app_icon_path()
    if icon:
        app.setWindowIcon(QIcon(str(icon)))
        # บอก Windows ว่าเป็นแอปของตัวเอง ไม่งั้น taskbar จะไปใช้ไอคอนของ Python
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BallcarPDF.App")
        except Exception:
            pass  # ไม่ใช่ Windows หรือเรียกไม่ได้ ก็ข้ามไป ไม่ใช่เรื่องคอขาดบาดตาย

    # คลิกขวาหลายไฟล์ใน Explorer -> "รวมไฟล์ด้วย Ballcar PDF"
    combine = COMBINE_FLAG in sys.argv
    files = pdf_files_from_argv(sys.argv)
    initial = None if combine else (files[0] if files else None)

    # คลิกขวาหลายไฟล์: Windows เรียกโปรแกรมทีละไฟล์
    # ชิงเป็น "ตัวรวบ" ก่อน — ใครแพ้ส่งชื่อไฟล์ไปให้ตัวรวบแล้วปิดตัวเอง
    # (จะได้เห็นหน้าต่างรวมไฟล์อันเดียว ไม่ใช่หลายหน้าต่างไฟล์ละอัน)
    combine_server = None
    if combine and files:
        combine_server = _try_become_collector()
        errorlog.log_info("combine: files=%s collector=%s", files, combine_server is not None)
        if combine_server is None:
            for attempt in range(15):        # ตัวรวบอาจยังเปิดหน้าต่างไม่เสร็จ ลองส่งซ้ำ
                if _send_to_combine_collector(files):
                    errorlog.log_info("combine: ส่งให้ตัวรวบสำเร็จ (รอบ %d) ปิดตัวเอง", attempt + 1)
                    _close_splash()
                    return
                time.sleep(0.2)
            errorlog.log_info("combine: ส่งไม่สำเร็จ เปิดหน้าต่างเอง")
            # ส่งไม่สำเร็จเลย — เปิดหน้าต่างของตัวเองไปเลย ดีกว่าเงียบหาย

    # กันเผลอเปิดโปรแกรมซ้ำ (เปิดช้าแล้วดับเบิลคลิกอีกที) — เฉพาะตอนเปิดโปรแกรมเปล่า
    # ถ้าเปิดจากไฟล์ .pdf (association) หรือสั่งรวมไฟล์ ยังให้เปิดหน้าต่างใหม่ได้ตามเดิม
    if initial is None and not combine and _notify_running_instance():
        _close_splash()
        return   # มีหน้าต่างเปิดอยู่แล้ว เด้งตัวนั้นขึ้นมาแทน

    window = MainWindow()
    # ดักข้อผิดพลาดที่ไม่ได้ดัก -> เขียน log + เด้งกล่องบอก + เซฟงานกู้คืนก่อน
    errorlog.install_excepthook(app, on_crash=window._autosave_tick)
    window.show()
    _close_splash()
    # splash ของ PyInstaller เป็นหน้าต่างแยก พอปิดแล้วโฟกัสมักตกไปที่โปรแกรมที่อยู่ข้างหลัง
    # (Outlook/Explorer ที่สั่งเปิดไฟล์) จึงต้องดึงตัวเองขึ้นมาหน้าสุดอีกทีหลัง event loop เริ่ม
    QTimer.singleShot(0, window.bring_to_front)
    QTimer.singleShot(250, window.bring_to_front)   # เผื่อ splash ปิดช้ากว่านั้น
    QTimer.singleShot(900, window.bring_to_front)   # เผื่อไฟล์ใหญ่/เครื่องช้า โหลดเสร็จช้า

    server = None
    if combine:
        if combine_server is not None:
            _attach_combine_handler(combine_server, window)
            app._combine_server = combine_server      # กัน GC
        # หน้าต่างรวมไฟล์รับไฟล์เพิ่มได้ตลอดระหว่างเปิดอยู่ (ผ่าน add_merge_files)
        QTimer.singleShot(0, lambda: window.merge_dialog(preset_files=sorted(files)))
    elif initial:
        window._open_path(initial)
    else:
        server = _listen_single_instance(window)   # เก็บ ref กัน GC
        # ไม่ได้เปิดไฟล์เจาะจง — เช็คว่ามีงานค้างจากครั้งก่อนให้กู้ไหม
        window.offer_recovery()

    app._single_instance_server = server   # ผูกอายุไว้กับ app

    # ตรวจอัปเดตจากเซิร์ฟเวอร์ภายในแบบเงียบ หลังหน้าต่างขึ้นแล้ว 1.5 วิ
    # (ไม่บล็อกการเปิด · ต่อไม่ได้ก็เงียบ · ไม่ทำตอนเปิดจากไฟล์/รวมไฟล์)
    if not combine and not initial:
        QTimer.singleShot(1500, lambda: window.check_updates(quiet=True))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
