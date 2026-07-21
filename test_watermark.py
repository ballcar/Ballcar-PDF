"""ทดสอบลายน้ำ + ลายเซ็น"""
import sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument, find_thai_font

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(3):
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 120), f"MARK{i+1}", fontsize=30)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

# รูปลายเซ็นจำลอง (PNG พื้นหลังใส)
sig = tmp / "sig.png"
pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 80), True)
pix.clear_with(0)
pix.save(str(sig))

app = QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc)
    w._refresh_all(keep_row=0)
    return w


def ink(d, i):
    """นับพิกเซลที่ไม่ใช่สีขาว — ใช้ดูว่ามีอะไรถูกวาดเพิ่มไหม"""
    p = d.render_page(i, 0.5)
    return sum(1 for b in p.samples if b < 250)


print("ฟอนต์ไทยที่จะใช้:", find_thai_font())
assert find_thai_font(), "ไม่พบฟอนต์ไทยในเครื่อง"

# ---- ลายน้ำภาษาอังกฤษ ----
w = fresh()
before = [ink(w.doc, i) for i in range(3)]
w.doc.add_text_watermark("COPY")
after = [ink(w.doc, i) for i in range(3)]
assert all(a > b for a, b in zip(after, before)), (before, after)
print("OK  ลายน้ำอังกฤษ ทุกหน้า")

w.undo()
assert [ink(w.doc, i) for i in range(3)] == before
print("OK  undo ลายน้ำได้")

# ---- ลายน้ำภาษาไทย (ต้องใช้ฟอนต์ไทย ไม่ใช่ helv) ----
w = fresh()
w.doc.add_text_watermark("สำเนา ห้ามใช้อ้างอิง")
assert ink(w.doc, 0) > before[0]
out = tmp / "thai.pdf"
w.doc.save(out)
with fitz.open(out) as v:
    fonts = [f[3] for f in v.load_page(0).get_fonts()]
    assert any("thai" in f.lower() or "leela" in f.lower() or "tahoma" in f.lower() for f in fonts), fonts
    # ข้อความไทยต้องอ่านกลับออกมาได้ ไม่ใช่กล่องสี่เหลี่ยม
    assert "สำเนา" in v.load_page(0).get_text(), repr(v.load_page(0).get_text())
print("OK  ลายน้ำภาษาไทย (ฟอนต์ฝังถูก อ่านกลับได้)")

# ---- ลายน้ำเฉพาะบางหน้า ----
w = fresh()
w.doc.add_text_watermark("DRAFT", indexes=[1])
now = [ink(w.doc, i) for i in range(3)]
assert now[0] == before[0] and now[2] == before[2] and now[1] > before[1], (before, now)
print("OK  ลายน้ำเฉพาะหน้าที่เลือก")

# ---- ข้อความว่างต้องเตือน ----
w = fresh()
try:
    w.doc.add_text_watermark("   ")
except ValueError:
    print("OK  ข้อความว่างถูกปฏิเสธ")
else:
    raise AssertionError("ข้อความว่างควร error")

# ---- ลายน้ำจากรูป ----
w = fresh()
w.doc.add_image_watermark(sig, scale=0.5)
assert ink(w.doc, 0) > before[0]
w.undo()
assert ink(w.doc, 0) == before[0]
print("OK  ลายน้ำจากรูป + undo")

# ---- ลายเซ็น: วางตามกรอบที่ปรับไว้ ----
def place(w, page, rect):
    """จำลองการวางลายเซ็น (รายละเอียดการลาก/ย่อขยายอยู่ใน test_placement.py)"""
    w.thumbs.setCurrentRow(page)
    w.doc.add_image(page, str(sig), rect)


w = fresh()
place(w, 1, fitz.Rect(100, 600, 300, 680))
assert ink(w.doc, 1) > before[1]
assert w.doc.dirty
imgs = w.doc.doc.load_page(1).get_images()
assert len(imgs) == 1, imgs
print("OK  วางลายเซ็นตามกรอบที่ลาก")

w.undo()
assert len(w.doc.doc.load_page(1).get_images()) == 0
print("OK  undo ลายเซ็น")

# ---- ลายเซ็นบนหน้าที่หมุนแล้ว ต้องไม่ error ----
w = fresh()
w.doc.rotate_pages([0], 90)
place(w, 0, fitz.Rect(50, 50, 250, 130))
assert len(w.doc.doc.load_page(0).get_images()) == 1
print("OK  วางลายเซ็นบนหน้าที่หมุนแล้ว")

# ---- บันทึกแล้วเปิดใหม่ยังอยู่ ----
w = fresh()
w.doc.add_text_watermark("สำเนา")
place(w, 0, fitz.Rect(100, 600, 300, 680))
final = tmp / "final.pdf"
w.doc.save(final)
with fitz.open(final) as v:
    assert "สำเนา" in v.load_page(0).get_text()
    assert len(v.load_page(0).get_images()) == 1
print("OK  บันทึกแล้วลายน้ำ+ลายเซ็นยังอยู่")

print("\nผ่านทั้งหมด")
