"""ทดสอบบันทึกทับไฟล์เดิม — กันบั๊กไฟล์เสีย/หน้าขาว (เจอจริงถึง 1.0.62)

อาการเดิม: รวมไฟล์หลายไฟล์ หรือแทรก/ลบ/หมุน/ย้ายหน้า แล้วกดบันทึกทับไฟล์เดิม
พอทำหลายรอบ ไฟล์จะเสีย — เปิดได้ 0 หน้า หรือมีข้อมูลหน้าเดียวที่เหลือขาวหมด
ต้นเหตุ: ใช้ incremental save (เขียนต่อท้ายไฟล์เดิม) ซึ่งใช้กับการเปลี่ยนโครงสร้างหน้าไม่ได้
"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())


def make(name: str, pages: int, tag: str, scanned: bool = False) -> Path:
    """สร้าง PDF ทดสอบ — scanned=True ทำหน้าเป็นรูปภาพ (เลียนแบบไฟล์สแกนงานจริง)"""
    src = fitz.open()
    for i in range(pages):
        p = src.new_page(width=595, height=842)
        p.insert_text((60, 90), f"{tag} page {i+1}", fontsize=28)
    if not scanned:
        path = tmp / name
        src.save(str(path)); src.close()
        return path
    out = fitz.open()
    for i in range(pages):
        pix = src.load_page(i).get_pixmap(dpi=100)
        pg = out.new_page(width=595, height=842)
        pg.insert_image(pg.rect, pixmap=pix)
    src.close()
    path = tmp / name
    out.save(str(path)); out.close()
    return path


def inspect(path: Path):
    """คืน (จำนวนหน้า, หน้าที่ว่างเปล่าจริงๆ) — เปิดไม่ได้ = (-1, [])"""
    try:
        with fitz.open(str(path)) as d:
            n = d.page_count
            blank = [i + 1 for i in range(n)
                     if not d.load_page(i).get_text().strip()
                     and not d.load_page(i).get_images()
                     and not d.load_page(i).get_drawings()]
        return n, blank
    except Exception:
        return -1, []


# ================= เคสที่เคยพัง: แก้โครงสร้างหน้า + บันทึกทับหลายรอบ =================

base = make("edit.pdf", 6, "DOC", scanned=True)
doc = PdfDocument(base)
steps = [
    ("แทรกหน้าว่าง", lambda d: d.insert_blank_page(1), 7),
    ("ลบหน้า", lambda d: d.delete_pages([0]), 6),
    ("หมุนหน้า", lambda d: d.rotate_pages([0], 90), 6),
    ("ย้ายหน้า", lambda d: d.move_page(0, 2), 6),
    ("ลบอีกหน้า", lambda d: d.delete_pages([5]), 5),
    ("เรียงหน้าใหม่", lambda d: d.reorder_pages([4, 3, 2, 1, 0]), 5),
]
for label, op, expect in steps:
    op(doc)
    doc.save()
    n, _ = inspect(base)
    assert n == expect, f"{label}: ไฟล์บนดิสก์ได้ {n} หน้า ควรได้ {expect}"
    assert doc.page_count == expect, f"{label}: ในหน่วยความจำได้ {doc.page_count} ควร {expect}"
doc.close()
print(f"OK  แก้โครงสร้างหน้า {len(steps)} รอบ บันทึกทับทุกรอบ — ไฟล์ไม่เสีย จำนวนหน้าตรงเสมอ")

# ---- ขนาดไฟล์ต้องหดลงจริงเมื่อลบหน้า (เขียนใหม่ ไม่ใช่ต่อท้าย) ----
shrink = make("shrink.pdf", 10, "S", scanned=True)
before = shrink.stat().st_size
d = PdfDocument(shrink)
d.delete_pages([0, 1, 2, 3, 4, 5, 6])
d.save()
d.close()
after = shrink.stat().st_size
assert after < before * 0.6, f"ลบ 7 จาก 10 หน้า ไฟล์ควรเล็กลงชัดเจน ({before} -> {after})"
# เล็กลงเพราะลบหน้า+บีบอัด ไม่ใช่เพราะเนื้อหาหาย — 3 หน้าที่เหลือต้องยังมีรูปครบ
n_left, blank_left = inspect(shrink)
assert n_left == 3, f"ควรเหลือ 3 หน้า ได้ {n_left}"
assert not blank_left, f"3 หน้าที่เหลือต้องยังมีเนื้อหา ไม่ใช่หน้าขาว ({blank_left})"
with fitz.open(str(shrink)) as v:
    assert all(v.load_page(i).get_images() for i in range(3)), "ทุกหน้าที่เหลือต้องยังมีรูป"
print(f"OK  ลบหน้าแล้วไฟล์เล็กลงจริง ({before//1024} -> {after//1024} KB) "
      "= เขียนใหม่ ไม่ใช่ต่อท้าย · 3 หน้าที่เหลือมีรูปครบ")

# ================= รวมไฟล์หลายไฟล์ แล้วบันทึกทับซ้ำๆ =================

acc = make("acc.pdf", 2, "BASE", scanned=True)
doc = PdfDocument(acc)
expect = 2
for i in range(5):
    doc.insert_pdfs(doc.page_count, [str(make(f"add{i}.pdf", 3, f"ADD{i}", scanned=True))])
    doc.save()
    expect += 3
    n, blank = inspect(acc)
    assert n == expect, f"รวมรอบ {i+1}: ได้ {n} หน้า ควร {expect}"
    assert not blank, f"รวมรอบ {i+1}: มีหน้าขาว {blank}"
doc.close()
print(f"OK  รวมไฟล์ 5 รอบ บันทึกทับทุกรอบ — ได้ {expect} หน้าครบ ไม่มีหน้าขาว")

# ---- รวมไฟล์เยอะๆ ทีเดียว (36 ไฟล์ เหมือนงานจริง) ----
many = [str(make(f"m{i}.pdf", 2, f"M{i}")) for i in range(36)]
big = make("big.pdf", 1, "FIRST")
doc = PdfDocument(big)
doc.insert_pdfs(doc.page_count, many)
doc.save()
doc.close()
n, blank = inspect(big)
assert n == 1 + 36 * 2, f"รวม 36 ไฟล์ ควรได้ {1+36*2} หน้า ได้ {n}"
assert not blank, f"มีหน้าขาว {blank}"
print(f"OK  รวม 36 ไฟล์ทีเดียว = {n} หน้า ไม่มีหน้าขาว (ไม่มีเพดานจำนวนหน้า)")

# ================= เนื้อหาต้องยังอยู่ครบ ไม่ใช่แค่จำนวนหน้าถูก =================

c1 = make("c1.pdf", 3, "ALPHA")
c2 = make("c2.pdf", 3, "BETA")
doc = PdfDocument(c1)
doc.insert_pdfs(doc.page_count, [str(c2)])
doc.delete_pages([0])
doc.save()
doc.close()
with fitz.open(str(c1)) as v:
    texts = [v.load_page(i).get_text().strip() for i in range(v.page_count)]
assert len([t for t in texts if t]) == 5, f"ทุกหน้าต้องมีข้อความ ได้ {texts}"
assert any("ALPHA" in t for t in texts) and any("BETA" in t for t in texts), texts
print(f"OK  เนื้อหายังอยู่ครบทุกหน้าหลังบันทึกทับ ({len(texts)} หน้า)")

# ================= ของลอย (ข้อความ/มาร์กอัป) + บันทึกทับ =================

f1 = make("float.pdf", 3, "F")
doc = PdfDocument(f1)
doc.add_textbox(1, fitz.Rect(100, 100, 300, 130), "ทดสอบข้อความ", font_size=14)
doc.add_annotation(2, "rect", [(50, 50), (200, 150)])
doc.save()
doc.save()          # บันทึกซ้ำอีกรอบ (ตอนนี้ของลอยถูกฝังไปแล้ว)
doc.close()
n, blank = inspect(f1)
assert n == 3 and not blank, f"ได้ {n} หน้า ขาว {blank}"
with fitz.open(str(f1)) as v:
    assert "ทดสอบข้อความ" in v.load_page(1).get_text(), "ข้อความที่ฝังต้องยังอยู่"
    assert v.load_page(2).get_drawings(), "มาร์กอัปต้องยังอยู่"
print("OK  ฝังข้อความ/มาร์กอัป แล้วบันทึกทับซ้ำ — ของยังอยู่ ไฟล์ไม่เสีย")

# ================= undo แล้วบันทึกทับ =================

u = make("undo.pdf", 4, "U")
doc = PdfDocument(u)
doc.delete_pages([0, 1])
doc.undo()
doc.save()
doc.close()
n, _ = inspect(u)
assert n == 4, f"undo แล้วบันทึกควรได้ 4 หน้า ได้ {n}"
print("OK  undo แล้วบันทึกทับ — ได้หน้าครบ")

# ================= ความปลอดภัย: ถ้าเขียนไฟล์ใหม่เสีย ต้องไม่ทับของเดิม =================

safe = make("safe.pdf", 4, "KEEP")
original = safe.read_bytes()
doc = PdfDocument(safe)
doc.insert_blank_page(0)
# จำลองว่าไฟล์ที่เขียนออกมาเสีย (จำนวนหน้าไม่ตรง)
broken = fitz.open()
broken.new_page(width=100, height=100)
real_save = fitz.Document.save          # เก็บของจริงไว้ ไม่งั้น mock เรียกตัวเองวนไม่จบ
with patch.object(fitz.Document, "save",
                  lambda self, p, **k: real_save(broken, str(p))):
    try:
        doc.save()
        raise AssertionError("ควรปฏิเสธการบันทึกเมื่อไฟล์ใหม่ไม่สมบูรณ์")
    except RuntimeError as exc:
        assert "ยกเลิกการบันทึก" in str(exc), str(exc)
broken.close()
assert safe.read_bytes() == original, "ไฟล์เดิมต้องไม่ถูกแตะเมื่อบันทึกไม่สำเร็จ"
assert not safe.with_suffix(".pdf.tmp").exists(), "ต้องเก็บไฟล์ชั่วคราวทิ้ง"
n, _ = inspect(safe)
assert n == 4, f"ไฟล์เดิมต้องยังเปิดได้ 4 หน้า ได้ {n}"
doc.close()
print("OK  เขียนไฟล์ใหม่ไม่สมบูรณ์ -> ไม่ทับไฟล์เดิม (ต้นฉบับปลอดภัย)")

# ================= Save As ยังทำงานปกติ =================

src = make("as1.pdf", 3, "SRC")
doc = PdfDocument(src)
doc.insert_pdfs(doc.page_count, [str(make("as2.pdf", 2, "MORE"))])
out = tmp / "saved-as.pdf"
doc.save(out)
doc.close()
n, blank = inspect(out)
assert n == 5 and not blank, f"Save As ได้ {n} หน้า ขาว {blank}"
assert inspect(src)[0] == 3, "Save As ต้องไม่แตะไฟล์ต้นฉบับ"
print("OK  Save As ได้ครบ และไม่แตะไฟล์ต้นฉบับ")


# ================= ซ่อมไฟล์ที่เสียอยู่แล้วให้อัตโนมัติ =================
# เครื่องที่เคยใช้เวอร์ชัน <= 1.0.62 อาจมีไฟล์เสียค้างอยู่ ต้องเปิดกู้ให้ได้

from app.pdfops import repair_pdf

good = make("tofix.pdf", 5, "FIX")
raw = good.read_bytes()
# ทำ xref เสียแบบเดียวกับที่ incremental save ทำ: ชี้ startxref ไปตำแหน่งผิด
idx = raw.rfind(b"startxref")
broken_bytes = raw[:idx] + b"startxref\n999999999\n%%EOF\n"
brk = tmp / "broken.pdf"
brk.write_bytes(broken_bytes)

with fitz.open(str(brk)) as v:
    damaged_pages = v.page_count
print(f"OK  สร้างไฟล์เสียจำลอง (PyMuPDF เปิดได้ {damaged_pages} หน้า)")

fixed = repair_pdf(brk)
assert fixed is not None, "ต้องซ่อมไฟล์ที่ xref เสียได้"
assert fixed.page_count == 5, f"ซ่อมแล้วควรได้ 5 หน้า ได้ {fixed.page_count}"
fixed.close()
print("OK  ตัวซ่อมกู้ไฟล์ที่ xref เสียได้ครบทุกหน้า")

# ---- เปิดไฟล์ที่ PyMuPDF อ่านไม่ออกเลย (0 หน้า) ต้องเรียกตัวซ่อมให้อัตโนมัติ ----
# จำลองด้วยการทำให้ fitz เปิดได้ 0 หน้า (ไฟล์จริงของผู้ใช้เป็นแบบนี้)
empty = fitz.open()                      # เอกสาร 0 หน้า แทนผลลัพธ์ของไฟล์เสีย
real_open = fitz.open
calls = {"n": 0}


def fake_open(*a, **k):
    """ครั้งแรกคืนเอกสาร 0 หน้า (เหมือนไฟล์เสีย) ครั้งถัดไปทำงานปกติ"""
    calls["n"] += 1
    if calls["n"] == 1:
        return empty
    return real_open(*a, **k)


with patch.object(fitz, "open", side_effect=fake_open):
    doc = PdfDocument(good)              # ไฟล์ดี แต่ถูกทำให้ดูเหมือนเปิดไม่ได้
assert doc.repaired_on_open is True, "เปิดได้ 0 หน้า ต้องเรียกตัวซ่อมอัตโนมัติ"
assert doc.page_count == 5, f"ซ่อมแล้วต้องได้ 5 หน้า ได้ {doc.page_count}"
doc.close()
print("OK  เปิดไฟล์แล้วได้ 0 หน้า -> เรียกตัวซ่อมอัตโนมัติ กู้หน้าคืนได้")

# ---- ซ่อมแล้วบันทึกทับ ไฟล์กลับมาใช้ได้ปกติ (ใช้ไฟล์เสียจริงจาก repair_pdf) ----
fixed = repair_pdf(brk)
assert fixed is not None
out_fixed = tmp / "fixed.pdf"
fixed.save(str(out_fixed), garbage=3, deflate=True)
fixed.close()
n, blank = inspect(out_fixed)
assert n == 5 and not blank, f"ไฟล์ที่ซ่อมแล้วได้ {n} หน้า ขาว {blank}"
with fitz.open(str(out_fixed)) as v:
    assert all(v.load_page(i).get_text().strip() for i in range(5)), "เนื้อหาต้องอยู่ครบ"
print("OK  ไฟล์ที่ซ่อมแล้วบันทึกออกมาใช้ได้ เนื้อหาครบ")

# ไฟล์ปกติต้องไม่ถูกแตะ (ไม่ตั้งธงว่าซ่อม)
normal = PdfDocument(make("normal.pdf", 3, "N"))
assert normal.repaired_on_open is False, "ไฟล์ปกติต้องไม่ถูกซ่อม"
normal.close()
print("OK  ไฟล์ปกติไม่ถูกซ่อมโดยไม่จำเป็น")

print("\nผ่านทั้งหมด")
