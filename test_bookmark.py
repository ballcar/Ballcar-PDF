"""ทดสอบ Bookmarks (สารบัญ)"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(6):
    doc.new_page(width=595, height=842)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()


# ---- ไฟล์ไม่มี bookmark ----
d = PdfDocument(src)
assert d.get_bookmarks() == []
print("OK  ไฟล์ใหม่ไม่มี bookmark")

# ---- เพิ่ม bookmark ----
d.add_bookmark("บทที่ 1 บทนำ", 0)
d.add_bookmark("บทที่ 2 วิธีใช้", 2)
d.add_bookmark("บทที่ 3 สรุป", 4)
bm = d.get_bookmarks()
assert len(bm) == 3
assert bm[0]["title"] == "บทที่ 1 บทนำ" and bm[0]["page"] == 0
assert bm[1]["page"] == 2 and bm[2]["page"] == 4
print("OK  เพิ่ม bookmark (ไทย) ได้")

# ---- บันทึกแล้วยังอยู่ ----
out = tmp / "bm.pdf"
d.save(out)
d2 = PdfDocument(out)
bm = d2.get_bookmarks()
assert len(bm) == 3 and bm[0]["title"] == "บทที่ 1 บทนำ"
print("OK  บันทึกแล้ว bookmark ยังอยู่")

# ---- เปลี่ยนชื่อ ----
d2.rename_bookmark(1, "บทที่ 2 การติดตั้ง")
assert d2.get_bookmarks()[1]["title"] == "บทที่ 2 การติดตั้ง"
print("OK  เปลี่ยนชื่อ bookmark")

# ---- ลบ ----
d2.remove_bookmark(0)
bm = d2.get_bookmarks()
assert len(bm) == 2 and bm[0]["title"] == "บทที่ 2 การติดตั้ง"
print("OK  ลบ bookmark")

# ---- undo ----
d2.undo()
assert len(d2.get_bookmarks()) == 3
print("OK  undo bookmark ได้")

# ---- ระดับย่อย (indent) ----
d = PdfDocument(src)
d.add_bookmark("บทที่ 1", 0)
d.add_bookmark("หัวข้อย่อย 1.1", 0)
d.move_bookmark_level(1, +1)   # ทำเป็นระดับ 2
assert d.get_bookmarks()[1]["level"] == 2
d.save(tmp / "lvl.pdf")
with fitz.open(tmp / "lvl.pdf") as v:
    toc = v.get_toc()
    assert toc[1][0] == 2, toc
print("OK  ปรับระดับ bookmark ย่อยได้")

# ---- ระดับกระโดดเกิน +1 ต้องถูกปรับให้ถูกกติกา ----
d = PdfDocument(src)
d.set_bookmarks([
    {"level": 1, "title": "A", "page": 0},
    {"level": 5, "title": "B", "page": 1},   # กระโดดจาก 1 ไป 5
])
d.save(tmp / "fix.pdf")
with fitz.open(tmp / "fix.pdf") as v:
    toc = v.get_toc()
    assert toc[1][0] == 2, f"ระดับต้องถูกปรับเป็น 2 ได้ {toc}"
print("OK  ระดับกระโดดถูกปรับอัตโนมัติ ไม่พัง")

# ---- อ่าน bookmark จากไฟล์ที่มีอยู่แล้ว ----
pre = fitz.open()
for i in range(4):
    pre.new_page()
pre.set_toc([[1, "Intro", 1], [1, "Body", 2], [2, "Detail", 3]])
presrc = tmp / "pre.pdf"
pre.save(str(presrc)); pre.close()
d = PdfDocument(presrc)
bm = d.get_bookmarks()
assert len(bm) == 3 and bm[2]["level"] == 2 and bm[2]["page"] == 2
print("OK  อ่าน bookmark ที่มีอยู่แล้วถูก")

print("\nผ่านทั้งหมด")
