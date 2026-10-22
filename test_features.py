"""ทดสอบ: บีบอัด, ครอบตัด, เซ็นทุกหน้า, สำรองอัตโนมัติ"""
import sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app import autosave
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())


def make_image_pdf(pages=2, big=True):
    """สร้าง PDF ที่มีรูปใหญ่ (บีบได้จริง)"""
    doc = fitz.open()
    # รูปสุ่มขนาดใหญ่ บีบ JPEG ได้เยอะ
    import random
    w = h = 900
    samples = bytes(random.randint(0, 255) for _ in range(w * h * 3))
    pix = fitz.Pixmap(fitz.csRGB, w, h, samples, 0)
    img = pix.tobytes("png")
    for _ in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_image(fitz.Rect(20, 20, 575, 800), stream=img)
    path = tmp / f"img{len(list(tmp.glob('*.pdf')))}.pdf"
    doc.save(str(path)); doc.close()
    return path


# ============ บีบอัด ============
src = make_image_pdf()
d = PdfDocument(src)
out = tmp / "compressed.pdf"
old, new = d.compress(out, image_quality=40, downsample_dpi=90)
assert out.exists()
assert new < old, f"บีบแล้วต้องเล็กลง {old} -> {new}"
# ไฟล์ที่บีบยังเปิดได้ หน้าครบ
chk = fitz.open(out)
assert chk.page_count == 2
chk.close()
print(f"OK  บีบอัด {old//1024}KB -> {new//1024}KB (เล็กลง {100-new*100//old}%)")

# ต้นฉบับไม่ถูกแตะ
assert d.doc.page_count == 2
print("OK  บีบอัดไม่แตะเอกสารที่เปิดอยู่")

# ============ ครอบตัดหน้า ============
doc = fitz.open()
for i in range(3):
    doc.new_page(width=600, height=800)
csrc = tmp / "crop.pdf"; doc.save(str(csrc)); doc.close()

d = PdfDocument(csrc)
# ครอบขอบเข้ามา 10% ทุกด้าน หน้าแรก
d.crop_pages([0], (0.1, 0.1, 0.1, 0.1))
page0 = d.doc.load_page(0)
assert abs(page0.rect.width - 600 * 0.8) < 2, f"กว้างควรเหลือ 480 ได้ {page0.rect.width}"
assert abs(page0.rect.height - 800 * 0.8) < 2
# หน้าอื่นไม่โดน
assert abs(d.doc.load_page(1).rect.width - 600) < 2
print("OK  ครอบตัดหน้าด้วย margins")

# ครอบด้วยกรอบ
d2 = PdfDocument(csrc)
d2.crop_pages_rect([0, 1], fitz.Rect(50, 50, 550, 750))
p = d2.doc.load_page(0)
assert abs(p.rect.width - 500) < 2 and abs(p.rect.height - 700) < 2
print("OK  ครอบตัดด้วยกรอบที่ลาก")

# undo ครอบได้
d2.undo()
assert abs(d2.doc.load_page(0).rect.width - 600) < 2, "undo ครอบต้องคืนขนาดเดิม"
print("OK  undo การครอบได้")

# ============ เซ็นทุกหน้า ============
# ทำรูปลายเซ็นเล็กๆ
sig = tmp / "sig.png"
fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 40)).save(str(sig))
doc = fitz.open()
for i in range(5):
    doc.new_page(width=595, height=842)
ssrc = tmp / "sign.pdf"; doc.save(str(ssrc)); doc.close()

d = PdfDocument(ssrc)
rect = fitz.Rect(400, 750, 550, 800)
n = d.add_stamp_all_pages(str(sig), rect)
assert n == 5, f"ต้องวาง 5 หน้า ได้ {n}"
for i in range(5):
    stamps = d.stamps_on(i)
    assert len(stamps) == 1 and stamps[0].rect == rect, f"หน้า {i+1} ต้องมีลายเซ็นตำแหน่งเดิม"
print("OK  เซ็นทุกหน้าตำแหน่งเดิม (5 หน้า)")

# undo เอาออกหมดในครั้งเดียว
d.undo()
assert all(not d.stamps_on(i) for i in range(5)), "undo ต้องเอาลายเซ็นออกทุกหน้าในครั้งเดียว"
print("OK  undo เซ็นทุกหน้า = ครั้งเดียว")

# เฉพาะบางหน้า
d.add_stamp_all_pages(str(sig), rect, indexes=[0, 2, 4])
assert d.stamps_on(1) == [] and len(d.stamps_on(2)) == 1
print("OK  เซ็นเฉพาะหน้าที่เลือกได้")

# บันทึกแล้วฝังจริงทุกหน้า
out = tmp / "signed.pdf"
d.save(out)
with fitz.open(out) as v:
    assert v.load_page(0).get_images() and v.load_page(4).get_images()
print("OK  บันทึกแล้วลายเซ็นฝังจริง")

# ============ สำรองอัตโนมัติ (recovery) ============
import os
os.environ["APPDATA"] = str(tmp / "appdata")

sid = "sess1"
# ยังไม่มีงานค้าง
for r in autosave.pending_recoveries():
    autosave.discard_recovery(r["meta_path"])
assert autosave.pending_recoveries() == []

d = PdfDocument(csrc)
d.crop_pages([0], (0.1, 0.1, 0.1, 0.1))    # ทำให้ dirty
autosave.write_recovery(d.doc.tobytes(), str(csrc), sid)
pend = autosave.pending_recoveries()
assert len(pend) == 1, f"ต้องมีงานค้าง 1 ได้ {len(pend)}"
assert pend[0]["original"] == str(csrc)
# ไฟล์กู้คืนเปิดได้ และมีการครอบไว้จริง
rec = fitz.open(pend[0]["pdf_path"])
assert abs(rec.load_page(0).rect.width - 480) < 2, "ไฟล์กู้คืนต้องเก็บงานที่ค้างไว้"
rec.close()
print("OK  เขียนไฟล์กู้คืน + อ่านกลับได้")

# บันทึกจริงแล้วเคลียร์
autosave.clear_recovery(str(csrc), sid)
assert autosave.pending_recoveries() == [], "บันทึกแล้วต้องเคลียร์งานค้าง"
print("OK  เคลียร์ไฟล์กู้คืนหลังบันทึก")

# ทิ้งงานค้าง
autosave.write_recovery(d.doc.tobytes(), str(csrc), sid)
autosave.discard_recovery(autosave.pending_recoveries()[0]["meta_path"])
assert autosave.pending_recoveries() == []
print("OK  ทิ้งงานค้างได้")

print("\nผ่านทั้งหมด")
