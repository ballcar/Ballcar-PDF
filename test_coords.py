"""ทดสอบพิกัดเมาส์ตรงกับตำแหน่งบนหน้า แม้หน้าจะเล็กกว่าจอ (ภาพถูกวางกึ่งกลาง)"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox
from unittest.mock import patch
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
doc.new_page(width=300, height=200)      # หน้าเล็ก
src = tmp / "small.pdf"
doc.save(str(src)); doc.close()

app = QApplication.instance() or QApplication(sys.argv)

w = MainWindow()
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w.viewer.set_zoom(1.0)
w._refresh_all(keep_row=0)
w.resize(1100, 800)          # จอใหญ่กว่าหน้ามาก -> ภาพถูกวางกึ่งกลาง
w.show()
app.processEvents()

off = w.viewer._page_offset()
assert off.x() > 0, f"ทดสอบนี้ต้องการให้ภาพถูกวางกึ่งกลาง (ขอบซ้าย {off.x()})"
print(f"OK  หน้าเล็กกว่าจอ -> ภาพถูกวางกึ่งกลาง (ขอบซ้าย {off.x()}px บน {off.y()}px)")


def press_at_page_point(page_x, page_y, handler=None):
    """คลิกที่จุดบนหน้า (พิกัด PDF) — จำลองเหมือนผู้ใช้คลิกตรงนั้นจริง"""
    label_pt = QPoint(int(page_x * w.viewer.zoom) + off.x(),
                      int(page_y * w.viewer.zoom) + off.y())
    pos = w.viewer._label.mapTo(w.viewer, label_pt)
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(pos), QPointF(pos),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    (handler or w.viewer.mousePressEvent)(ev)
    return pos


# ---- คลิกวางจุดข้อความ: จุดที่ได้ต้องตรงกับที่คลิก ----
got = {}
w.viewer.pointPicked.connect(lambda p, x, y: got.update(x=x, y=y))
w.viewer.start_point_pick("add")
# main ก็ต่อสัญญาณนี้แล้วเปิด dialog โมดัล -> ต้อง patch ไม่งั้นเทสต์ค้าง
with patch.object(w, "_ask_text_content", return_value=("", "", False, False)):
    press_at_page_point(120, 80)
assert got, "ต้องได้สัญญาณจุดที่คลิก"
assert abs(got["x"] - 120) <= 1 and abs(got["y"] - 80) <= 1, \
    f"คลิกที่ (120,80) แต่ได้ ({got['x']:.1f},{got['y']:.1f})"
print(f"OK  คลิกวางข้อความตรงจุด (ได้ {got['x']:.0f},{got['y']:.0f})")

# ---- ลากกรอบยางลบ: กรอบต้องตรงกับที่ลาก ----
dragged = {}
w.viewer.eraseDragged.connect(lambda p, r: dragged.update(rect=r))
w.viewer.start_erase_drag()
press_at_page_point(50, 40)
# ลากไปปล่อยที่ (200, 120)
end_label = QPoint(int(200 * w.viewer.zoom) + off.x(), int(120 * w.viewer.zoom) + off.y())
end_pos = w.viewer._label.mapTo(w.viewer, end_label)
# main จะถามต่อว่าจะพิมพ์ข้อความไหม -> ตอบ No กันเทสต์ค้าง
with patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    w.viewer.mouseReleaseEvent(QMouseEvent(
        QEvent.MouseButtonRelease, QPointF(end_pos), QPointF(end_pos),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
r = dragged.get("rect")
assert r is not None, "ต้องได้กรอบที่ลาก"
assert abs(r.x0 - 50) <= 1 and abs(r.y0 - 40) <= 1, f"มุมบนซ้ายเพี้ยน {r}"
assert abs(r.x1 - 200) <= 1 and abs(r.y1 - 120) <= 1, f"มุมล่างขวาเพี้ยน {r}"
print(f"OK  ลากกรอบยางลบตรงกับเมาส์ ({r.x0:.0f},{r.y0:.0f})-({r.x1:.0f},{r.y1:.0f})")

# ---- คลิกเลือกกล่องข้อความที่วางไว้: ต้องโดน ----
w.viewer.stop_erase_drag()
box = w.doc.add_textbox(0, fitz.Rect(100, 60, 220, 90), "ทดสอบ", font_size=12)
w._refresh_all(keep_row=0)
app.processEvents()
off = w.viewer._page_offset()
w.viewer.selected_textbox = None
press_at_page_point(150, 75)     # คลิกกลางกล่อง
assert w.viewer.selected_textbox is box, "คลิกกลางกล่องต้องเลือกโดน"
print("OK  คลิกเลือกกล่องข้อความโดนตรงตำแหน่ง")

# ---- วาง/แก้ลายเซ็นผ่าน overlay: กลับไปกลับมาต้องได้พิกัดเดิม ----
sig = tmp / "sig.png"
fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 30)).save(str(sig))
stamp = w.doc.add_stamp(0, str(sig), fitz.Rect(80, 100, 200, 150))
w.viewer.start_editing(stamp)
back = w.viewer.placement_rect()
assert abs(back.x0 - 80) <= 1 and abs(back.y0 - 100) <= 1, f"พิกัด overlay เพี้ยน {back}"
assert abs(back.x1 - 200) <= 1 and abs(back.y1 - 150) <= 1, f"พิกัด overlay เพี้ยน {back}"
print(f"OK  overlay ลายเซ็นพิกัดตรง ({back.x0:.0f},{back.y0:.0f})-({back.x1:.0f},{back.y1:.0f})")
w.viewer.cancel_placing()

print("\nผ่านทั้งหมด")
