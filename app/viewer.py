"""วิวเออร์แสดงหน้า PDF + ไฮไลต์ผลค้นหา"""
from __future__ import annotations

import fitz
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea

from .pdfops import PdfDocument, SearchHit, TextBox, find_thai_font

_TEXT_FONT_FAMILY: str | None = None


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


def render_textbox_pixmap(box: TextBox, zoom: float) -> QPixmap:
    """วาดข้อความในกล่องลงบน QPixmap โปร่งใส (ใช้ทั้งบนจอและตอนลากย้าย)"""
    w = max(1, int(box.rect.width * zoom))
    h = max(1, int(box.rect.height * zoom))
    pixmap = QPixmap(w, h)
    pixmap.fill(Qt.transparent)
    if box.text.strip():
        painter = QPainter(pixmap)
        font = QFont(text_font_family())
        font.setPixelSize(max(1, int(box.font_size * zoom)))
        painter.setFont(font)
        r, g, b = box.color
        painter.setPen(QColor(int(r * 255), int(g * 255), int(b * 255)))
        painter.drawText(QRect(0, 0, w, h), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, box.text)
        painter.end()
    return pixmap

ZOOM_MIN, ZOOM_MAX = 0.25, 6.0
HANDLE = 10  # ขนาดจุดจับมุมสำหรับย่อ/ขยาย (พิกเซลบนจอ)
MIN_SIZE = 24


class PlacementOverlay(QLabel):
    """ตัวอย่างรูปที่ลากย้าย/ย่อขยายได้ ก่อนกดยืนยันวางลงไฟล์จริง"""

    committed = Signal()
    cancelled = Signal()

    def __init__(self, parent: QLabel, image_path: str) -> None:
        super().__init__(parent)
        self.source = QPixmap(image_path)
        self.setScaledContents(True)
        self.setPixmap(self.source)
        self.setMouseTracking(True)
        # ตัวแม่ (_label) ตั้งพื้นหลังสีเทาไว้ ซึ่ง stylesheet จะตกทอดมาที่ QLabel ลูกด้วย
        # ต้องล้างทิ้ง ไม่งั้นตัวอย่างลายเซ็นจะมีพื้นเทาบังเนื้อหาใต้กรอบจนจัดตำแหน่งไม่ได้
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._mode: str | None = None       # move / nw / ne / sw / se
        self._grab: QPoint | None = None
        self._start_geo: QRect | None = None
        self.setToolTip("ลากตรงกลางเพื่อย้าย · ลากมุมเพื่อย่อ/ขยาย\nEnter = ยืนยัน · Esc = ยกเลิก")

    # ---------- รู้ว่าเมาส์อยู่ตรงมุมไหน ----------

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
        # กรอบประ + จุดจับ 4 มุม ให้เห็นว่ายังไม่ถูกวางลงไฟล์
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
    # copy() เพราะ buffer ของ pixmap จะถูกปล่อยเมื่อ pix หมดอายุ
    return QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()


