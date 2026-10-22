"""ทดสอบการเลื่อนต่อเนื่องหลายหน้า (กระดาษเรียงกันบนแคนวาสเดียว)"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument
from app.viewer import GAP

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(4):
    doc.new_page(width=595, height=842).insert_text((72, 72), f"page {i+1}")
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

app = QApplication(sys.argv)
w = MainWindow()
w.resize(900, 600)
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)
w.show()
w.viewer.set_zoom(1.0)
app.processEvents()

v = w.viewer
vbar = v.verticalScrollBar()

# ---- ทุกหน้าถูกวางเรียงกันบนแคนวาสเดียว (มีช่องว่างคั่น) ----
assert len(v._geoms) == 4, "ต้องมีกรอบครบ 4 หน้า"
for i in range(3):
    gap = v._geoms[i + 1].y() - v._geoms[i].bottom()
    assert abs(gap - GAP) <= 2, f"ช่องว่างระหว่างหน้า {i+1}-{i+2} ควร ~{GAP}px ได้ {gap}"
print("OK  4 หน้าเรียงต่อกันบนแคนวาสเดียว มีช่องว่างคั่น")

# ---- แคนวาสสูงพอครอบทุกหน้า (เลื่อนต่อเนื่องได้จริง) ----
assert v._label.height() >= v._geoms[-1].bottom(), "แคนวาสต้องสูงครอบหน้าสุดท้าย"
assert vbar.maximum() > 0, "ต้องมีพื้นที่ scroll"
print("OK  แคนวาสสูงครอบทั้งเล่ม เลื่อนต่อเนื่องได้")

# ---- เลื่อน scroll แล้ว index ตามหน้าที่มองเห็น + ส่งสัญญาณ pageChanged ----
seen = []
v.pageChanged.connect(lambda i: seen.append(i))
vbar.setValue(0)
assert v.index == 0
vbar.setValue(v._geoms[2].y() + 5)     # เลื่อนให้หน้า 3 อยู่บนสุด
app.processEvents()
assert v.index == 2, f"เลื่อนถึงหน้า 3 แต่ index={v.index}"
assert 2 in seen, "ต้องส่งสัญญาณ pageChanged(2)"
print("OK  เลื่อน scroll -> index ตามหน้าที่เห็น + แจ้ง pageChanged")

# ---- show_page เลื่อนไปหน้านั้นบนสุด ----
v.show_page(3)
app.processEvents()
assert v.index == 3
assert abs(vbar.value() - (v._geoms[3].y() - 4)) <= 6, "หน้า 4 ต้องเลื่อนมาบนสุด"
print("OK  show_page เลื่อนไปหน้าที่ขอไว้")

# ---- _page_at: จุดบนแคนวาสรู้ว่าอยู่หน้าไหน ----
mid2 = v._geoms[1].center()
idx, px, py = v._page_at(mid2)
assert idx == 1, f"จุดกลางหน้า 2 ควรได้ index 1 ได้ {idx}"
print("OK  แปลงพิกัดแคนวาส -> รู้ว่าอยู่หน้าไหน")

# ---- Ctrl+ล้อ = ซูม (ไม่พัง, ยังอยู่หน้าเดิม) ----
v.show_page(1); app.processEvents()
z0 = v.zoom
ev = QWheelEvent(QPoint(100, 100), v.mapToGlobal(QPoint(100, 100)),
                 QPoint(0, 120), QPoint(0, 120), Qt.NoButton, Qt.ControlModifier,
                 Qt.NoScrollPhase, False)
v.wheelEvent(ev); app.processEvents()
assert v.zoom > z0, "Ctrl+ล้อขึ้นต้องซูมเข้า"
assert v.index == 1, "ซูมแล้วยังอยู่หน้าเดิม"
print("OK  Ctrl+ล้อ ยังซูมได้ คงหน้าเดิม")

print("\nผ่านทั้งหมด")
