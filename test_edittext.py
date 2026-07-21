"""ทดสอบแก้ไขข้อความเดิมในไฟล์ (ลบของเดิม + วางใหม่)"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app.pdfops import PdfDocument, find_thai_font

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.insert_font(fontname="thai", fontfile=find_thai_font())
page.insert_text((100, 100), "Invoice No. ABC123", fontsize=14)
page.insert_text((100, 200), "ชื่อลูกค้า สมชาย", fontname="thai", fontsize=16, color=(0, 0, 1))
page.insert_text((100, 300), "ราคา 1,000 บาท", fontname="thai", fontsize=14)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()


# ---- หาข้อความเดิมที่จุด ----
d = PdfDocument(src)
span = d.text_span_at(0, fitz.Point(150, 96))
assert span is not None, "ควรเจอข้อความตรงบรรทัด Invoice"
assert "ABC123" in span["text"], span["text"]
assert 12 < span["size"] < 16, span["size"]
print("OK  หาข้อความเดิมที่จุดได้:", repr(span["text"]))

# จุดที่ไม่มีข้อความ
assert d.text_span_at(0, fitz.Point(400, 600)) is None
print("OK  จุดว่างคืน None")

# สีของข้อความไทยสีน้ำเงิน
blue = d.text_span_at(0, fitz.Point(150, 196))
assert blue["color"][2] > 0.8 and blue["color"][0] < 0.2, blue["color"]
print("OK  อ่านสีข้อความเดิมถูก")

# ---- แก้ข้อความ: ลบเดิม + ได้กล่องใหม่เติมคำเดิม ----
d = PdfDocument(src)
box = d.start_edit_existing_text(0, fitz.Point(150, 96))
assert box is not None
assert "ABC123" in box.text, box.text
assert len(d.textboxes) == 1
# ข้อความเดิมถูกลบออกจากหน้าจริงแล้ว
assert "ABC123" not in d.page_text(0), "ข้อความเดิมต้องถูกลบ"
print("OK  แก้ข้อความ -> ลบเดิม + ได้กล่องเติมคำเดิม")

# แก้คำแล้วบันทึก
d.update_textbox_content(box, text="Invoice No. XYZ999")
out = tmp / "edited.pdf"
d.save(out)
with fitz.open(out) as v:
    text = v.load_page(0).get_text()
    assert "XYZ999" in text, text
    assert "ABC123" not in text, "คำเดิมต้องไม่หลงเหลือ"
print("OK  บันทึกแล้วเป็นคำใหม่ คำเดิมหายไป")

# ---- แก้ข้อความไทย คงสีเดิม ----
d = PdfDocument(src)
box = d.start_edit_existing_text(0, fitz.Point(150, 196))
assert "สมชาย" in box.text, box.text
assert box.color[2] > 0.8, "ต้องคงสีน้ำเงินเดิม"
d.update_textbox_content(box, text="ชื่อลูกค้า สมหญิง")
d.save(tmp / "th.pdf")
with fitz.open(tmp / "th.pdf") as v:
    got = v.load_page(0).get_text()
    assert "สมหญิง" in got and "สมชาย" not in got, got
print("OK  แก้ข้อความไทยได้ คงสีเดิม")

# ---- จุดว่างคืน None (ไม่ลบอะไร) ----
d = PdfDocument(src)
before = d.page_text(0)
assert d.start_edit_existing_text(0, fitz.Point(400, 600)) is None
assert d.page_text(0) == before, "จุดว่างต้องไม่แตะเนื้อหา"
assert not d.dirty
print("OK  จุดว่างไม่แก้อะไร")

# ---- undo คืนข้อความเดิม ----
d = PdfDocument(src)
d.start_edit_existing_text(0, fitz.Point(150, 96))
assert "ABC123" not in d.page_text(0)
d.undo()
assert "ABC123" in d.page_text(0), "undo ต้องคืนข้อความเดิม"
assert d.textboxes == []
print("OK  undo คืนข้อความเดิมได้")

# ---- ไฟล์สแกน (เป็นรูป) ต้องหาข้อความไม่เจอ ----
scan = fitz.open()
sp = scan.new_page(width=595, height=842)
sp.insert_image(sp.rect, pixmap=fitz.open(src)[0].get_pixmap(dpi=100))
scan_src = tmp / "scan.pdf"
scan.save(str(scan_src)); scan.close()
d = PdfDocument(scan_src)
assert d.start_edit_existing_text(0, fitz.Point(150, 96)) is None, "ไฟล์สแกนแก้ข้อความไม่ได้"
print("OK  ไฟล์สแกนหาข้อความไม่เจอ (คืน None)")

print("\nผ่านทั้งหมด")
