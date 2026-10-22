"""ทดสอบ UI ไฮไลต์ข้อความ"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QColor
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
doc.new_page(width=595, height=842).insert_text((72, 100), "The quick brown fox jumps", fontsize=14)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

app = QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc)
    w.viewer.set_zoom(1.0)
    w._refresh_all(keep_row=0)
    w.resize(1000, 800)
    w.show()
    return w


def drag(w, p0, p1):
    """ลากบนวิวเออร์จากจุด p0 ถึง p1 (พิกัดหน้า PDF)"""
    def pos(pt):
        # ต้องบวก offset ที่ภาพหน้าถูกวางกึ่งกลางใน label ด้วย (เหมือนที่ผู้ใช้เห็นจริง)
        off = w.viewer._page_offset()
        local = QPoint(int(pt.x * w.viewer.zoom) + off.x(),
                       int(pt.y * w.viewer.zoom) + off.y())
        return w.viewer._label.mapTo(w.viewer, local)
    a, b = pos(p0), pos(p1)
    w.viewer.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(a), QPointF(a),
                                         Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    w.viewer.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(b), QPointF(b),
                                        Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    w.viewer.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPointF(b), QPointF(b),
                                           Qt.LeftButton, Qt.NoButton, Qt.NoModifier))


def hl_count(w):
    return len([a for a in w.doc.doc.load_page(0).annots(types=[fitz.PDF_ANNOT_HIGHLIGHT])])


# ---- เข้าโหมดไฮไลต์ ----
w = fresh()
w.toggle_highlight_mode()
assert w.viewer._highlighting
assert w._highlight_bar.isVisible()
print("OK  เข้าโหมดไฮไลต์ แถบเครื่องมือโผล่")

# ---- ลากคลุมข้อความ -> ไฮไลต์ ----
drag(w, fitz.Point(70, 92), fitz.Point(250, 110))
assert hl_count(w) == 1, hl_count(w)
assert w.doc.dirty
print("OK  ลากคลุมข้อความแล้วไฮไลต์")

# ---- คลิกที่ไฮไลต์ -> ลบ ----
drag(w, fitz.Point(90, 100), fitz.Point(91, 101))  # คลิกเฉยๆ
assert hl_count(w) == 0, "คลิกที่ไฮไลต์ต้องลบออก"
print("OK  คลิกที่ไฮไลต์เพื่อลบ")

# ---- ลากในที่ว่าง ไม่ไฮไลต์ ----
drag(w, fitz.Point(70, 400), fitz.Point(250, 450))
assert hl_count(w) == 0
print("OK  ลากในที่ว่างไม่ไฮไลต์")

# ---- ล้างไฮไลต์ทั้งหน้า ----
drag(w, fitz.Point(70, 92), fitz.Point(150, 110))
drag(w, fitz.Point(155, 92), fitz.Point(250, 110))
assert hl_count(w) == 2
w.clear_highlights_page()
assert hl_count(w) == 0
print("OK  ล้างไฮไลต์ทั้งหน้า")

# ---- เลือกสีไฮไลต์ ----
with patch("PySide6.QtWidgets.QColorDialog.getColor", return_value=QColor(80, 255, 80)):
    w._pick_highlight_color()
assert w._highlight_color[1] > 0.9 and w._highlight_color[0] < 0.5
drag(w, fitz.Point(70, 92), fitz.Point(200, 110))
a = list(w.doc.doc.load_page(0).annots(types=[fitz.PDF_ANNOT_HIGHLIGHT]))[0]
assert a.colors["stroke"][1] > 0.9, a.colors
print("OK  เลือกสีไฮไลต์แล้วใช้สีนั้น")

# ---- Esc ออกจากโหมด ----
w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
assert not w.viewer._highlighting
assert not w._highlight_bar.isVisible()
print("OK  Esc ออกจากโหมดไฮไลต์")

# ---- toggle ปิดได้ ----
w.toggle_highlight_mode()
assert w.viewer._highlighting
w.toggle_highlight_mode()
assert not w.viewer._highlighting
print("OK  กดปุ่มซ้ำเพื่อปิดโหมด")

# ---- undo ----
w = fresh()
w.toggle_highlight_mode()
drag(w, fitz.Point(70, 92), fitz.Point(250, 110))
assert hl_count(w) == 1
w.undo()
assert hl_count(w) == 0
print("OK  undo ไฮไลต์ได้")

print("\nผ่านทั้งหมด")
