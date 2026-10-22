"""ทดสอบเครื่องมือวาด/มาร์กอัป (ปากกา/เส้น/ลูกศร/สี่เหลี่ยม/วงกลม)"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp / "appdata")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app.pdfops import PdfDocument, Annotation, arrowhead_points

doc = fitz.open()
for i in range(2):
    doc.new_page(width=400, height=300)
src = tmp / "t.pdf"; doc.save(str(src)); doc.close()

# ---- arrowhead ----
left, right = arrowhead_points((0, 0), (100, 0), 2.0)
assert left[0] < 100 and right[0] < 100, "ปีกลูกศรต้องอยู่ก่อนปลาย"
assert abs(left[1]) > 1 and abs(right[1]) > 1, "ปีกต้องกางออกจากแกน"
print("OK  คำนวณปลายลูกศร")

# ---- เพิ่ม/เก็บ/undo แต่ละชนิด ----
d = PdfDocument(src)
d.add_annotation(0, "rect", [(50, 50), (200, 150)], (1, 0, 0), 2)
d.add_annotation(0, "arrow", [(20, 200), (180, 250)], (0, 0, 1), 3)
d.add_annotation(0, "draw", [(10, 10), (20, 30), (40, 15)], (0, 0.5, 0), 2)
d.add_annotation(1, "circle", [(30, 30), (120, 100)], (0.6, 0, 0.6), 2)
assert len(d.annotations_on(0)) == 3 and len(d.annotations_on(1)) == 1
a0 = d.annotations_on(0)[0]
assert a0.kind == "rect" and a0.color == (1, 0, 0) and a0.width == 2
assert a0.copy().points == a0.points
print("OK  เพิ่มรูปวาด 4 ชนิด แยกตามหน้า")

# ยังไม่บันทึก -> ยังไม่มีในไฟล์
assert not d.doc.load_page(0).get_drawings(), "ยังไม่บันทึก ไม่ควรฝังลงไฟล์"
print("OK  ยังไม่บันทึก ยังไม่ฝัง")

# undo ทีละชิ้น
d.undo()
assert len(d.annotations_on(1)) == 0
print("OK  undo รูปวาดได้")

# ---- บันทึก -> ฝังเป็น vector จริง ----
out = tmp / "drawn.pdf"
d.save(out)
with fitz.open(out) as v:
    dr0 = v.load_page(0).get_drawings()
    # rect(1) + arrow(line+2ปีก=3) + draw polyline(1) = 5 เส้น
    assert len(dr0) >= 4, f"ควรมี vector หลายเส้น ได้ {len(dr0)}"
assert d.annotations == [], "บันทึกแล้ว annotation ต้องถูกฝัง"
print(f"OK  บันทึกแล้วฝังเป็น vector ({len(dr0)} เส้น) — ยังคมชัดตอนซูม")

# ---- clear ทั้งหน้า ----
d2 = PdfDocument(src)
d2.add_annotation(0, "line", [(0, 0), (10, 10)])
d2.add_annotation(0, "line", [(5, 5), (20, 20)])
assert d2.clear_annotations(0) == 2 and d2.annotations_on(0) == []
print("OK  ล้างที่วาดทั้งหน้า")

# ---- พิมพ์/ออกรูป รวมรูปวาด (flattened) ----
d3 = PdfDocument(src)
d3.add_annotation(0, "rect", [(40, 40), (300, 200)], (1, 0, 0), 3)
with d3.flattened() as flat:
    assert flat.load_page(0).get_drawings(), "flattened ต้องมีรูปวาด"
assert not d3.doc.load_page(0).get_drawings(), "ต้นฉบับต้องไม่ถูกแตะ"
print("OK  พิมพ์/ออกรูป รวมรูปวาด (ต้นฉบับไม่ถูกแตะ)")

# ============ UI ============
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app.main import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
    w.viewer.set_zoom(1.0); w.resize(1000, 700); w.show(); app.processEvents()
    return w


def drag(w, p0, p1):
    off = w.viewer._page_offset()
    def pos(p):
        return w.viewer._label.mapTo(w.viewer, QPoint(int(p[0]) + off.x(), int(p[1]) + off.y()))
    a, b = pos(p0), pos(p1)
    w.viewer.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(a), QPointF(a),
                                         Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    w.viewer.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(b), QPointF(b),
                                        Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    w.viewer.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPointF(b), QPointF(b),
                                           Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
    app.processEvents()


# เข้าโหมด + วาดสี่เหลี่ยม
w = fresh()
w.toggle_annot_mode()
assert w.viewer._annotating and w._annot_bar.isVisible()
w._set_annot_tool("rect")
drag(w, (50, 50), (200, 160))
assert len(w.doc.annotations_on(0)) == 1
assert w.doc.annotations_on(0)[0].kind == "rect"
print("OK  เข้าโหมดวาด + ลากวาดสี่เหลี่ยมผ่าน UI")

# วาดปากกา (freehand) — ต้องเก็บหลายจุด
w._set_annot_tool("draw")
off = w.viewer._page_offset()
def local(p): return w.viewer._label.mapTo(w.viewer, QPoint(int(p[0]) + off.x(), int(p[1]) + off.y()))
p0 = local((10, 250))
w.viewer.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(p0), QPointF(p0),
                                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
for pt in [(30, 260), (60, 240), (90, 270)]:
    lp = local(pt)
    w.viewer.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(lp), QPointF(lp),
                                        Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
endp = local((90, 270))
w.viewer.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPointF(endp), QPointF(endp),
                                       Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
app.processEvents()
draws = [a for a in w.doc.annotations_on(0) if a.kind == "draw"]
assert draws and len(draws[0].points) >= 3, "ปากกาต้องเก็บหลายจุด"
print(f"OK  วาดปากกา (freehand) เก็บ {len(draws[0].points)} จุด")

# คลิกเฉยๆ (ไม่ลาก) ไม่เกิดรูป
before = len(w.doc.annotations_on(0))
w._set_annot_tool("line")
drag(w, (100, 100), (101, 101))
assert len(w.doc.annotations_on(0)) == before, "คลิกเฉยๆ ไม่ควรเกิดรูป"
print("OK  คลิกเฉยๆ ไม่เกิดรูป (กันจุดหลงจากคลิกพลาด)")

# เปลี่ยนสี/ความหนา แล้วรูปใหม่ได้ค่านั้น
w._annot_color = (0.0, 0.0, 1.0)
w.viewer.set_annot_style(w._annot_color, 5.0)
w._annot_width = 5.0
w._set_annot_tool("arrow")
drag(w, (20, 20), (150, 60))
arrow = [a for a in w.doc.annotations_on(0) if a.kind == "arrow"][0]
assert arrow.color == (0.0, 0.0, 1.0) and arrow.width == 5.0
print("OK  เปลี่ยนสี/ความหนา มีผลกับรูปใหม่")

# ออกโหมด + undo
w._end_annot_mode()
assert not w.viewer._annotating and not w._annot_bar.isVisible()
n = len(w.doc.annotations)
w.undo()
assert len(w.doc.annotations) == n - 1
print("OK  ออกโหมด + undo ผ่าน UI")

# clear หน้า
w.clear_annotations_page()
assert w.doc.annotations_on(0) == []
print("OK  ล้างที่วาดหน้านี้ผ่าน UI")

# ปุ่ม markup อยู่ในเมนูเครื่องมือ
tb_menu = w.tools_button.menu()
labels = [a.text() for a in tb_menu.actions() if a.text()]
assert any("มาร์กอัป" in x or "Markup" in x for x in labels), labels
print("OK  มีเมนู 'วาด/มาร์กอัป' ในเครื่องมือ")

print("\nผ่านทั้งหมด")
