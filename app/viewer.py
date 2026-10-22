"""วิวเออร์แสดงหน้า PDF — เลื่อนต่อเนื่องหลายหน้า (กระดาษเรียงกันแบบ Adobe) + ไฮไลต์ผลค้นหา

สถาปัตยกรรม: หน้าเอกสารทุกหน้าถูกวางเรียงในแนวตั้งบน "แคนวาส" เดียว (มีช่องว่างสีเทา
คั่นระหว่างหน้าให้เห็นเป็นกระดาษหลายแผ่น) แคนวาสสูงเท่าเอกสารทั้งเล่ม แต่ render จริง
เฉพาะหน้าที่มองเห็นตอนนั้น (lazy paint) เพื่อไม่ให้กินหน่วยความจำเมื่อไฟล์หลายร้อยหน้า

พิกัด: ทุกอย่างทำงานบน "พิกัดแคนวาส" (canvas coords) แล้วแปลงเป็นพิกัดบนหน้าใดหน้าหนึ่ง
ด้วย _page_at() (รู้ว่าคลิกโดนหน้าไหน) — เครื่องมือแก้ไขทั้งหมด (ลายเซ็น/ข้อความ/
ไฮไลต์/ยางลบ/มาร์กอัป) จึงทำงานกับหน้าที่เมาส์ชี้อยู่จริง
"""
from __future__ import annotations

import fitz
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QImage, QMouseEvent,
                           QPainter, QPen, QPixmap)
from PySide6.QtWidgets import QLabel, QScrollArea, QWidget

from .pdfops import (PdfDocument, SearchHit, TextBox, find_thai_font,
                     merge_line_rects, page_words, render_textbox_bitmap,
                     select_words_between)

_TEXT_FONT_FAMILY: str | None = None

GAP = 16            # ช่องว่างสีเทาระหว่างหน้า (พิกเซลบนจอ)
SHADOW = 4          # ระยะเงาใต้กระดาษ


def text_font_family() -> str:
    """ฟอนต์ที่ใช้แสดงข้อความบนจอ (โหลดฟอนต์ไทยเข้ามาให้ตรงกับตอนบันทึกลงไฟล์)"""
    global _TEXT_FONT_FAMILY
    if _TEXT_FONT_FAMILY is None:
        path = find_thai_font()
        family = ""
        if path:
            fid = QFontDatabase.addApplicationFont(path)
            families = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            family = families[0] if families else ""
        _TEXT_FONT_FAMILY = family or "Tahoma"
    return _TEXT_FONT_FAMILY


def render_textbox_pixmap(box: TextBox, zoom: float, overflow: bool = True) -> QPixmap:
    """วาดข้อความในกล่องลงบน QPixmap โปร่งใส (ใช้ทั้งบนจอและตอนลากย้าย)"""
    if not box.text.strip():
        pixmap = QPixmap(max(1, int(box.rect.width * zoom)),
                         max(1, int(box.rect.height * zoom)))
        pixmap.fill(Qt.transparent)
        return pixmap
    return QPixmap.fromImage(pixmap_to_qimage(render_textbox_bitmap(box, zoom, overflow)))


def _paint_annotation(painter: QPainter, kind: str, qpts: list, color, width: float) -> None:
    """วาดรูปมาร์กอัปลงบน painter (พิกัดที่ส่งมาเป็นพิกัดบนแคนวาสแล้ว)"""
    if not qpts:
        return
    from .pdfops import arrowhead_points
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    r, g, b = color
    pen = QPen(QColor(int(r * 255), int(g * 255), int(b * 255)), max(1.0, width))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    if kind == "draw":
        for i in range(len(qpts) - 1):
            painter.drawLine(qpts[i], qpts[i + 1])
    else:
        a, b2 = qpts[0], qpts[-1]
        if kind == "rect":
            painter.drawRect(QRect(a, b2).normalized())
        elif kind == "circle":
            painter.drawEllipse(QRect(a, b2).normalized())
        elif kind in ("line", "arrow"):
            painter.drawLine(a, b2)
            if kind == "arrow":
                left, right = arrowhead_points((a.x(), a.y()), (b2.x(), b2.y()), width)
                painter.drawLine(b2, QPoint(int(left[0]), int(left[1])))
                painter.drawLine(b2, QPoint(int(right[0]), int(right[1])))
    painter.restore()


ZOOM_MIN, ZOOM_MAX = 0.25, 6.0
HANDLE = 10  # ขนาดจุดจับมุมสำหรับย่อ/ขยาย (พิกเซลบนจอ)
MIN_SIZE = 24


