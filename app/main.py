"""Ballcar PDF — หน้าต่างหลัก"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QToolButton,
    QPushButton, QSplitter, QStatusBar, QToolBar, QVBoxLayout, QWidget,
)

if __package__ in (None, ""):  # รันตรงๆ ด้วย python app/main.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app import i18n, library, pdfops
    from app.i18n import t
    from app.pdfops import PdfDocument, merge_files, parse_page_ranges
    from app.viewer import PageViewer, pixmap_to_qimage
else:
    from . import i18n, library, pdfops
    from .i18n import t
    from .pdfops import PdfDocument, merge_files, parse_page_ranges
    from .viewer import PageViewer, pixmap_to_qimage

APP_NAME = "Ballcar PDF"

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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.doc: PdfDocument | None = None
        self.setWindowTitle("Ballcar PDF")
        self.resize(1280, 860)

        self.viewer = PageViewer()
        self.thumbs = QListWidget()
        self.thumbs.setIconSize(QSize(140, 190))
        self.thumbs.setSelectionMode(QListWidget.ExtendedSelection)
        self.thumbs.setMaximumWidth(210)
        self.thumbs.currentRowChanged.connect(self._on_thumb_selected)
        # ลากวางเพื่อสลับลำดับหน้าได้โดยตรง
        self.thumbs.setDragDropMode(QListWidget.InternalMove)
        self.thumbs.setDefaultDropAction(Qt.MoveAction)
        self.thumbs.model().rowsMoved.connect(self._on_rows_moved)
        self._applying_reorder = False
        # คลิกขวาที่หน้า -> เมนูลัด
        self.thumbs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.thumbs.customContextMenuRequested.connect(self._thumb_context_menu)

        self.text_panel = QPlainTextEdit(readOnly=True)
        self.text_panel.setPlaceholderText(t("text.placeholder"))
        self.text_panel.setMaximumWidth(360)
        self.text_panel.hide()

        self.thumbs.setToolTip(t("thumb.tip"))
        self.viewer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.viewer.customContextMenuRequested.connect(self._viewer_context_menu)
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
        done_btn = self._done_btn = QPushButton(t("bar.done"))
        done_btn.clicked.connect(self.deselect_stamp)
        stamp_layout.addWidget(stamp_tip)
        stamp_layout.addStretch(1)
        for b in (move_btn, save_btn, del_btn, done_btn):
            stamp_layout.addWidget(b)
        style_action_bar(self._stamp_bar, "stampBar", "#fff3cd", "#ffcf6b")
        self._stamp_bar.hide()
        self.viewer.stampSelected.connect(self._on_stamp_selected)
        self.viewer.stampEditRequested.connect(self.edit_selected_stamp)

        # ค่าเริ่มต้นของข้อความที่จะเพิ่ม (จำค่าล่าสุดที่ผู้ใช้ตั้ง)
        self._last_font_size = 16.0
        self._last_color = (0.0, 0.0, 0.0)

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
        self._text_del_btn = QPushButton(t("text.delete_btn"))
        self._text_del_btn.clicked.connect(self.delete_selected_textbox)
        self._text_done_btn = QPushButton(t("bar.done"))
        self._text_done_btn.clicked.connect(self.deselect_textbox)
        text_layout.addWidget(self._text_tip)
        text_layout.addStretch(1)
        for b in (self._text_edit_btn, self._text_move_btn, self._text_color_btn,
                  self._text_del_btn, self._text_done_btn):
            text_layout.addWidget(b)
        style_action_bar(self._text_bar, "textBar", "#d1e7dd", "#8fc4a8")
        self._text_bar.hide()
        self.viewer.textboxSelected.connect(self._on_textbox_selected)
        self.viewer.textboxEditRequested.connect(self.edit_selected_textbox)
        self.viewer.pointPicked.connect(self._on_point_picked)
        self.viewer.editPointPicked.connect(self._on_edit_point_picked)
        self.viewer.rectDragged.connect(self._on_rect_dragged)

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

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(2)
        left_layout.addWidget(self.thumbs)
        hint = self._hint_label = QLabel(t("thumb.hint"))
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#888; font-size:11px; padding:2px;")
        left_layout.addWidget(hint)
        left.setMaximumWidth(215)

        splitter = QSplitter()
        splitter.addWidget(left)

        viewer_area = QWidget()
        viewer_layout = QVBoxLayout(viewer_area)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)
        viewer_layout.addWidget(self._placing_bar)
        viewer_layout.addWidget(self._stamp_bar)
        viewer_layout.addWidget(self._text_bar)
        viewer_layout.addWidget(self._highlight_bar)
        viewer_layout.addWidget(self.viewer)
        splitter.addWidget(viewer_area)

        splitter.addWidget(self.text_panel)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.setStatusBar(QStatusBar())
        self._build_toolbars()
        self._build_menu()
        self._update_state()

    # ---------------- แถบเครื่องมือ / เมนู ----------------

    def _act(self, text: str, slot, shortcut: str | None = None, tip: str | None = None) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.setToolTip(tip or text)
        return action

    def _build_toolbars(self) -> None:
        bar = QToolBar("main")
        bar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(bar)
        self._toolbar = bar

        self.act_open = self._act(t("file.open"), self.open_file, "Ctrl+O")
        self.act_save = self._act(t("file.save"), self.save_file, "Ctrl+S")
        self.act_save_as = self._act(t("file.save_as"), self.save_file_as, "Ctrl+Shift+S")
        self.act_print = self._act(t("file.print"), self.print_document, "Ctrl+P")
        for a in (self.act_open, self.act_save, self.act_save_as, self.act_print):
            bar.addAction(a)

        bar.addSeparator()
        self.act_undo = self._act("↶ " + t("edit.undo"), self.undo, "Ctrl+Z")
        self.act_redo = self._act("↷ " + t("edit.redo"), self.redo, "Ctrl+Y")
        bar.addAction(self.act_undo)
        bar.addAction(self.act_redo)

        bar.addSeparator()
        self.act_prev = self._act(t("tb.prev"), lambda: self.goto_page(self.viewer.index - 1), "PgUp")
        self.act_next = self._act(t("tb.next"), lambda: self.goto_page(self.viewer.index + 1), "PgDown")
        bar.addAction(self.act_prev)
        bar.addAction(self.act_next)

        self.page_box = QLineEdit(maximumWidth=60, alignment=Qt.AlignCenter)
        self.page_box.returnPressed.connect(self._on_page_box)
        bar.addWidget(self.page_box)
        self.page_label = QLabel(" / 0   ")
        bar.addWidget(self.page_label)

        bar.addSeparator()
        bar.addAction(self._act(t("tb.zoom_out"), lambda: self.viewer.set_zoom(self.viewer.zoom / 1.25), "Ctrl+-"))
        bar.addAction(self._act(t("tb.zoom_in"), lambda: self.viewer.set_zoom(self.viewer.zoom * 1.25), "Ctrl+="))
        bar.addAction(self._act(t("tb.fit_width"), self.viewer.fit_width))

        bar.addSeparator()
        previous_search = getattr(self, "search_box", None)
        self.search_box = QLineEdit(placeholderText=t("tb.search_placeholder"), maximumWidth=220)
        if previous_search is not None:
            self.search_box.setText(previous_search.text())   # เปลี่ยนภาษาแล้วคำค้นไม่หาย
        self.search_box.returnPressed.connect(self.search_next)
        bar.addWidget(self.search_box)
        self.act_find = self._act(t("tb.find_next"), self.search_next, "F3")
        bar.addAction(self.act_find)
        self.act_clear_find = self._act(t("tb.clear_find"), self.clear_search)
        bar.addAction(self.act_clear_find)

        bar.addSeparator()
        self.act_add_text = self._act(t("tb.add_text"), self.add_text_dialog)
        bar.addAction(self.act_add_text)
        self.act_edit_text = self._act(t("tb.edit_text"), self.edit_text_dialog)
        bar.addAction(self.act_edit_text)
        self.act_highlight = self._act(t("tb.highlight"), self.toggle_highlight_mode)
        bar.addAction(self.act_highlight)

        self.sig_button = QToolButton()
        self.sig_button.setText(t("tb.signature"))
        self.sig_button.setPopupMode(QToolButton.InstantPopup)
        self.sig_menu = QMenu(self)
        self.sig_menu.aboutToShow.connect(self._build_signature_menu)
        self.sig_button.setMenu(self.sig_menu)
        self.sig_button.setToolTip(t("tb.signature_tip"))
        bar.addWidget(self.sig_button)

    def _build_menu(self) -> None:
        menu = self.menuBar()
        menu.clear()   # เปลี่ยนภาษาแล้วสร้างใหม่ทั้งแถบ

        m_file = menu.addMenu(t("menu.file"))
        for a in (self.act_open, self.act_save, self.act_save_as):
            m_file.addAction(a)
        m_file.addSeparator()
        m_file.addAction(self.act_print)
        m_file.addSeparator()
        m_file.addAction(self._act(t("file.exit"), self.close, "Ctrl+Q"))

        m_edit = menu.addMenu(t("menu.edit"))
        m_edit.addAction(self.act_undo)
        m_edit.addAction(self.act_redo)

        m_page = menu.addMenu(t("menu.pages"))
        self.page_actions = [
            self._act(t("pages.insert_blank"), self.insert_blank),
            self._act(t("pages.insert_pdf"), self.insert_pdf_file),
            self._act(t("pages.delete"), self.delete_selected, "Delete"),
            self._act(t("pages.move_up"), lambda: self.move_selected(-1), "Ctrl+Shift+Up"),
            self._act(t("pages.move_down"), lambda: self.move_selected(1), "Ctrl+Shift+Down"),
            self._act(t("pages.rotate_left"), lambda: self.rotate_selected(-90)),
            self._act(t("pages.rotate_right"), lambda: self.rotate_selected(90)),
            self._act(t("pages.rotate_180"), lambda: self.rotate_selected(180)),
        ]
        for a in self.page_actions:
            m_page.addAction(a)

        m_tools = menu.addMenu(t("menu.tools"))
        self.tool_actions = [
            self._act(t("tools.add_text"), self.add_text_dialog),
            self._act(t("tools.edit_text"), self.edit_text_dialog),
            self._act(t("tools.fill_form"), self.fill_form_dialog),
            self._act(t("tools.password"), self.password_dialog),
            self._act(t("tools.merge"), self.merge_dialog),
            self._act(t("tools.split"), self.split_dialog),
            self._act(t("tools.page_numbers"), self.add_numbers_dialog),
            self._act(t("tools.save_images"), self.export_images_dialog),
            self._act(t("tools.extract_text"), self.extract_all_text),
            self._act(t("tools.ocr"), self.ocr_dialog),
            self._act(t("tools.to_word"), self.export_word),
            self._act(t("tools.to_excel"), self.export_excel),
            self._act(t("tools.extract_images"), self.export_embedded_images),
            self._act(t("tools.watermark_text"), self.watermark_dialog),
            self._act(t("tools.watermark_image"), self.image_watermark_dialog),
            self._act(t("tools.signature"), self.signature_dialog),
        ]
        for a in self.tool_actions:
            m_tools.addAction(a)

        m_view = menu.addMenu(t("menu.view"))
        toggle_text = QAction(t("view.show_text"), self, checkable=True)
        toggle_text.setChecked(self.text_panel.isVisible())
        toggle_text.toggled.connect(self._toggle_text_panel)
        m_view.addAction(toggle_text)

        m_lang = menu.addMenu(t("menu.language"))
        for code, key in (("th", "lang.thai"), ("en", "lang.english")):
            action = QAction(t(key), self, checkable=True)
            action.setChecked(i18n.current() == code)
            action.triggered.connect(lambda _=False, c=code: self.change_language(c))
            m_lang.addAction(action)

        m_help = menu.addMenu(t("menu.help"))
        m_help.addAction(self._act(t("help.about"), self.show_about))

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
        QMessageBox.about(self, t("help.about_title"), t("help.about_body", version=APP_VERSION))

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

    def _rebuild_thumbs(self, keep_row: int | None = None) -> None:
        row = self.thumbs.currentRow() if keep_row is None else keep_row
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        if self.doc:
            for i in range(self.doc.page_count):
                pix = QPixmap.fromImage(pixmap_to_qimage(self.doc.render_page(i, THUMB_ZOOM)))
                item = QListWidgetItem(QIcon(pix), t("thumb.page", n=i + 1))
                item.setData(Qt.UserRole, i)  # ใช้อ้างลำดับเดิมตอนลากวาง
                self.thumbs.addItem(item)
        self.thumbs.blockSignals(False)
        if self.doc and self.doc.page_count:
            self.thumbs.setCurrentRow(max(0, min(row, self.doc.page_count - 1)))

    def _refresh_all(self, keep_row: int | None = None) -> None:
        self._rebuild_thumbs(keep_row)
        self.viewer.refresh()
        self._update_text_panel()
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
        menu.addAction("แทรกไฟล์ PDF อื่นตรงนี้…", self.insert_pdf_file)
        menu.addSeparator()
        menu.addAction(f"บันทึก {label} เป็นไฟล์ PDF ใหม่…", self.split_selected)
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

    def _toggle_text_panel(self, on: bool) -> None:
        self.text_panel.setVisible(on)
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
        self._update_state()
        self.statusBar().showMessage(f"บันทึกแล้ว: {path}", 5000)
        return True

    def print_document(self) -> None:
        if not self.doc:
            return
        printer = QPrinter(QPrinter.HighResolution)
        printer.setFromTo(1, self.doc.page_count)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("พิมพ์เอกสาร")
        if dialog.exec() != QPrintDialog.Accepted:
            return

        if printer.printRange() == QPrinter.PageRange:
            pages = range(printer.fromPage() - 1, printer.toPage())
        else:
            pages = range(self.doc.page_count)

        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "พิมพ์ไม่สำเร็จ", "เริ่มงานพิมพ์ไม่ได้")
            return
        try:
            dpi = printer.resolution()
            for n, i in enumerate(pages):
                if n:
                    printer.newPage()
                image = pixmap_to_qimage(self.doc.render_page(i, dpi / 72))
                target = painter.viewport()
                scaled = image.scaled(target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                # จัดหน้าให้อยู่กึ่งกลางกระดาษ
                x = (target.width() - scaled.width()) // 2
                y = (target.height() - scaled.height()) // 2
                painter.drawImage(x, y, scaled)
        finally:
            painter.end()
        self.statusBar().showMessage("ส่งงานพิมพ์แล้ว", 5000)

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

    def insert_pdf_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "เลือกไฟล์ที่จะแทรก", "", PDF_FILTER)
        if not path:
            return
        rows = self._selected_rows()
        at = rows[0] if rows else 0
        try:
            added = self.doc.insert_pdf(at, path)
        except Exception as exc:
            QMessageBox.critical(self, "แทรกไฟล์ไม่สำเร็จ", str(exc))
            return
        self._refresh_all(keep_row=at)
        self.statusBar().showMessage(f"แทรก {added} หน้าที่ตำแหน่งหน้า {at + 1}", 5000)

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

    def merge_dialog(self) -> None:
        others, _ = QFileDialog.getOpenFileNames(
            self, "เลือกไฟล์ PDF ที่จะรวมต่อท้ายเอกสารนี้", "", PDF_FILTER
        )
        if not others:
            return
        target, _ = QFileDialog.getSaveFileName(self, "บันทึกไฟล์ที่รวมแล้วเป็น", "รวมไฟล์.pdf", PDF_FILTER)
        if not target:
            return
        try:
            sources = [self.doc.path] if self.doc.path else []
            if not sources:
                QMessageBox.warning(self, "รวมไฟล์", "กรุณาบันทึกเอกสารปัจจุบันก่อน")
                return
            merge_files(sources + others, target)
        except Exception as exc:
            QMessageBox.critical(self, "รวมไฟล์ไม่สำเร็จ", str(exc))
            return
        self.statusBar().showMessage(f"รวม {len(others) + 1} ไฟล์แล้ว: {target}", 6000)

    def split_dialog(self) -> None:
        spec, ok = QInputDialog.getText(
            self, "แยกไฟล์",
            f"ระบุช่วงหน้าที่จะแยกออกมา (เอกสารมี {self.doc.page_count} หน้า)\nตัวอย่าง: 1-3,5,8-10",
        )
        if not ok:
            return
        try:
            indexes = parse_page_ranges(spec, self.doc.page_count)
        except ValueError as exc:
            QMessageBox.warning(self, "ช่วงหน้าไม่ถูกต้อง", str(exc))
            return
        target, _ = QFileDialog.getSaveFileName(self, "บันทึกไฟล์ที่แยกเป็น", "แยกหน้า.pdf", PDF_FILTER)
        if not target:
            return
        try:
            self.doc.extract_to(indexes, target)
        except Exception as exc:
            QMessageBox.critical(self, "แยกไฟล์ไม่สำเร็จ", str(exc))
            return
        self.statusBar().showMessage(f"แยก {len(indexes)} หน้าไปที่ {target}", 6000)

    def add_numbers_dialog(self) -> None:
        positions = {
            "ล่างกึ่งกลาง": "bottom-center", "ล่างขวา": "bottom-right", "ล่างซ้าย": "bottom-left",
            "บนกึ่งกลาง": "top-center", "บนขวา": "top-right", "บนซ้าย": "top-left",
        }
        label, ok = QInputDialog.getItem(self, "เพิ่มเลขหน้า", "ตำแหน่ง:", list(positions), 0, False)
        if not ok:
            return
        fmt, ok = QInputDialog.getItem(
            self, "เพิ่มเลขหน้า", "รูปแบบ:",
            ["{page}/{total}", "{page}", "หน้า {page}", "- {page} -"], 0, True,
        )
        if not ok:
            return
        self.doc.add_page_numbers(fmt=fmt, position=positions[label])
        self._refresh_all()
        self.statusBar().showMessage("เพิ่มเลขหน้าแล้ว — อย่าลืมบันทึก", 6000)

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
        """ถามว่าจะทำกับหน้าที่เลือก หรือทุกหน้า"""
        rows = self._selected_rows()
        options = [f"ทุกหน้า ({self.doc.page_count} หน้า)", f"เฉพาะหน้าที่เลือก ({len(rows)} หน้า)"]
        choice, ok = QInputDialog.getItem(self, title, "ใส่ที่หน้าไหน:", options, 0, False)
        if not ok:
            return None
        return list(range(self.doc.page_count)) if choice.startswith("ทุกหน้า") else rows

    def watermark_dialog(self) -> None:
        text, ok = QInputDialog.getText(self, "ใส่ลายน้ำข้อความ", "ข้อความลายน้ำ:", text="สำเนา")
        if not ok or not text.strip():
            return
        indexes = self._ask_scope("ใส่ลายน้ำข้อความ")
        if indexes is None:
            return
        percent, ok = QInputDialog.getInt(
            self, "ใส่ลายน้ำข้อความ", "ความเข้ม (%):", 18, 5, 100, 1
        )
        if not ok:
            return
        angle, ok = QInputDialog.getInt(self, "ใส่ลายน้ำข้อความ", "องศาเอียง:", 45, -90, 90, 15)
        if not ok:
            return
        try:
            self.doc.add_text_watermark(text, indexes, opacity=percent / 100, angle=angle)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "ใส่ลายน้ำไม่สำเร็จ", str(exc))
            return
        self._refresh_all()
        self.statusBar().showMessage(f"ใส่ลายน้ำ {len(indexes)} หน้าแล้ว — Ctrl+Z ถ้าไม่ถูกใจ", 7000)

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

        self.deselect_stamp()
        self._pending_image = path
        self.viewer.start_placing(path)
        self.viewer.overlay.committed.connect(self.commit_placement)
        self._placing_bar.show()
        self.statusBar().showMessage(
            "ลากตรงกลางเพื่อย้าย · ลากมุมเพื่อย่อ/ขยาย · Enter หรือดับเบิลคลิก = ยืนยัน · Esc = ยกเลิก", 0
        )

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
                message = "ย้าย/ปรับขนาดลายเซ็นแล้ว"
            else:
                if not image:
                    return
                stamp = self.doc.add_stamp(page_index, image, rect)
                self.viewer.selected_stamp = stamp
                message = "วางลายเซ็นแล้ว — คลิกที่ลายเซ็นเพื่อย้าย/ปรับขนาดได้อีก"
        except Exception as exc:
            QMessageBox.critical(self, "วางลายเซ็นไม่สำเร็จ", str(exc))
            return
        self._refresh_all(keep_row=page_index)
        self.statusBar().showMessage(message, 7000)

    def _on_stamp_selected(self) -> None:
        """คลิกโดนลายเซ็นที่วางไว้ — โชว์แถบให้ย้าย/ปรับขนาด/ลบ"""
        self._stamp_bar.show()
        self.viewer.refresh()
        self.statusBar().showMessage(
            "เลือกลายเซ็นแล้ว — กด 'ย้าย/ปรับขนาด' หรือ Delete เพื่อลบ", 6000
        )

    def edit_selected_stamp(self) -> None:
        stamp = self.viewer.selected_stamp
        if stamp is None:
            return
        self._stamp_bar.hide()
        self.viewer.start_editing(stamp)
        self.viewer.overlay.committed.connect(self.commit_placement)
        self._placing_bar.show()

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
        self.statusBar().showMessage("ลบลายเซ็นแล้ว — Ctrl+Z เพื่อเอากลับ", 6000)

    def cancel_placement(self, quiet: bool = False) -> None:
        self.viewer.cancel_placing()
        self._pending_image = None
        self._placing_bar.hide()
        if not quiet:
            self.statusBar().showMessage("ยกเลิกการวางลายเซ็นแล้ว", 4000)

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
        text, ok = self._ask_text_content(t("edit.edit_title"), box.text)
        if ok:
            self.doc.update_textbox_content(box, text=text)
        self.viewer.selected_textbox = box
        self._refresh_all(keep_row=page_index)
        self._text_bar.show()
        self.statusBar().showMessage(t("edit.done_hint"), 7000)

    def _on_point_picked(self, page_index: int, px: float, py: float) -> None:
        text, ok = self._ask_text_content(t("text.new_title"), "")
        if not ok or not text.strip():
            self.statusBar().clearMessage()
            return
        size = self._last_font_size
        # กล่องเริ่มต้น: กว้างพอสมควร สูงตามขนาดฟอนต์ (ปรับภายหลังได้)
        page = self.doc.doc.load_page(page_index)
        width = min(page.rect.width - px - 10, max(200, len(text) * size * 0.6))
        rect = fitz.Rect(px, py, px + width, py + size * 1.8)
        box = self.doc.add_textbox(page_index, rect, text, font_size=size, color=self._last_color)
        self.viewer.selected_textbox = box
        self._refresh_all(keep_row=page_index)
        self._text_bar.show()
        self.statusBar().showMessage(t("text.added"), 7000)

    def _ask_text_content(self, title: str, initial: str) -> tuple[str, bool]:
        """กล่องกรอกข้อความ (หลายบรรทัดได้) + ขนาดฟอนต์"""
        from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                                       QLabel as QLbl, QPlainTextEdit, QVBoxLayout)

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(420, 240)
        layout = QVBoxLayout(dialog)

        editor = QPlainTextEdit(initial)
        editor.setPlaceholderText(t("text.placeholder_input"))
        layout.addWidget(editor)

        row = QLbl(t("text.font_size"))
        layout.addWidget(row)
        size_box = QComboBox()
        sizes = ["4", "6", "8", "10", "12", "14", "16", "18", "20", "24", "28", "36", "48"]
        size_box.addItems(sizes)
        size_box.setEditable(True)
        size_box.setCurrentText(str(int(self._last_font_size)))
        layout.addWidget(size_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        editor.setFocus()

        if dialog.exec() != QDialog.Accepted:
            return "", False
        try:
            self._last_font_size = max(4.0, float(size_box.currentText()))
        except ValueError:
            pass
        return editor.toPlainText(), True

    def _on_textbox_selected(self) -> None:
        self._text_bar.show()
        self.viewer.refresh()
        self.statusBar().showMessage(t("text.selected_hint"), 6000)

    def edit_selected_textbox(self) -> None:
        """แก้คำในกล่องข้อความที่เลือก"""
        box = self.viewer.selected_textbox
        if box is None:
            return
        text, ok = self._ask_text_content(t("text.edit_title"), box.text)
        if not ok:
            return
        self.doc.update_textbox_content(box, text=text, font_size=self._last_font_size)
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

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()


def main() -> None:
    i18n.load_language()   # ต้องโหลดก่อนสร้างหน้าต่าง ไม่งั้นเมนูเป็นภาษาเริ่มต้น

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    icon = app_icon_path()
    if icon:
        app.setWindowIcon(QIcon(str(icon)))
        # บอก Windows ว่าเป็นแอปของตัวเอง ไม่งั้น taskbar จะไปใช้ไอคอนของ Python
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BallcarPDF.App")
        except Exception:
            pass  # ไม่ใช่ Windows หรือเรียกไม่ได้ ก็ข้ามไป ไม่ใช่เรื่องคอขาดบาดตาย

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
