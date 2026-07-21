"""ทดสอบไฮไลต์ข้อความ"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app.pdfops import PdfDocument, find_thai_font

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.insert_font(fontname="thai", fontfile=find_thai_font())
page.insert_text((72, 100), "The quick brown fox", fontsize=14)
page.insert_text((72, 150), "ราคารวมทั้งสิ้น 38,200 บาท", fontname="thai", fontsize=14)
page.insert_text((72, 200), "The quick red fox", fontsize=14)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()


def count_highlights(path, page=0):
    with fitz.open(path) as v:
        return len([a for a in v.load_page(page).annots(types=[fitz.PDF_ANNOT_HIGHLIGHT])])


# ---- ไฮไลต์ตามกรอบ ----
d = PdfDocument(src)
n = d.highlight_rect(0, fitz.Rect(70, 92, 200, 112))  # คลุมบรรทัดแรกบางส่วน
assert n > 0, "ควรไฮไลต์คำได้"
out = tmp / "h.pdf"
d.save(out)
assert count_highlights(out) == 1, "ควรมี 1 annotation ไฮไลต์"
print(f"OK  ไฮไลต์ตามกรอบ ({n} คำ)")

# ---- ไฮไลต์ข้อความไทย ----
d = PdfDocument(src)
n = d.highlight_rect(0, fitz.Rect(70, 142, 400, 162))
assert n > 0
d.save(tmp / "th.pdf")
assert count_highlights(tmp / "th.pdf") == 1
print(f"OK  ไฮไลต์ข้อความไทยได้ ({n} คำ)")

# ---- กรอบที่ไม่โดนข้อความ -> ไม่ไฮไลต์ ----
d = PdfDocument(src)
assert d.highlight_rect(0, fitz.Rect(70, 400, 200, 450)) == 0
assert not d.dirty, "ไม่โดนข้อความ ต้องไม่นับว่าแก้ไข"
print("OK  กรอบว่างไม่ไฮไลต์อะไร")

# ---- ไฮไลต์จากคำค้น (ทุกจุด) ----
d = PdfDocument(src)
n = d.highlight_search("fox")
assert n == 2, f"คำว่า fox มี 2 จุด ได้ {n}"
d.save(tmp / "s.pdf")
# 2 จุดอยู่หน้าเดียวกัน = 1 annotation ที่คลุม 2 quad
assert count_highlights(tmp / "s.pdf") >= 1
print("OK  ไฮไลต์จากคำค้นทุกจุด")

assert PdfDocument(src).highlight_search("notfound") == 0
print("OK  คำค้นไม่เจอไม่ไฮไลต์")

# ---- ลบไฮไลต์ที่จุด ----
d = PdfDocument(src)
d.highlight_rect(0, fitz.Rect(70, 92, 200, 112))
assert d.remove_highlight_at(0, fitz.Point(90, 100)) is True
d.save(tmp / "rm.pdf")
assert count_highlights(tmp / "rm.pdf") == 0
print("OK  ลบไฮไลต์ที่จุดได้")

assert d.remove_highlight_at(0, fitz.Point(300, 500)) is False
print("OK  คลิกที่ไม่มีไฮไลต์คืน False")

# ---- ล้างไฮไลต์ทั้งหน้า ----
d = PdfDocument(src)
d.highlight_rect(0, fitz.Rect(70, 92, 300, 112))
d.highlight_rect(0, fitz.Rect(70, 192, 300, 212))
assert d.clear_highlights(0) == 2
d.save(tmp / "clr.pdf")
assert count_highlights(tmp / "clr.pdf") == 0
print("OK  ล้างไฮไลต์ทั้งหน้าได้")

# ---- undo ----
d = PdfDocument(src)
d.highlight_rect(0, fitz.Rect(70, 92, 300, 112))
d.undo()
d.save(tmp / "u.pdf")
assert count_highlights(tmp / "u.pdf") == 0, "undo ต้องเอาไฮไลต์ออก"
print("OK  undo ไฮไลต์ได้")

# ---- สีที่กำหนด ----
d = PdfDocument(src)
d.highlight_rect(0, fitz.Rect(70, 92, 300, 112), color=(0.4, 1, 0.4))  # เขียว
out = tmp / "green.pdf"
d.save(out)
with fitz.open(out) as v:
    a = list(v.load_page(0).annots(types=[fitz.PDF_ANNOT_HIGHLIGHT]))[0]
    stroke = a.colors.get("stroke")
    assert stroke and stroke[1] > 0.8 and stroke[0] < 0.6, stroke
print("OK  กำหนดสีไฮไลต์ได้")

print("\nผ่านทั้งหมด")
