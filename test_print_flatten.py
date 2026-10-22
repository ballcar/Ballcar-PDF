"""ทดสอบว่าพิมพ์/ออกรูป รวมข้อความ-ลายเซ็น-ลายน้ำที่ยังไม่บันทึกด้วย
และตัวอย่างบนจอตรงกับผลจริง
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from app.pdfops import PdfDocument, TextBox, find_thai_font, render_textbox_bitmap

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(2):
    doc.new_page(width=595, height=842).insert_text((72, 60), f"original {i+1}")
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

TEXT = "299/185 หมู่4 ตำบลบางเดื่อ ปทุมธานี"


# ---- flattened() รวมข้อความที่เพิ่มไว้ ----
d = PdfDocument(src)
d.add_textbox(0, fitz.Rect(60, 300, 500, 340), TEXT, font_size=14)
# เอกสารจริงยังไม่มี (ยังไม่บันทึก)
assert TEXT not in d.page_text(0)
with d.flattened() as flat:
    assert TEXT in flat.load_page(0).get_text(), "สำเนาสำหรับพิมพ์ต้องมีข้อความที่เพิ่มไว้"
    assert "original 1" in flat.load_page(0).get_text(), "เนื้อหาเดิมต้องยังอยู่"
# ต้นฉบับไม่ถูกแตะ
assert TEXT not in d.page_text(0), "flattened() ต้องไม่แก้เอกสารต้นฉบับ"
assert len(d.textboxes) == 1, "วัตถุลอยต้องยังอยู่ แก้ต่อได้"
print("OK  flattened() รวมข้อความที่เพิ่ม โดยไม่แตะต้นฉบับ")

# ---- รวมลายน้ำด้วย ----
d.set_watermark("สำเนา")
with d.flattened() as flat:
    text = flat.load_page(0).get_text()
    assert "สำเนา" in text and TEXT in text
print("OK  flattened() รวมลายน้ำด้วย")

# ---- ไม่มีวัตถุลอย -> ใช้ตัวจริง ไม่เสียเวลาสำเนา ----
plain = PdfDocument(src)
with plain.flattened() as flat:
    assert flat is plain.doc, "ไม่มีวัตถุลอยควรใช้เอกสารเดิมเลย"
print("OK  ไม่มีวัตถุลอย ไม่ต้องสำเนา")

# ---- บันทึกเป็นรูป ต้องมีข้อความที่เพิ่มไว้ ----
d2 = PdfDocument(src)
d2.add_textbox(0, fitz.Rect(60, 300, 500, 340), TEXT, font_size=14)
folder = tmp / "imgs"
files = d2.export_images([0], folder, dpi=100, fmt="png")
assert files and files[0].exists()
# เทียบกับรูปที่ไม่มีข้อความ -> ต้องต่างกัน (มีหมึกเพิ่ม)
plain2 = PdfDocument(src)
plain_files = plain2.export_images([0], tmp / "imgs_plain", dpi=100, fmt="png")
from PIL import Image
import numpy as np
a = np.asarray(Image.open(files[0]).convert("L"))
b = np.asarray(Image.open(plain_files[0]).convert("L"))
ink_with = int((a < 200).sum())
ink_without = int((b < 200).sum())
assert ink_with > ink_without + 100, f"รูปต้องมีข้อความเพิ่ม (หมึก {ink_without} -> {ink_with})"
print(f"OK  บันทึกเป็นรูป มีข้อความที่เพิ่ม (หมึก {ink_without} -> {ink_with})")

# ---- ตัวอย่างบนจอ ใช้เอนจินเดียวกับผลจริง ----
box = TextBox(page=0, rect=fitz.Rect(0, 0, 300, 40), text=TEXT, font_size=14)
preview = render_textbox_bitmap(box, 1.0)
assert preview.alpha, "ตัวอย่างต้องพื้นหลังโปร่งใส"
assert preview.pixel(preview.width - 1, preview.height - 1)[3] == 0, "มุมต้องโปร่งใส"

# วาดกล่องเดียวกันลงหน้าจริง แล้วเทียบว่าหมึกตกที่แถวเดียวกัน
page_doc = fitz.open()
pg = page_doc.new_page(width=300, height=300)
from app.pdfops import draw_textbox
draw_textbox(pg, TextBox(page=0, rect=fitz.Rect(0, 0, 300, 40), text=TEXT, font_size=14))
real = pg.get_pixmap(matrix=fitz.Matrix(1, 1))
page_doc.close()


def ink_rows(pix, w, h, alpha):
    rows = []
    for y in range(min(h, 60)):
        n = 0
        for x in range(w):
            p = pix.pixel(x, y)
            dark = (p[3] > 0 and sum(p[:3]) < 600) if alpha else (sum(p[:3]) < 600)
            if dark:
                n += 1
        rows.append(n)
    return rows


pv = ink_rows(preview, 300, preview.height, True)
rl = ink_rows(real, 300, real.height, False)
first_pv = next((i for i, n in enumerate(pv) if n > 0), -1)
first_rl = next((i for i, n in enumerate(rl) if n > 0), -1)
assert first_pv >= 0 and first_rl >= 0, "ต้องมีหมึกทั้งคู่"
assert abs(first_pv - first_rl) <= 1, \
    f"ตัวอย่างกับผลจริงต้องเริ่มบรรทัดแถวเดียวกัน (จอ {first_pv} vs จริง {first_rl})"
print(f"OK  ตัวอย่างบนจอตรงกับผลจริง (เริ่มแถวที่ {first_pv} เท่ากัน)")

print("\nผ่านทั้งหมด")


# ---- overlay ตอนแก้ไข: รูปต้องสูงเท่ากล่อง (ไม่เผื่อ 6 บรรทัด) กันตัวอักษรถูกบีบแบน ----
import fitz as _fitz
from app.pdfops import render_textbox_bitmap as _rtb
_box = TextBox(page=0, rect=_fitz.Rect(0, 0, 400, 22), text="ทดสอบข้อความยาว "*3, font_size=13)
_overflow = _rtb(_box, 1.0, overflow=True).height
_exact = _rtb(_box, 1.0, overflow=False).height
assert _exact <= 24, f"overflow=False ต้องสูงเท่ากล่อง (~22) ได้ {_exact}"
assert _overflow > _exact + 50, "overflow=True ต้องเผื่อความสูงไว้โชว์ส่วนล้น"
print(f"OK  overlay ใช้รูปพอดีกล่อง ({_exact}px) ไม่ใช่รูปเผื่อล้น ({_overflow}px) -> ไม่บีบแบน")

print("\nผ่านทั้งหมด (รวม overlay)")
