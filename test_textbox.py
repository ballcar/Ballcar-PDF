"""ทดสอบเพิ่ม/แก้ไขข้อความ (ฝั่งตรรกะ)"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(2):
    doc.new_page(width=595, height=842)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()


def ink(d, i, zoom=0.5):
    p = d.render_page(i, zoom)
    return sum(1 for b in p.samples if b < 200)


# ---- เพิ่มกล่องข้อความ (ลอย ยังไม่ฝัง) ----
d = PdfDocument(src)
box = d.add_textbox(0, fitz.Rect(100, 100, 400, 140), "Hello World", font_size=16)
assert len(d.textboxes) == 1
assert d.dirty
# ยังไม่ save จึงยังไม่มีข้อความในหน้าเอกสารจริง
assert "Hello" not in d.page_text(0)
print("OK  เพิ่มกล่องข้อความเป็นชั้นลอย ยังไม่ฝังลงไฟล์")

# ---- แก้ข้อความในกล่อง ----
d.update_textbox_content(box, text="Hello Ballcar")
assert box.text == "Hello Ballcar"
# ---- ย้าย/ปรับขนาด ----
d.update_textbox_rect(box, fitz.Rect(120, 200, 420, 250))
assert box.rect == fitz.Rect(120, 200, 420, 250)
print("OK  แก้ข้อความ + ย้าย/ปรับขนาดกล่อง")

# ---- หากล่องที่จุด ----
assert d.textbox_at(0, fitz.Point(200, 220)) is box
assert d.textbox_at(0, fitz.Point(10, 10)) is None
assert d.textbox_at(1, fitz.Point(200, 220)) is None
print("OK  คลิกหากล่องข้อความถูกตัว/ถูกหน้า")

# ---- undo/redo ----
d.remove_textbox(box)
assert d.textboxes == []
d.undo()
assert len(d.textboxes) == 1 and d.textboxes[0].text == "Hello Ballcar"
d.redo()
assert d.textboxes == []
print("OK  undo/redo การเพิ่ม-ลบข้อความ")

# ---- บันทึกแล้วฝังลงไฟล์ จริง + ค้นหาได้ ----
d = PdfDocument(src)
d.add_textbox(0, fitz.Rect(100, 100, 450, 140), "Invoice No. 12345", font_size=14)
out = tmp / "en.pdf"
d.save(out)
assert d.textboxes == [], "บันทึกแล้วต้องฝังลงไฟล์"
with fitz.open(out) as v:
    text = v.load_page(0).get_text()
    assert "Invoice No. 12345" in text, repr(text)
    assert v.load_page(0).search_for("12345"), "ต้องค้นหาข้อความที่เพิ่มเจอ"
print("OK  บันทึกแล้วข้อความฝังลงไฟล์ + ค้นหาได้")

# ---- ข้อความภาษาไทย: ฟอนต์ฝังถูก อ่านกลับได้ ----
d = PdfDocument(src)
d.add_textbox(0, fitz.Rect(80, 300, 500, 360), "ผลการคัดเลือก ผ่าน", font_size=18)
before = ink(d, 0)
out = tmp / "th.pdf"
d.save(out)
with fitz.open(out) as v:
    got = v.load_page(0).get_text()
    assert "ผลการคัดเลือก" in got, f"อ่านไทยกลับไม่ได้: {got!r}"
    fonts = [f[3].lower() for f in v.load_page(0).get_fonts()]
    assert any("leela" in f or "tahoma" in f or "thai" in f for f in fonts), fonts
print("OK  ข้อความไทยฝังฟอนต์ถูก อ่าน/ค้นหาได้")

# ---- ข้อความว่างไม่วาดอะไร ----
d = PdfDocument(src)
d.add_textbox(0, fitz.Rect(100, 100, 300, 130), "   ")
d.save(tmp / "empty.pdf")
with fitz.open(tmp / "empty.pdf") as v:
    assert v.load_page(0).get_text().strip() == ""
print("OK  กล่องข้อความว่างไม่วาดอะไร ไม่พัง")

# ---- หลายกล่องหลายหน้า ----
d = PdfDocument(src)
d.add_textbox(0, fitz.Rect(50, 50, 200, 80), "หน้าหนึ่ง")
d.add_textbox(0, fitz.Rect(50, 100, 200, 130), "อีกกล่อง")
d.add_textbox(1, fitz.Rect(50, 50, 200, 80), "page two")
assert len(d.textboxes_on(0)) == 2 and len(d.textboxes_on(1)) == 1
d.save(tmp / "multi.pdf")
with fitz.open(tmp / "multi.pdf") as v:
    assert "หน้าหนึ่ง" in v.load_page(0).get_text()
    assert "page two" in v.load_page(1).get_text()
    assert "page two" not in v.load_page(0).get_text()
print("OK  หลายกล่องหลายหน้าฝังถูกที่")

# ---- สีข้อความ ----
d = PdfDocument(src)
d.add_textbox(0, fitz.Rect(100, 100, 400, 140), "RED TEXT", font_size=20, color=(1, 0, 0))
d.save(tmp / "red.pdf")   # กล่องลอยยังไม่ถูกวาดลงหน้า ต้องบันทึกก่อน
with fitz.open(tmp / "red.pdf") as v:
    pix = v.load_page(0).get_pixmap(matrix=fitz.Matrix(2, 2))
s, n = pix.samples, pix.n
# หาพิกเซลที่ช่องแดงเด่นกว่าเขียว/น้ำเงินชัดเจน (เผื่อ antialiasing ไม่ใช่แดงสนิท)
has_red = any(s[k] - s[k+1] > 60 and s[k] - s[k+2] > 60
              for k in range(0, len(s) - n, n))
assert has_red, "ควรมีข้อความสีแดง"
print("OK  กำหนดสีข้อความได้")

# ---- ข้อความติดไปกับลายเซ็นตอน save ----
d = PdfDocument(src)
sig = tmp / "sig.png"
sp = fitz.open(); spp = sp.new_page(width=100, height=40)
spp.draw_line((5, 20), (95, 20), color=(0, 0, 1), width=2)
spp.get_pixmap(alpha=False).save(str(sig)); sp.close()
d.add_stamp(0, str(sig), fitz.Rect(100, 500, 200, 540))
d.add_textbox(0, fitz.Rect(100, 100, 300, 130), "ทั้งคู่")
d.save(tmp / "both.pdf")
with fitz.open(tmp / "both.pdf") as v:
    assert "ทั้งคู่" in v.load_page(0).get_text()
    assert len(v.load_page(0).get_images()) == 1
print("OK  ข้อความ + ลายเซ็นฝังพร้อมกันได้")

print("\nผ่านทั้งหมด")
