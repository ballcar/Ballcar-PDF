"""ทดสอบว่ารวม/แทรกไฟล์แล้วลายเซ็นไม่หาย

ลายเซ็น/ตราประทับในไฟล์งานจริงมักเป็น annotation (Stamp) ไม่ใช่เนื้อหาหน้า
บั๊กที่เจอ (ถึง 1.0.65): เลือก "ปรับขนาดหน้าให้เท่ากัน" ตอนแทรกไฟล์
-> ใช้ show_pdf_page ซึ่งคัดลอกแค่เนื้อหา -> ลายเซ็นหายทั้งไฟล์
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app.pdfops import PdfDocument, merge_files

tmp = Path(tempfile.mkdtemp())


def signed_pdf(name: str, pages: int = 1, width: float = 842, height: float = 595) -> Path:
    """PDF ที่มี 'ลายเซ็น' เป็น Stamp annotation (เหมือนไฟล์งานจริง)"""
    d = fitz.open()
    for i in range(pages):
        p = d.new_page(width=width, height=height)
        p.insert_text((60, 60), f"{name} page {i+1}", fontsize=16)
        # ลายเซ็นเป็น annotation ไม่ใช่เนื้อหาหน้า
        r = fitz.Rect(width * 0.55, height * 0.70, width * 0.90, height * 0.82)
        annot = p.add_rect_annot(r)
        annot.set_border(width=3)
        annot.set_colors(stroke=(0, 0, 0.8))
        annot.update()
    path = tmp / name
    d.save(str(path)); d.close()
    return path


def count_annots(path: Path) -> int:
    with fitz.open(str(path)) as d:
        return sum(len(list(d.load_page(i).annots())) for i in range(d.page_count))


def ink(path: Path, page: int) -> int:
    """หมึกในโซนลายเซ็น (มุมขวาล่าง) — นับรวม annotation ที่วาดออกมา"""
    with fitz.open(str(path)) as d:
        pg = d.load_page(page)
        r = pg.rect
        clip = fitz.Rect(r.width * 0.5, r.height * 0.65, r.width * 0.95, r.height * 0.88)
        px = pg.get_pixmap(dpi=60, clip=clip, annots=True)
    return sum(1 for y in range(px.height) for x in range(px.width)
               if sum(px.pixel(x, y)) < 600)


a = signed_pdf("A.pdf")
b = signed_pdf("B.pdf", width=595, height=842)     # ขนาดต่างกัน -> จะได้เข้าเส้นทางปรับขนาด
assert count_annots(a) == 1 and count_annots(b) == 1
base_ink = ink(b, 0)
assert base_ink > 100, f"ไฟล์ทดสอบต้องมีลายเซ็นให้เห็น ({base_ink})"
print(f"OK  สร้างไฟล์ทดสอบที่มีลายเซ็นเป็น annotation (หมึก {base_ink} พิกเซล)")

# ---- รวมไฟล์ (เมนูรวมไฟล์) ----
merged = tmp / "merged.pdf"
merge_files([str(a), str(b)], merged)
assert count_annots(merged) == 2, f"รวมไฟล์แล้ว annotation ต้องครบ ได้ {count_annots(merged)}"
assert ink(merged, 1) > 100, "ลายเซ็นบนหน้าที่รวมมาต้องยังเห็น"
print("OK  รวมไฟล์ — ลายเซ็นครบ")

# ---- แทรกไฟล์ แบบคงขนาดเดิม ----
import shutil
f1 = tmp / "keep.pdf"; shutil.copy(a, f1)
doc = PdfDocument(f1)
doc.insert_pdfs(doc.page_count, [str(b)], fit_to_page=False)
doc.save(); doc.close()
assert count_annots(f1) == 2, f"คงขนาดเดิม: annotation ต้องครบ ได้ {count_annots(f1)}"
assert ink(f1, 1) > 100, "คงขนาดเดิม: ลายเซ็นต้องยังเห็น"
print("OK  แทรกไฟล์ (คงขนาดเดิม) — ลายเซ็นครบ")

# ---- แทรกไฟล์ แบบปรับขนาดให้เท่ากัน (เคสที่เคยทำลายเซ็นหาย) ----
f2 = tmp / "fit.pdf"; shutil.copy(a, f2)
doc = PdfDocument(f2)
doc.insert_pdfs(doc.page_count, [str(b)], fit_to_page=True)
doc.save(); doc.close()
got = ink(f2, 1)
assert got > 100, f"ปรับขนาด: ลายเซ็นหาย! (หมึก {got} พิกเซล)"
print(f"OK  แทรกไฟล์ (ปรับขนาดให้เท่ากัน) — ลายเซ็นยังอยู่ (หมึก {got} พิกเซล)")

# ---- หลายไฟล์ หลายหน้า พร้อมกัน ----
many = [str(signed_pdf(f"m{i}.pdf", pages=2, width=595 + i * 30, height=842)) for i in range(5)]
f3 = tmp / "many.pdf"; shutil.copy(a, f3)
doc = PdfDocument(f3)
doc.insert_pdfs(doc.page_count, many, fit_to_page=True)
doc.save(); doc.close()
with fitz.open(str(f3)) as v:
    total = v.page_count
assert total == 1 + 10, f"ควรได้ 11 หน้า ได้ {total}"
missing = [i + 1 for i in range(1, total) if ink(f3, i) <= 100]
assert not missing, f"ลายเซ็นหายที่หน้า {missing}"
print(f"OK  แทรก 5 ไฟล์ (10 หน้า) แบบปรับขนาด — ลายเซ็นครบทุกหน้า")

# ---- ข้อความที่เขียนเป็น annotation (FreeText) ก็ต้องไม่หาย ----
ft = fitz.open()
pg = ft.new_page(width=595, height=842)
a2 = pg.add_freetext_annot(fitz.Rect(100, 400, 420, 440), "หมายเหตุแนบท้าย", fontsize=16)
a2.update()
ftp = tmp / "freetext.pdf"; ft.save(str(ftp)); ft.close()
with fitz.open(str(ftp)) as v:
    assert "หมายเหตุแนบท้าย" in v.load_page(0).get_text(), "ไฟล์ทดสอบต้องเห็นข้อความ"

f4 = tmp / "withnote.pdf"; shutil.copy(a, f4)
doc = PdfDocument(f4)
doc.insert_pdfs(doc.page_count, [str(ftp)], fit_to_page=True)
doc.save(); doc.close()
with fitz.open(str(f4)) as v:
    text = v.load_page(1).get_text()
assert "หมายเหตุแนบท้าย" in text, f"ข้อความ annotation หายหลังปรับขนาด: {text!r}"
print("OK  ข้อความที่เขียนเป็น annotation — ไม่หายหลังปรับขนาด")

# ---- ไฟล์ที่ไม่มี annotation ต้องไม่ถูกแตะต้อง (ไม่เสียเวลา bake) ----
plain = fitz.open()
plain.new_page(width=595, height=842).insert_text((60, 60), "PLAIN", fontsize=14)
pp = tmp / "plain.pdf"; plain.save(str(pp)); plain.close()
assert PdfDocument._baked_copy(fitz.open(str(pp))) is None, "ไม่มี annotation ก็ไม่ต้อง bake"
print("OK  ไฟล์ที่ไม่มี annotation — ข้ามขั้นตอน bake")

print("\nผ่านทั้งหมด")