class PageViewer(QScrollArea):
    stampSelected = Signal()        # คลิกโดนลายเซ็นที่วางไว้
    stampEditRequested = Signal()   # ดับเบิลคลิกลายเซ็น = ขอแก้ตำแหน่ง/ขนาดเลย
    textboxSelected = Signal()      # คลิกโดนกล่องข้อความ
    textboxEditRequested = Signal() # ดับเบิลคลิกกล่องข้อความ = ขอแก้ข้อความ
    pointPicked = Signal(int, float, float)  # คลิกจุดบนหน้าตอนโหมด "เพิ่มข้อความ"
    editPointPicked = Signal(int, float, float)  # คลิกข้อความเดิมตอนโหมด "แก้ข้อความ"
    rectDragged = Signal(int, object)        # ลากกรอบเสร็จตอนโหมดไฮไลต์ (page, fitz.Rect)

    def __init__(self) -> None:
        super().__init__()
        self._label = QLabel(alignment=Qt.AlignCenter)
        self._label.setStyleSheet("background:#525659;")
        self.setWidget(self._label)
        self.setWidgetResizable(True)

        self.doc: PdfDocument | None = None
        self.index = 0
        self.zoom = 1.0
        self.highlights: list[SearchHit] = []

        self.overlay: PlacementOverlay | None = None
        self.selected_stamp = None          # ลายเซ็นที่กำลังถูกเลือกอยู่
        self._editing_stamp = None          # ลายเซ็นที่กำลังแก้ตำแหน่งผ่าน overlay
        self.selected_textbox = None        # กล่องข้อความที่กำลังถูกเลือก
        self._editing_textbox = None        # กล่องข้อความที่กำลังแก้ตำแหน่งผ่าน overlay
        self._stamp_cache: dict[str, QPixmap] = {}
        self._picking_point = False
        # โหมดลากกรอบเพื่อไฮไลต์
        self._highlighting = False
        self._drag_start: QPoint | None = None
        self._drag_now: QPoint | None = None

    def _stamp_pixmap(self, path: str) -> QPixmap:
        if path not in self._stamp_cache:
            self._stamp_cache[path] = QPixmap(path)
        return self._stamp_cache[path]

    # ---------- วางรูปแบบมีตัวอย่างให้ปรับก่อน ----------

    @property
    def placing(self) -> bool:
        return self.overlay is not None

    def start_placing(self, image_path: str) -> None:
        """แสดงตัวอย่างรูปกลางหน้าจอ ให้ผู้ใช้ลากย้าย/ย่อขยายก่อนยืนยัน"""
        self.cancel_placing()
        overlay = PlacementOverlay(self._label, image_path)

        # ขนาดเริ่มต้น: กว้าง 1 ใน 3 ของหน้า วางกลางพื้นที่ที่มองเห็น
        page_w = self._label.pixmap().width() if self._label.pixmap() else self.width()
        width = max(MIN_SIZE * 2, page_w // 3)
        ratio = overlay.source.height() / overlay.source.width() if overlay.source.width() else 0.4
        height = max(MIN_SIZE, int(width * ratio))
        cx = self.horizontalScrollBar().value() + self.viewport().width() // 2
        cy = self.verticalScrollBar().value() + self.viewport().height() // 2
        overlay.setGeometry(cx - width // 2, cy - height // 2, width, height)

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
        """กรอบที่ผู้ใช้ปรับไว้ แปลงเป็นพิกัดบนหน้า PDF"""
        if self.overlay is None:
            return None
        geo = self.overlay.geometry()
        z = self.zoom
        # QRect.right()/bottom() เป็นพิกเซลสุดท้ายแบบรวม (กว้าง 200 -> right = left+199)
        # จึงใช้ x()+width() เพื่อให้ได้ขอบจริง
        return fitz.Rect(
            geo.x() / z, geo.y() / z,
            (geo.x() + geo.width()) / z, (geo.y() + geo.height()) / z,
        )

    def set_document(self, doc: PdfDocument | None) -> None:
        self.doc = doc
        self.index = 0
        self.highlights = []
        self.refresh()

    def show_page(self, index: int) -> None:
        if self.doc and 0 <= index < self.doc.page_count:
            self.index = index
            self.refresh()

    def set_zoom(self, zoom: float) -> None:
        old = self.zoom
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, zoom))
        # ถ้ากำลังวางรูปอยู่ ต้องขยับ/ย่อกรอบตัวอย่างตามซูมด้วย ไม่งั้นตำแหน่งเพี้ยน
        if self.overlay is not None and old:
            factor = self.zoom / old
            geo = self.overlay.geometry()
            self.overlay.setGeometry(
                int(geo.left() * factor), int(geo.top() * factor),
                max(MIN_SIZE, int(geo.width() * factor)),
                max(MIN_SIZE, int(geo.height() * factor)),
            )
        self.refresh()

    def fit_width(self) -> None:
        """ปรับซูมให้หน้ากว้างพอดีกับพื้นที่แสดงผล"""
        if not self.doc or not self.doc.page_count:
            return
        page_width = self.doc.doc.load_page(self.index).rect.width
        if page_width > 0:
            self.set_zoom((self.viewport().width() - 24) / page_width)

    def refresh(self) -> None:
        if not self.doc or not self.doc.page_count:
            self._label.clear()
            from .i18n import t

            self._label.setText(t("viewer.no_file"))
            self._label.setStyleSheet("background:#525659; color:#bbb; font-size:16px;")
            return

        self.index = min(self.index, self.doc.page_count - 1)
        self._label.setStyleSheet("background:#525659;")
        pixmap = QPixmap.fromImage(pixmap_to_qimage(self.doc.render_page(self.index, self.zoom)))

        page_hits = [h for h in self.highlights if h.page == self.index]
        if page_hits:
            rotation = self.doc.doc.load_page(self.index).rotation
            painter = QPainter(pixmap)
            painter.setBrush(Qt.yellow)
            painter.setPen(Qt.NoPen)
            painter.setOpacity(0.35)
            for hit in page_hits:
                # search_for คืนพิกัดก่อนหมุน — แปลงตามมุมหมุนของหน้าก่อนวาด
                r = hit.rect * self.doc.doc.load_page(self.index).rotation_matrix if rotation else hit.rect
                painter.drawRect(
                    int(r.x0 * self.zoom), int(r.y0 * self.zoom),
                    int(r.width * self.zoom), int(r.height * self.zoom),
                )
            painter.end()

        # วาดลายเซ็นที่ยังลอยอยู่ (ยังไม่ฝังลงไฟล์) ทับลงบนภาพหน้า
        for stamp in self.doc.stamps_on(self.index):
            if stamp is self._editing_stamp:
                continue  # ตัวที่กำลังลากอยู่ แสดงผ่าน overlay แทน
            image = self._stamp_pixmap(stamp.image_path)
            if image.isNull():
                continue
            r = stamp.rect
            box = QRect(int(r.x0 * self.zoom), int(r.y0 * self.zoom),
                        int(r.width * self.zoom), int(r.height * self.zoom))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            fitted = image.scaled(box.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(box.topLeft(), fitted)
            if stamp is self.selected_stamp:
                painter.setPen(QPen(Qt.blue, 1, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(box.adjusted(0, 0, -1, -1))
            painter.end()

        # วาดกล่องข้อความที่ยังลอยอยู่
        for tb in self.doc.textboxes_on(self.index):
            if tb is self._editing_textbox:
                continue  # ตัวที่กำลังลากอยู่ แสดงผ่าน overlay แทน
            r = tb.rect
            box = QRect(int(r.x0 * self.zoom), int(r.y0 * self.zoom),
                        int(r.width * self.zoom), int(r.height * self.zoom))
            painter = QPainter(pixmap)
            painter.drawPixmap(box.topLeft(), render_textbox_pixmap(tb, self.zoom))
            if tb is self.selected_textbox:
                painter.setPen(QPen(Qt.blue, 1, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(box.adjusted(0, 0, -1, -1))
            painter.end()

        # กรอบตัวอย่างขณะลากไฮไลต์
        if self._highlighting and self._drag_start is not None and self._drag_now is not None:
            painter = QPainter(pixmap)
            painter.setPen(QPen(QColor(220, 180, 0), 1, Qt.DashLine))
            painter.setBrush(QColor(255, 235, 60, 70))
            painter.drawRect(QRect(self._drag_start, self._drag_now).normalized())
            painter.end()

        self._label.setPixmap(pixmap)
        self._label.resize(pixmap.size())

    def start_point_pick(self, mode: str = "add") -> None:
        """เข้าโหมดรอผู้ใช้คลิกจุด — mode 'add' วางข้อความใหม่, 'edit' แก้ข้อความเดิม"""
        self._picking_point = True
        self._pick_mode = mode
        self._label.setCursor(Qt.IBeamCursor)

    def stop_point_pick(self) -> None:
        self._picking_point = False
        self._label.unsetCursor()

    def start_highlight_drag(self) -> None:
        """เข้าโหมดลากกรอบคลุมข้อความเพื่อไฮไลต์"""
        self._highlighting = True
        self._drag_start = None
        self._label.setCursor(Qt.CrossCursor)

    def stop_highlight_drag(self) -> None:
        self._highlighting = False
        self._drag_start = None
        self._drag_now = None
        self._label.unsetCursor()
        self.refresh()

    def mousePressEvent(self, event) -> None:
        """คลิก = เลือกลายเซ็น/กล่องข้อความ หรือวางจุดข้อความใหม่"""
        if self.placing or not self.doc or event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        if self._highlighting:
            self._drag_start = self._label.mapFrom(self, event.pos())
            self._drag_now = self._drag_start
            event.accept()
            return

        local = self._label.mapFrom(self, event.pos())
        px, py = local.x() / self.zoom, local.y() / self.zoom
        point = fitz.Point(px, py)

        if getattr(self, "_picking_point", False):
            mode = getattr(self, "_pick_mode", "add")
            self.stop_point_pick()
            if mode == "edit":
                self.editPointPicked.emit(self.index, px, py)
            else:
                self.pointPicked.emit(self.index, px, py)
            event.accept()
            return

        tb = self.doc.textbox_at(self.index, point)
        stamp = self.doc.stamp_at(self.index, point)
        changed = False

        if tb is not None:            # กล่องข้อความอยู่บนสุด ให้ก่อน
            self.selected_textbox = tb
            self.selected_stamp = None
            self.textboxSelected.emit()
        elif stamp is not None:
            self.selected_stamp = stamp
            self.selected_textbox = None
            self.stampSelected.emit()
        else:
            changed = self.selected_stamp is not None or self.selected_textbox is not None
            self.selected_stamp = None
            self.selected_textbox = None
            if changed:
                self.refresh()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._highlighting and self._drag_start is not None:
            self._drag_now = self._label.mapFrom(self, event.pos())
            self.refresh()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._highlighting and self._drag_start is not None:
            end = self._label.mapFrom(self, event.pos())
            a, b = self._drag_start, end
            self._drag_start = None
            self._drag_now = None
            z = self.zoom
            rect = fitz.Rect(min(a.x(), b.x()) / z, min(a.y(), b.y()) / z,
                             max(a.x(), b.x()) / z, max(a.y(), b.y()) / z)
            # ลากเป็นกรอบ = ไฮไลต์, คลิกเฉยๆ (กรอบจิ๋ว) = ลบไฮไลต์ตรงนั้น
            self.rectDragged.emit(self.index, rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        """ดับเบิลคลิกที่ลายเซ็น = เข้าโหมดย้าย/ย่อขยายทันที"""
        if self.placing or not self.doc or event.button() != Qt.LeftButton:
            super().mouseDoubleClickEvent(event)
            return

        local = self._label.mapFrom(self, event.pos())
        point = fitz.Point(local.x() / self.zoom, local.y() / self.zoom)
        tb = self.doc.textbox_at(self.index, point)
        if tb is not None:                       # ดับเบิลคลิกข้อความ = แก้คำ
            self.selected_textbox = tb
            self.textboxEditRequested.emit()
            event.accept()
            return
        hit = self.doc.stamp_at(self.index, point)
        if hit is not None:
            self.selected_stamp = hit
            self.stampEditRequested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def start_editing(self, stamp) -> None:
        """เอาลายเซ็นที่เลือกมาเข้าโหมดลากย้าย/ย่อขยาย"""
        self.start_placing(stamp.image_path)   # เรียกก่อน เพราะข้างในล้าง _editing_stamp
        self._editing_stamp = stamp
        r = stamp.rect
        self.overlay.setGeometry(
            int(r.x0 * self.zoom), int(r.y0 * self.zoom),
            max(MIN_SIZE, int(r.width * self.zoom)), max(MIN_SIZE, int(r.height * self.zoom)),
        )
        self.refresh()

    def start_editing_textbox(self, box) -> None:
        """เอากล่องข้อความมาเข้าโหมดลากย้าย/ย่อขยาย (ใช้ overlay รูปข้อความ)"""
        self.cancel_placing()
        overlay = PlacementOverlay(self._label, "")
        overlay.source = render_textbox_pixmap(box, self.zoom)
        overlay.setPixmap(overlay.source)
        r = box.rect
        overlay.setGeometry(
            int(r.x0 * self.zoom), int(r.y0 * self.zoom),
            max(MIN_SIZE, int(r.width * self.zoom)), max(MIN_SIZE, int(r.height * self.zoom)),
        )
        overlay.show()
        overlay.raise_()
        self.overlay = overlay
        self._editing_textbox = box
        self.refresh()

    @property
    def editing_stamp(self):
        return self._editing_stamp

    @property
    def editing_textbox(self):
        return self._editing_textbox

    def wheelEvent(self, event) -> None:
        # Ctrl+ล้อเมาส์ = ซูม, ล้อเปล่า = เลื่อนตามปกติ
        if event.modifiers() & Qt.ControlModifier:
            self.set_zoom(self.zoom * (1.1 if event.angleDelta().y() > 0 else 1 / 1.1))
            event.accept()
        else:
            super().wheelEvent(event)