class PlacementOverlay(QLabel):
    """ตัวอย่างรูปที่ลากย้าย/ย่อขยายได้ ก่อนกดยืนยันวางลงไฟล์จริง"""

    committed = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget, image_path: str) -> None:
        super().__init__(parent)
        self.source = QPixmap(image_path)
        self.setScaledContents(True)
        self.setPixmap(self.source)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._mode: str | None = None       # move / nw / ne / sw / se
        self._grab: QPoint | None = None
        self._start_geo: QRect | None = None
        self.setToolTip("ลากตรงกลางเพื่อย้าย · ลากมุมเพื่อย่อ/ขยาย\nEnter = ยืนยัน · Esc = ยกเลิก")

    def _zone(self, pos: QPoint) -> str:
        near_left = pos.x() <= HANDLE
        near_right = pos.x() >= self.width() - HANDLE
        near_top = pos.y() <= HANDLE
        near_bottom = pos.y() >= self.height() - HANDLE
        if near_top and near_left:
            return "nw"
        if near_top and near_right:
            return "ne"
        if near_bottom and near_left:
            return "sw"
        if near_bottom and near_right:
            return "se"
        return "move"

    CURSORS = {
        "nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor,
        "ne": Qt.SizeBDiagCursor, "sw": Qt.SizeBDiagCursor,
        "move": Qt.SizeAllCursor,
    }

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._mode = self._zone(event.pos())
            self._grab = event.globalPosition().toPoint()
            self._start_geo = self.geometry()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._mode is None:
            self.setCursor(self.CURSORS[self._zone(event.pos())])
            return

        delta = event.globalPosition().toPoint() - self._grab
        geo = QRect(self._start_geo)

        if self._mode == "move":
            geo.translate(delta)
        else:
            if "n" in self._mode:
                geo.setTop(min(geo.top() + delta.y(), geo.bottom() - MIN_SIZE))
            if "s" in self._mode:
                geo.setBottom(max(geo.bottom() + delta.y(), geo.top() + MIN_SIZE))
            if "w" in self._mode:
                geo.setLeft(min(geo.left() + delta.x(), geo.right() - MIN_SIZE))
            if "e" in self._mode:
                geo.setRight(max(geo.right() + delta.x(), geo.left() + MIN_SIZE))

        self.setGeometry(geo)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._mode = None
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        self.committed.emit()
        event.accept()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.blue, 1, Qt.DashLine))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.setPen(Qt.NoPen)
        painter.setBrush(Qt.blue)
        for x in (0, self.width() - HANDLE):
            for y in (0, self.height() - HANDLE):
                painter.drawRect(x, y, HANDLE, HANDLE)
        painter.end()


def pixmap_to_qimage(pix: fitz.Pixmap) -> QImage:
    fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
    return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()


class _Canvas(QWidget):
    """พื้นที่วาดหน้าเอกสารทั้งเล่ม (สูงเท่าเล่มจริง แต่ render เฉพาะหน้าที่มองเห็น)"""

    def __init__(self, viewer: "PageViewer") -> None:
        super().__init__()
        self.v = viewer
        self.setMouseTracking(True)
        self.setStyleSheet("background:#525659;")

    def paintEvent(self, event) -> None:
        self.v._paint(self, event)

    # ส่งต่อ event ให้ตัว PageViewer จัดการ (พิกัดบนแคนวาสอยู่แล้ว)
    def mousePressEvent(self, e) -> None:
        self.v._dispatch_press(e.position().toPoint(), e.button())

    def mouseMoveEvent(self, e) -> None:
        self.v._dispatch_move(e.position().toPoint())

    def mouseReleaseEvent(self, e) -> None:
        self.v._dispatch_release(e.position().toPoint(), e.button())

    def mouseDoubleClickEvent(self, e) -> None:
        self.v._dispatch_double(e.position().toPoint(), e.button())

    def contextMenuEvent(self, e) -> None:
        self.v.contextRequested.emit(self.mapTo(self.v, e.pos()))


