"""ทดสอบฟังก์ชัน PDF โดยไม่ต้องเปิด UI"""
import shutil
import tempfile
from pathlib import Path

import fitz

from app.pdfops import PdfDocument, merge_files, parse_page_ranges

tmp = Path(tempfile.mkdtemp(prefix="pdftest-"))


def make_pdf(name: str, pages: int) -> Path:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 120), f"{name} page {i + 1} apple", fontsize=24)
    path = tmp / f"{name}.pdf"
    doc.save(str(path))
    doc.close()
    return path


src = make_pdf("alpha", 3)
other = make_pdf("beta", 2)

d = PdfDocument(src)
assert d.page_count == 3, d.page_count
assert "apple" in d.page_text(0)
assert len(d.search("apple")) == 3
print("OK  อ่าน/ค้นหา")

d.insert_blank_page(1)
assert d.page_count == 4
d.insert_pdf(0, other)
assert d.page_count == 6
d.delete_pages([0, 1])
assert d.page_count == 4
d.move_page(0, 2)
d.rotate_pages([0], 90)
assert d.doc.load_page(0).rotation == 90
print("OK  จัดการหน้า (แทรก/ลบ/ย้าย/หมุน)")

out = d.save(tmp / "edited.pdf")
assert out.exists() and not d.dirty
reopened = PdfDocument(out)
assert reopened.page_count == 4
reopened.close()
print("OK  บันทึก + เปิดซ้ำ")

part = d.extract_to([0, 2], tmp / "part.pdf")
with fitz.open(part) as p:
    assert p.page_count == 2
merged = merge_files([src, other], tmp / "merged.pdf")
with fitz.open(merged) as m:
    assert m.page_count == 5
print("OK  แยก/รวมไฟล์")

d.add_page_numbers(fmt="{page}/{total}")
assert "/4" in d.page_text(3)
print("OK  เลขหน้า")

jpgs = d.export_images([0, 1], tmp / "img", dpi=100, fmt="jpg")
assert len(jpgs) == 2 and all(f.exists() and f.stat().st_size > 0 for f in jpgs)
pngs = d.export_images([0], tmp / "img", dpi=100, fmt="png")
assert pngs[0].exists()
print("OK  export jpg/png")

assert parse_page_ranges("1-3,5", 10) == [0, 1, 2, 4]
for bad in ("0-2", "3-1", "5-99"):
    try:
        parse_page_ranges(bad, 10)
    except ValueError:
        pass
    else:
        raise AssertionError(f"ควร error: {bad}")
print("OK  parse ช่วงหน้า")

# บันทึกทับไฟล์เดิม (incremental)
copy = tmp / "inplace.pdf"
shutil.copy(src, copy)
d2 = PdfDocument(copy)
d2.rotate_pages([0], 180)
d2.save()
d2.close()
with fitz.open(copy) as v:
    assert v.load_page(0).rotation == 180
print("OK  บันทึกทับไฟล์เดิม")

d.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nผ่านทั้งหมด")
