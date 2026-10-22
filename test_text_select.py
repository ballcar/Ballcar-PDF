"""ทดสอบลากเลือกข้อความบนหน้า แล้วคัดลอก/ไฮไลต์/ค้นหา"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import (PdfDocument, merge_line_rects, page_words,
                        select_words_between)

tmp = Path(tempfile.mkdtemp())
LINES = ["329 Moo.3 Banmai, Pakkred",
         "Nonthaburi, 11120",
         "Thailand",
         "020181111",
         "cssmeeting@cssthailand.com"]
d = fitz.open()
pg = d.new_page(width=420, height=300)
pg.insert_text((40, 40), "Sold To Address:", fontsize=11)
for n, line in enumerate(LINES):
    pg.insert_text((150, 60 + n * 18), line, fontsize=11)
d.new_page(width=420, height=300).insert_text((40, 40), "second page", fontsize=11)
src = tmp / "addr.pdf"
d.save(str(src)); d.close()

# ================= ส่วนคำนวณ =================

doc = fitz.open(str(src))
words = page_words(doc.load_page(0))
assert words, "ต้องอ่านคำบนหน้าได้"

# ลากจากคำแรกของบรรทัด 1 ถึงคำสุดท้ายของบรรทัด 3
rects, text = select_words_between(words, (152, 60), (300, 96))
assert "329" in text and "Thailand" in text, text
assert "cssmeeting" not in text, "ไม่ควรเลยไปบรรทัดที่ไม่ได้ลาก"
assert text.count("\n") == 2, f"3 บรรทัดต้องมีขึ้นบรรทัดใหม่ 2 ครั้ง ได้ {text!r}"
print(f"OK  เลือกข้ามบรรทัดได้ ({text.splitlines()[0]!r} … {text.splitlines()[-1]!r})")

# ลากย้อนทิศ ต้องได้ผลเหมือนกัน
rects_b, text_b = select_words_between(words, (300, 96), (152, 60))
assert text_b == text, "ลากย้อนทิศต้องได้ข้อความเดียวกัน"
print("OK  ลากย้อนทิศได้ผลเหมือนกัน")

# เลือกคำเดียว
_, one = select_words_between(words, (155, 96), (158, 96))
assert one.strip() == "Thailand", repr(one)
print(f"OK  เลือกคำเดียวได้ ({one!r})")

# รวมกรอบคำในบรรทัดเดียวกันเป็นแถบเดียว
merged = merge_line_rects(rects)
assert len(merged) == 3, f"3 บรรทัด ควรได้ 3 แถบ ได้ {len(merged)}"
assert all(m.width > 0 and m.height > 0 for m in merged)
print("OK  รวมกรอบคำเป็นแถบต่อบรรทัด (ไฮไลต์ดูเรียบ)")

# หน้าไม่มีข้อความ ต้องไม่พัง
blank = fitz.open(); blank.new_page(width=200, height=200)
assert select_words_between(page_words(blank.load_page(0)), (10, 10), (50, 50)) == ([], "")
blank.close()
doc.close()
print("OK  หน้าไม่มีข้อความ -> ไม่พัง")

# ================= ลากเลือกผ่านหน้าจอจริง =================

app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow()
w.resize(900, 700)
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)
w.show()
w.viewer.set_zoom(1.0)
app.processEvents()
v = w.viewer


def drag(p0, p1):
    a = v.page_point_to_viewer(0, *p0)
    b = v.page_point_to_viewer(0, *p1)
    v.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(a), QPointF(a),
                                  Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    v.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(b), QPointF(b),
                                 Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    v.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPointF(b), QPointF(b),
                                    Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
    app.processEvents()


got = []
v.textSelected.connect(lambda txt, pg_, r: got.append(txt))
drag((152, 60), (300, 96))
assert got, "ลากแล้วต้องส่งสัญญาณว่าเลือกข้อความ"
assert "329" in v.selected_text and "Thailand" in v.selected_text, v.selected_text
assert v._sel_rects, "ต้องมีแถบไฮไลต์ให้เห็น"
print(f"OK  ลากเลือกบนหน้าจอได้ ({len(v.selected_text)} ตัวอักษร)")

# แถบลอยต้องโผล่ และอยู่ในกรอบวิวเออร์
assert w._sel_popup.isVisible(), "แถบลอยต้องโผล่หลังเลือก"
r = w._sel_popup.geometry()
assert r.x() >= 0 and r.y() >= 0, f"แถบลอยหลุดขอบ {r}"
assert r.right() <= v.width() and r.bottom() <= v.height(), f"แถบลอยล้นวิวเออร์ {r}"
# ต้องอยู่ "ข้างข้อความที่เลือก" จริงๆ ไม่ใช่ค้างมุมบนซ้าย
anchor = v.page_point_to_viewer(0, v._sel_rects[-1].x0, v._sel_rects[-1].y1)
assert abs(r.x() - anchor.x()) < 60 and 0 < r.y() - anchor.y() < 60, \
    f"แถบลอยไม่ได้อยู่ข้างข้อความ (แถบ {r.x()},{r.y()} vs ข้อความ {anchor.x()},{anchor.y()})"
print("OK  แถบลอยโผล่ข้างข้อความที่เลือก อยู่ในกรอบพอดี")

# คัดลอกเข้าคลิปบอร์ด
w.copy_selected_text()
clip = QApplication.clipboard().text()
assert "329 Moo.3 Banmai" in clip and "Thailand" in clip, repr(clip)
assert not w._sel_popup.isVisible(), "คัดลอกแล้วแถบควรหาย"
print(f"OK  คัดลอกเข้าคลิปบอร์ดได้ ({len(clip)} ตัวอักษร)")

# คลิกที่ว่างเปล่า = ล้างการเลือก
drag((10, 280), (11, 281))
assert v.selected_text == "" or len(v.selected_text) < len(clip), "คลิกใหม่ต้องเริ่มเลือกใหม่"
v.clear_selection()
assert v.selected_text == "" and not v._sel_rects
assert not w._sel_popup.isVisible()
print("OK  ล้างการเลือกได้ แถบลอยหายตาม")

# เลือกทั้งหน้า (Ctrl+A)
text_all = v.select_all_on_page(0)
assert "Sold To Address" in text_all and "cssmeeting" in text_all, text_all[:80]
print(f"OK  เลือกข้อความทั้งหน้าได้ ({len(text_all)} ตัวอักษร)")

# ไฮไลต์จากข้อความที่เลือก
drag((152, 60), (300, 78))
before = len(w.doc.doc.load_page(0).annots() and list(w.doc.doc.load_page(0).annots()) or [])
w.highlight_selected_text()
app.processEvents()
after = list(w.doc.doc.load_page(0).annots())
assert len(after) > before, "ไฮไลต์แล้วต้องมี annotation เพิ่ม"
assert v.selected_text == "", "ไฮไลต์แล้วต้องล้างการเลือก"
print(f"OK  ไฮไลต์ข้อความที่เลือกได้ ({len(after)} จุด)")

# ค้นหาคำที่เลือก
drag((152, 96), (200, 96))
picked = v.selected_text.strip()
w.search_selected_text()
app.processEvents()
assert w.search_box.text() == picked, f"{w.search_box.text()!r} vs {picked!r}"
print(f"OK  ส่งข้อความที่เลือกไปช่องค้นหาได้ ({picked!r})")

# ================= ไม่กวนเครื่องมืออื่น =================

# อยู่ในโหมดไฮไลต์ ลากแล้วต้องไม่ไปเลือกข้อความ
v.clear_selection()
v.start_highlight_drag()
drag((152, 60), (300, 78))
assert v.selected_text == "", "ระหว่างโหมดไฮไลต์ ห้ามลากเลือกข้อความ"
v.stop_highlight_drag()
print("OK  ระหว่างโหมดไฮไลต์/ยางลบ ไม่ไปลากเลือกข้อความ")

# คลิกโดนกล่องข้อความที่วางไว้ ต้องเลือกกล่อง ไม่ใช่เลือกข้อความ
box = w.doc.add_textbox(0, fitz.Rect(40, 200, 200, 230), "กล่องทดสอบ", font_size=12)
w._refresh_all(keep_row=0)
drag((60, 210), (120, 215))
assert v.selected_textbox is box, "คลิกโดนกล่องต้องเลือกกล่อง"
assert v.selected_text == "", "ไม่ควรลากเลือกข้อความทับกล่อง"
print("OK  คลิกโดนกล่องข้อความ/ลายเซ็น ไม่ไปลากเลือกข้อความ")

# แก้เอกสารแล้วแคชคำต้องถูกล้าง (ไม่เลือกได้ข้อความเก่า)
v.clear_selection()
w.doc.insert_blank_page(0)
w._refresh_all(keep_row=0)
assert v._words_cache == {}, "รีเฟรชแล้วต้องล้างแคชคำ"
print("OK  แก้เอกสารแล้วล้างแคชคำ")

print("\nผ่านทั้งหมด")