class PageViewer(QScrollArea):
    stampSelected = Signal()
    stampEditRequested = Signal()
    textboxSelected = Signal()
    textboxEditRequested = Signal()
    pointPicked = Signal(int, float, float)
    editPointPicked = Signal(int, float, float)
    rectDragged = Signal(int, object)
    eraseDragged = Signal(int, object)
    annotDrawn = Signal(int, object)
    textSelected = Signal(str, int, object)  # ลากเลือกข้อความเสร็จ (ข้อความ, page, กรอบสุดท้าย)
    selectionCleared = Signal()              # ยกเลิกการเลือกข้อความ
    pageFlip = Signal(int, bool)             # (เก็บไว้เพื่อความเข้ากันได้ — ไม่ใช้แล้ว)
    pageChanged = Signal(int)                # หน้าที่มองเห็นเปลี่ยน (เลื่อน scroll)
    contextRequested = Signal(QPoint)        # คลิกขวา (พิกัดเทียบ viewer)

    def __init__(self) -> None:
        super().__init__()
        self._label = _Canvas(self)          # ใช้ชื่อ _label เดิมเพื่อความเข้ากันได้
        self.setWidget(self._label)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.doc: PdfDocument | None = None
        self.index = 0
        self.zoom = 1.0
        self.highlights: list[SearchHit] = []

        self._geoms: list[QRect] = []        # กรอบแต่ละหน้าบนแคนวาส
        self._cache: dict[tuple, QPixmap] = {}  # แคชภาพหน้า (i, zoomkey) -> pixmap ฐาน

        self.overlay: PlacementOverlay | None = None
        self.selected_stamp = None
        self._editing_stamp = None
        self.selected_textbox = None
        self._editing_textbox = None
        self._stamp_cache: dict[str, QPixmap] = {}
        self._picking_point = False
        self.selected_eraser = None
        self._erasing = False
        self._highlighting = False
        self._drag_page = -1                 # หน้าที่กำลังลากกรอบ (ไฮไลต์/ยางลบ)
        self._drag_start: QPoint | None = None   # พิกเซลบนหน้า (เทียบมุมบนซ้ายหน้านั้น)
        self._drag_now: QPoint | None = None
        self._annotating = False
        self._annot_tool = "draw"
        self._annot_color = (0.9, 0.1, 0.1)
        self._annot_width = 2.0
        self._annot_page = -1
        self._annot_points: list = []        # พิกัดบนหน้า (หน่วยจุด PDF)
        # เลือกข้อความด้วยการลาก (โหมดปกติ ไม่ต้องเข้าโหมดพิเศษ)
        self._words_cache: dict[int, list] = {}
        self._sel_page = -1
        self._sel_from: tuple | None = None   # จุดเริ่มลาก (พิกัดบนหน้า)
        self._sel_rects: list = []            # แถบไฮไลต์ที่เลือกอยู่
        self._sel_text = ""
        self._selecting = False

        self.verticalScrollBar().valueChanged.connect(self._sync_current_page)

    # ---------- layout / พิกัด ----------

    def _page_size(self, i: int) -> tuple[float, float]:
        """ขนาดหน้าบนจอ — ต้องตรงกับภาพที่ render_page() คืนมาเป๊ะ

        page.rect ของ PyMuPDF สลับกว้าง/สูงให้ตามมุมหมุนอยู่แล้ว (หน้า 400x600 หมุน 90
        จะได้ 600x400) ห้ามสลับซ้ำเอง ไม่งั้นหน้าที่ถูกหมุน (ไฟล์สแกน) จะได้กรอบผิดด้าน
        แล้วภาพจริงล้นไปทับหน้าถัดไป
        """
        r = self.doc.doc.load_page(i).rect
        return r.width * self.zoom, r.height * self.zoom

    def _relayout(self) -> None:
        """คำนวณตำแหน่งแต่ละหน้าบนแคนวาส + ตั้งขนาดแคนวาส"""
        self._geoms = []
        vp_w = self.viewport().width()
        vp_h = self.viewport().height()
        if not self.doc or not self.doc.page_count:
            self._label.setFixedSize(max(vp_w, 1), max(vp_h, 1))
            return
        sizes = [self._page_size(i) for i in range(self.doc.page_count)]
        strip_w = max((w for w, _ in sizes), default=vp_w)
        canvas_w = max(vp_w, int(strip_w) + 2 * SHADOW)
        y = SHADOW
        for (w, h) in sizes:
            x = (canvas_w - int(w)) // 2
            self._geoms.append(QRect(x, int(y), int(w), int(h)))
            y += h + GAP
        strip_h = y - GAP + SHADOW
        canvas_h = max(vp_h, int(strip_h))
        self._label.setFixedSize(canvas_w, canvas_h)

    def _ensure_layout(self) -> None:
        """กัน layout ค้างของเก่า — ถ้าจำนวนหน้าเปลี่ยน (แทรก/ลบ) ให้คำนวณใหม่ทันที

        จำเป็นเพราะ _refresh_all() สร้างภาพย่อก่อน ซึ่งจะเรียก show_page() กลับเข้ามา
        ตั้งแต่ตอนที่ยังไม่ได้ relayout — ถ้าไม่กันไว้จะอ่าน _geoms เกินขอบ (IndexError)
        แล้ววิวเออร์ค้างเป็นจอว่าง
        """
        want = self.doc.page_count if self.doc else 0
        if len(self._geoms) != want:
            self._relayout()

    def _page_offset(self) -> QPoint:
        """มุมบนซ้ายของหน้าปัจจุบันบนแคนวาส (เพื่อความเข้ากันได้กับโค้ด/เทสต์เดิม)"""
        if self._geoms and 0 <= self.index < len(self._geoms):
            return self._geoms[self.index].topLeft()
        return QPoint(0, 0)

    def _to_page_px(self, pos: QPoint) -> QPoint:
        """พิกัดเมาส์ (เทียบ viewer) -> พิกเซลบนหน้าปัจจุบัน (เทียบมุมบนซ้ายหน้านั้น)"""
        canvas = self._label.mapFrom(self, pos)
        off = self._page_offset()
        return QPoint(canvas.x() - off.x(), canvas.y() - off.y())

    def _page_at(self, canvas_pt: QPoint) -> tuple[int, float, float]:
        """พิกัดบนแคนวาส -> (index หน้า, x, y บนหน้าเป็นหน่วยจุด PDF)"""
        self._ensure_layout()
        if not self._geoms:
            return (self.index, 0.0, 0.0)
        y = canvas_pt.y()
        idx = len(self._geoms) - 1
        for i, g in enumerate(self._geoms):
            if y < g.bottom() + GAP // 2:
                idx = i
                break
        g = self._geoms[idx]
        return (idx, (canvas_pt.x() - g.x()) / self.zoom, (canvas_pt.y() - g.y()) / self.zoom)

    def _current_page(self) -> int:
        """หน้าที่อยู่บนสุดของพื้นที่มองเห็นตอนนี้"""
        self._ensure_layout()
        if not self._geoms:
            return 0
        top = self.verticalScrollBar().value()
        for i, g in enumerate(self._geoms):
            if g.bottom() >= top + 4:
                return i
        return len(self._geoms) - 1

    def _sync_current_page(self) -> None:
        new = self._current_page()
        if new != self.index:
            self.index = new
            self.pageChanged.emit(new)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()
        self._label.update()

    # ---------- วาง/แก้ไขรูป (overlay) ----------

    @property
    def placing(self) -> bool:
        return self.overlay is not None

    def _viewport_center_canvas(self) -> QPoint:
        return QPoint(self.horizontalScrollBar().value() + self.viewport().width() // 2,
                      self.verticalScrollBar().value() + self.viewport().height() // 2)

    def start_placing(self, image_path: str) -> None:
        """แสดงตัวอย่างรูปกลางพื้นที่มองเห็น ให้ผู้ใช้ลากย้าย/ย่อขยายก่อนยืนยัน"""
        self.cancel_placing()
        overlay = PlacementOverlay(self._label, image_path)
        center = self._viewport_center_canvas()
        idx, _, _ = self._page_at(center)
        self.index = idx
        g = self._geoms[idx] if self._geoms else QRect(0, 0, self.width(), self.height())
        width = max(MIN_SIZE * 2, g.width() // 3)
        ratio = overlay.source.height() / overlay.source.width() if overlay.source.width() else 0.4
        height = max(MIN_SIZE, int(width * ratio))
        overlay.setGeometry(center.x() - width // 2, center.y() - height // 2, width, height)
        overlay.show()
        overlay.raise_()
        self.overlay = overlay

    def cancel_placing(self) -> None:
        if self.overlay is not None:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None
        self._editing_stamp = None
        self._editing_textbox = None

    def placement_rect(self) -> fitz.Rect | None:
        """กรอบที่ผู้ใช้ปรับไว้ แปลงเป็นพิกัดบนหน้า PDF (ของหน้าปัจจุบัน)"""
        self._ensure_layout()
        if self.overlay is None or not (0 <= self.index < len(self._geoms)):
            return None
        geo = self.overlay.geometry()
        z = self.zoom
        g = self._geoms[self.index]
        x0, y0 = geo.x() - g.x(), geo.y() - g.y()
        return fitz.Rect(x0 / z, y0 / z, (x0 + geo.width()) / z, (y0 + geo.height()) / z)

    def start_editing(self, stamp) -> None:
        self._ensure_layout()
        if not (0 <= stamp.page < len(self._geoms)):
            return
        self.index = stamp.page
        self.start_placing(stamp.image_path)
        self._editing_stamp = stamp
        r = stamp.rect
        g = self._geoms[stamp.page]
        self.overlay.setGeometry(
            int(r.x0 * self.zoom) + g.x(), int(r.y0 * self.zoom) + g.y(),
            max(MIN_SIZE, int(r.width * self.zoom)), max(MIN_SIZE, int(r.height * self.zoom)),
        )
        self._label.update()

    def start_editing_textbox(self, box) -> None:
        self._ensure_layout()
        if not (0 <= box.page < len(self._geoms)):
            return
        self.cancel_placing()
        self.index = box.page
        overlay = PlacementOverlay(self._label, "")
        overlay.source = render_textbox_pixmap(box, self.zoom, overflow=False)
        overlay.setPixmap(overlay.source)
        r = box.rect
        g = self._geoms[box.page]
        overlay.setGeometry(
            int(r.x0 * self.zoom) + g.x(), int(r.y0 * self.zoom) + g.y(),
            max(MIN_SIZE, int(r.width * self.zoom)), max(MIN_SIZE, int(r.height * self.zoom)),
        )
        overlay.show()
        overlay.raise_()
        self.overlay = overlay
        self._editing_textbox = box
        self._label.update()

    @property
    def editing_stamp(self):
        return self._editing_stamp

    @property
    def editing_textbox(self):
        return self._editing_textbox

    def _stamp_pixmap(self, path: str) -> QPixmap:
        if path not in self._stamp_cache:
            self._stamp_cache[path] = QPixmap(path)
        return self._stamp_cache[path]

    # ---------- เอกสาร / นำทาง ----------

    def set_document(self, doc: PdfDocument | None) -> None:
        self.doc = doc
        self.index = 0
        self.highlights = []
        self.clear_selection(quiet=True)
        self._cache.clear()
        self._words_cache.clear()
        self._relayout()
        self.verticalScrollBar().setValue(0)
        self._label.update()

    def show_page(self, index: int) -> None:
        if not self.doc or not (0 <= index < self.doc.page_count):
            return
        self._ensure_layout()
        if index < len(self._geoms):
            self.index = index
            self.verticalScrollBar().setValue(max(0, self._geoms[index].y() - SHADOW))
            self._label.update()

    def set_zoom(self, zoom: float) -> None:
        # จำหน้าปัจจุบัน + ตำแหน่งกรอบตัวอย่างเป็นพิกัดบนหน้า แล้ววางกลับหลังเปลี่ยนซูม
        anchor = self.index
        page_rect = self.placement_rect() if self.overlay is not None else None
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
        self._cache.clear()
        self._relayout()
        if self._geoms and 0 <= anchor < len(self._geoms):
            self.verticalScrollBar().setValue(max(0, self._geoms[anchor].y() - SHADOW))
        if self.overlay is not None and page_rect is not None and self._geoms:
            g = self._geoms[self.index]
            self.overlay.setGeometry(
                int(page_rect.x0 * self.zoom) + g.x(),
                int(page_rect.y0 * self.zoom) + g.y(),
                max(MIN_SIZE, int(page_rect.width * self.zoom)),
                max(MIN_SIZE, int(page_rect.height * self.zoom)),
            )
        self._label.update()

    def fit_width(self) -> None:
        if not self.doc or not self.doc.page_count:
            return
        page_width = self.doc.doc.load_page(self.index).rect.width
        if page_width > 0:
            self.set_zoom((self.viewport().width() - 2 * SHADOW - 24) / page_width)

    def refresh(self) -> None:
        """เรียกหลังแก้เอกสาร — คำนวณ layout ใหม่ + ล้างแคชภาพ + วาดใหม่"""
        if self.doc and self.doc.page_count:
            self.index = min(self.index, self.doc.page_count - 1)
        self._cache.clear()
        self._words_cache.clear()      # เนื้อหาอาจเปลี่ยน ต้องอ่านคำใหม่
        self._relayout()
        self._label.update()

    # ---------- render หน้า (lazy + แคช) ----------

    def _page_pixmap(self, i: int) -> QPixmap:
        """ภาพหน้า i ที่ซูมปัจจุบัน — เรนเดอร์ตามความละเอียดจอจริงเพื่อความคมชัด

        จอที่ตั้งสเกล 125%/150% (โน้ตบุ๊กส่วนใหญ่) 1 พิกเซลตรรกะ = 1.25/1.5 พิกเซลจริง
        ถ้าเรนเดอร์แค่ขนาดตรรกะ Windows จะขยายภาพให้เอง -> ตัวหนังสือเบลอ
        จึงเรนเดอร์ที่ zoom * devicePixelRatio แล้วบอก Qt ว่าเป็นภาพความละเอียดสูง
        """
        dpr = max(1.0, float(self._label.devicePixelRatioF()))
        key = (i, round(self.zoom, 4), round(dpr, 3))
        pm = self._cache.get(key)
        if pm is None:
            pm = QPixmap.fromImage(
                pixmap_to_qimage(self.doc.render_page(i, self.zoom * dpr)))
            pm.setDevicePixelRatio(dpr)      # Qt จะย่อกลับตอนวาด ได้ขนาดเท่าเดิมแต่คมกว่า
            if len(self._cache) > 12:        # กันแคชโตเกิน (เก็บพอสำหรับหน้าที่มองเห็น)
                self._cache.clear()
            self._cache[key] = pm
        return pm

    def _paint(self, canvas: _Canvas, event) -> None:
        painter = QPainter(canvas)
        painter.fillRect(event.rect(), QColor(0x52, 0x56, 0x59))
        if not self.doc or not self.doc.page_count:
            from .i18n import t
            painter.setPen(QColor(0xbb, 0xbb, 0xbb))
            f = painter.font(); f.setPixelSize(16); painter.setFont(f)
            painter.drawText(canvas.rect(), Qt.AlignCenter, t("viewer.no_file"))
            painter.end()
            return
        self._ensure_layout()          # กันวาดด้วย layout ค้างของเก่าหลังแทรก/ลบหน้า
        vis = event.rect()
        for i, g in enumerate(self._geoms):
            if not g.intersects(vis):
                continue
            painter.fillRect(QRect(g.x() + SHADOW, g.y() + SHADOW, g.width(), g.height()),
                             QColor(0, 0, 0, 45))                     # เงาใต้กระดาษ
            painter.drawPixmap(g.topLeft(), self._page_pixmap(i))
            painter.setPen(QColor(0, 0, 0, 60)); painter.setBrush(Qt.NoBrush)
            painter.drawRect(g.adjusted(0, 0, -1, -1))                # เส้นขอบกระดาษบางๆ
            self._paint_overlays(painter, i, g)
        painter.end()

    def _paint_overlays(self, painter: QPainter, i: int, g: QRect) -> None:
        """วาดของที่ยังลอยอยู่ (ไฮไลต์/ยางลบ/ลายเซ็น/ข้อความ/ลายน้ำ/มาร์กอัป) ของหน้า i"""
        z = self.zoom
        ox, oy = g.x(), g.y()

        # แถบข้อความที่กำลังเลือกอยู่ (ลากเลือกเพื่อคัดลอก)
        if self._sel_page == i and self._sel_rects:
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(51, 120, 255, 90))
            for r in self._sel_rects:
                painter.drawRect(int(ox + r.x0 * z), int(oy + r.y0 * z),
                                 max(1, int(r.width * z)), max(1, int(r.height * z)))
            painter.restore()

        # ไฮไลต์ผลค้นหา
        page_hits = [h for h in self.highlights if h.page == i]
        if page_hits:
            page = self.doc.doc.load_page(i)
            rotation = page.rotation
            painter.save()
            painter.setBrush(Qt.yellow); painter.setPen(Qt.NoPen); painter.setOpacity(0.35)
            for hit in page_hits:
                r = hit.rect * page.rotation_matrix if rotation else hit.rect
                painter.drawRect(int(ox + r.x0 * z), int(oy + r.y0 * z),
                                 int(r.width * z), int(r.height * z))
            painter.restore()

        # ยางลบ/แผ่นปิดทับ
        for eraser in self.doc.erasers_on(i):
            r = eraser.rect
            box = QRect(int(ox + r.x0 * z), int(oy + r.y0 * z),
                        int(r.width * z), int(r.height * z))
            er, eg, eb = eraser.color
            painter.fillRect(box, QColor(int(er * 255), int(eg * 255), int(eb * 255)))
            if eraser is self.selected_eraser:
                painter.setPen(QPen(Qt.blue, 1, Qt.DashLine)); painter.setBrush(Qt.NoBrush)
                painter.drawRect(box.adjusted(0, 0, -1, -1))

        # ลายเซ็น
        for stamp in self.doc.stamps_on(i):
            if stamp is self._editing_stamp:
                continue
            image = self._stamp_pixmap(stamp.image_path)
            if image.isNull():
                continue
            r = stamp.rect
            box = QRect(int(ox + r.x0 * z), int(oy + r.y0 * z),
                        int(r.width * z), int(r.height * z))
            painter.save()
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            fitted = image.scaled(box.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(box.topLeft(), fitted)
            if stamp is self.selected_stamp:
                painter.setPen(QPen(Qt.blue, 1, Qt.DashLine)); painter.setBrush(Qt.NoBrush)
                painter.drawRect(box.adjusted(0, 0, -1, -1))
            painter.restore()

        # กล่องข้อความ
        for tb in self.doc.textboxes_on(i):
            if tb is self._editing_textbox:
                continue
            r = tb.rect
            box = QRect(int(ox + r.x0 * z), int(oy + r.y0 * z),
                        int(r.width * z), int(r.height * z))
            painter.drawPixmap(box.topLeft(), render_textbox_pixmap(tb, z))
            if tb is self.selected_textbox:
                painter.save()
                painter.setPen(QPen(Qt.blue, 1, Qt.DashLine)); painter.setBrush(Qt.NoBrush)
                painter.drawRect(box.adjusted(0, 0, -1, -1))
                painter.restore()

        # ลายน้ำ
        geo = self.doc.watermark_geometry(i)
        if geo is not None:
            wm = self.doc.watermark
            cx, cy, size, width = geo
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setOpacity(wm.opacity)
            r, g2, b = wm.color
            painter.setPen(QColor(int(r * 255), int(g2 * 255), int(b * 255)))
            font = QFont(text_font_family()); font.setPixelSize(max(1, int(size * z)))
            painter.setFont(font)
            painter.translate(ox + cx * z, oy + cy * z)
            painter.rotate(-wm.angle)
            painter.drawText(int(-width * z / 2), int(size * 0.35 * z), wm.text)
            painter.restore()

        # มาร์กอัปที่ยังลอยอยู่
        for a in self.doc.annotations_on(i):
            qpts = [QPoint(int(ox + x * z), int(oy + y * z)) for x, y in a.points]
            _paint_annotation(painter, a.kind, qpts, a.color, a.width * z)

        # ตัวอย่างขณะกำลังวาดมาร์กอัป (บนหน้าที่กำลังวาด)
        if self._annotating and self._annot_page == i and len(self._annot_points) >= 2:
            qpts = [QPoint(int(ox + x * z), int(oy + y * z)) for x, y in self._annot_points]
            _paint_annotation(painter, self._annot_tool, qpts,
                              self._annot_color, self._annot_width * z)

        # กรอบตัวอย่างขณะลากไฮไลต์/ยางลบ (บนหน้าที่กำลังลาก)
        if (self._highlighting or self._erasing) and self._drag_page == i \
                and self._drag_start is not None and self._drag_now is not None:
            painter.save()
            if self._erasing:
                painter.setPen(QPen(QColor(200, 60, 60), 1, Qt.DashLine))
                painter.setBrush(QColor(255, 255, 255, 200))
            else:
                painter.setPen(QPen(QColor(220, 180, 0), 1, Qt.DashLine))
                painter.setBrush(QColor(255, 235, 60, 70))
            a = QPoint(ox + self._drag_start.x(), oy + self._drag_start.y())
            b = QPoint(ox + self._drag_now.x(), oy + self._drag_now.y())
            painter.drawRect(QRect(a, b).normalized())
            painter.restore()

    # ---------- โหมดต่างๆ ----------

    def start_point_pick(self, mode: str = "add") -> None:
        self._picking_point = True
        self._pick_mode = mode
        self._label.setCursor(Qt.IBeamCursor)

    def stop_point_pick(self) -> None:
        self._picking_point = False
        self._label.unsetCursor()

    def start_highlight_drag(self) -> None:
        self._highlighting = True
        self._drag_start = None
        self._label.setCursor(Qt.CrossCursor)

    def stop_highlight_drag(self) -> None:
        self._highlighting = False
        self._drag_start = None
        self._drag_now = None
        self._label.unsetCursor()
        self._label.update()

    def start_erase_drag(self) -> None:
        self._erasing = True
        self._drag_start = None
        self._drag_now = None
        self._label.setCursor(Qt.CrossCursor)

    def stop_erase_drag(self) -> None:
        self._erasing = False
        self._drag_start = None
        self._drag_now = None
        self._label.unsetCursor()
        self._label.update()

    def start_annotate(self, tool: str, color, width: float) -> None:
        self._annotating = True
        self._annot_tool = tool
        self._annot_color = color
        self._annot_width = width
        self._annot_points = []
        self._annot_page = -1
        self._label.setCursor(Qt.CrossCursor)

    def set_annot_style(self, color, width: float) -> None:
        self._annot_color = color
        self._annot_width = width

    def set_annot_tool(self, tool: str) -> None:
        self._annot_tool = tool

    def stop_annotate(self) -> None:
        self._annotating = False
        self._annot_points = []
        self._annot_page = -1
        self._label.unsetCursor()
        self._label.update()

    # ---------- เลือกข้อความบนหน้า (ลากเลือกได้เลย ไม่ต้องเข้าโหมด) ----------

    @property
    def selected_text(self) -> str:
        return self._sel_text

    def _words(self, index: int) -> list:
        if index not in self._words_cache:
            self._words_cache[index] = page_words(self.doc.doc.load_page(index))
        return self._words_cache[index]

    def clear_selection(self, quiet: bool = False) -> None:
        if not self._sel_rects and not self._sel_text:
            return
        self._sel_rects = []
        self._sel_text = ""
        self._sel_page = -1
        self._label.update()
        if not quiet:
            self.selectionCleared.emit()

    def select_all_on_page(self, index: int | None = None) -> str:
        """เลือกข้อความทั้งหน้า (Ctrl+A)"""
        if not self.doc:
            return ""
        index = self.index if index is None else index
        words = self._words(index)
        if not words:
            return ""
        rects, text = select_words_between(
            words, (words[0][0], words[0][1]), (words[-1][2], words[-1][3]))
        self._sel_page = index
        self._sel_rects = merge_line_rects(rects)
        self._sel_text = text
        self._label.update()
        if text and self._sel_rects:
            self.textSelected.emit(text, index, self._sel_rects[-1])
        return text

    def page_point_to_viewer(self, page: int, x: float, y: float) -> QPoint:
        """พิกัดบนหน้า -> พิกัดในวิวเออร์ (ใช้วางแถบลอยให้ตรงกับข้อความที่เลือก)"""
        self._ensure_layout()
        if not (0 <= page < len(self._geoms)):
            return QPoint(0, 0)
        g = self._geoms[page]
        return self._label.mapTo(
            self, QPoint(int(g.x() + x * self.zoom), int(g.y() + y * self.zoom)))

    def _update_selection(self, page: int, start, end) -> None:
        rects, text = select_words_between(self._words(page), start, end)
        self._sel_page = page
        self._sel_rects = merge_line_rects(rects)
        self._sel_text = text
        self._label.update()

    def _busy(self) -> bool:
        return (self.placing or self._picking_point or self._highlighting
                or self._erasing or self._annotating)

    # ---------- จัดการเมาส์ (พิกัดบนแคนวาส) ----------

    def _dispatch_press(self, canvas_pt: QPoint, button) -> None:
        if self.placing or not self.doc or button != Qt.LeftButton:
            return
        idx, px, py = self._page_at(canvas_pt)
        self.index = idx
        g = self._geoms[idx]
        local = QPoint(canvas_pt.x() - g.x(), canvas_pt.y() - g.y())   # พิกเซลบนหน้า

        if self._annotating:
            self._annot_page = idx
            self._annot_points = [(px, py)]
            return
        if self._highlighting or self._erasing:
            self._drag_page = idx
            self._drag_start = local
            self._drag_now = local
            return

        point = fitz.Point(px, py)
        if getattr(self, "_picking_point", False):
            mode = getattr(self, "_pick_mode", "add")
            self.stop_point_pick()
            if mode == "edit":
                self.editPointPicked.emit(idx, px, py)
            else:
                self.pointPicked.emit(idx, px, py)
            return

        tb = self.doc.textbox_at(idx, point)
        stamp = self.doc.stamp_at(idx, point)
        if tb is not None:
            self.clear_selection()
            self.selected_textbox = tb
            self.selected_stamp = None
            self.textboxSelected.emit()
        elif stamp is not None:
            self.clear_selection()
            self.selected_stamp = stamp
            self.selected_textbox = None
            self.stampSelected.emit()
        else:
            changed = self.selected_stamp is not None or self.selected_textbox is not None
            self.selected_stamp = None
            self.selected_textbox = None
            # คลิกที่ว่าง = เริ่มลากเลือกข้อความ (พฤติกรรมปกติแบบโปรแกรมอ่าน PDF ทั่วไป)
            self.clear_selection()
            self._selecting = True
            self._sel_from = (px, py)
            self._sel_page = idx
            if changed:
                self._label.update()

    def _dispatch_move(self, canvas_pt: QPoint) -> None:
        if self._annotating and self._annot_points and self._annot_page >= 0:
            g = self._geoms[self._annot_page]
            pt = ((canvas_pt.x() - g.x()) / self.zoom, (canvas_pt.y() - g.y()) / self.zoom)
            if self._annot_tool == "draw":
                self._annot_points.append(pt)
            else:
                self._annot_points = [self._annot_points[0], pt]
            self._label.update()
            return
        if (self._highlighting or self._erasing) and self._drag_start is not None:
            g = self._geoms[self._drag_page]
            self._drag_now = QPoint(canvas_pt.x() - g.x(), canvas_pt.y() - g.y())
            self._label.update()
            return
        if self._selecting and self._sel_from is not None and self._sel_page >= 0:
            g = self._geoms[self._sel_page]
            end = ((canvas_pt.x() - g.x()) / self.zoom, (canvas_pt.y() - g.y()) / self.zoom)
            self._update_selection(self._sel_page, self._sel_from, end)

    def _dispatch_release(self, canvas_pt: QPoint, button) -> None:
        if self._annotating and self._annot_points and self._annot_page >= 0:
            pts = list(self._annot_points)
            page = self._annot_page
            self._annot_points = []
            self._annot_page = -1
            enough = (self._annot_tool == "draw" and len(pts) >= 2) or (
                len(pts) >= 2 and (abs(pts[0][0] - pts[-1][0]) > 3
                                   or abs(pts[0][1] - pts[-1][1]) > 3))
            if enough:
                self.annotDrawn.emit(page, {"kind": self._annot_tool, "points": pts})
            else:
                self._label.update()
            return
        if (self._highlighting or self._erasing) and self._drag_start is not None:
            page = self._drag_page
            g = self._geoms[page]
            a = self._drag_start
            b = QPoint(canvas_pt.x() - g.x(), canvas_pt.y() - g.y())   # ตำแหน่งปล่อยเมาส์
            erasing = self._erasing
            self._drag_start = None
            self._drag_now = None
            z = self.zoom
            rect = fitz.Rect(min(a.x(), b.x()) / z, min(a.y(), b.y()) / z,
                             max(a.x(), b.x()) / z, max(a.y(), b.y()) / z)
            if erasing:
                self.eraseDragged.emit(page, rect)
            else:
                self.rectDragged.emit(page, rect)
            return
        if self._selecting:
            self._selecting = False
            self._sel_from = None
            if self._sel_text and self._sel_rects:
                self.textSelected.emit(self._sel_text, self._sel_page, self._sel_rects[-1])

    def _dispatch_double(self, canvas_pt: QPoint, button) -> None:
        if self.placing or not self.doc or button != Qt.LeftButton:
            return
        idx, px, py = self._page_at(canvas_pt)
        self.index = idx
        point = fitz.Point(px, py)
        tb = self.doc.textbox_at(idx, point)
        if tb is not None:
            self.selected_textbox = tb
            self.textboxEditRequested.emit()
            return
        hit = self.doc.stamp_at(idx, point)
        if hit is not None:
            self.selected_stamp = hit
            self.stampEditRequested.emit()

    # ---------- adapter: รับ event แบบเดิม (เทสต์เรียกด้วยพิกัดเทียบ viewer) ----------

    def mousePressEvent(self, event) -> None:
        self._dispatch_press(self._label.mapFrom(self, event.pos()), event.button())

    def mouseMoveEvent(self, event) -> None:
        self._dispatch_move(self._label.mapFrom(self, event.pos()))

    def mouseReleaseEvent(self, event) -> None:
        self._dispatch_release(self._label.mapFrom(self, event.pos()), event.button())

    def mouseDoubleClickEvent(self, event) -> None:
        self._dispatch_double(self._label.mapFrom(self, event.pos()), event.button())

    def wheelEvent(self, event) -> None:
        # Ctrl+ล้อเมาส์ = ซูม (คงตำแหน่งหน้าเดิม)
        if event.modifiers() & Qt.ControlModifier:
            self.set_zoom(self.zoom * (1.1 if event.angleDelta().y() > 0 else 1 / 1.1))
            event.accept()
            return
        super().wheelEvent(event)   # เลื่อนต่อเนื่องข้ามหน้าตามธรรมชาติ
