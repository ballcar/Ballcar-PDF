"""ทดสอบหน้าที่ถูกหมุนไว้ (/Rotate 90/180/270 — ไฟล์สแกนแนวนอนเจอบ่อย)

บันทึกแล้วลายเซ็น/รูป/ตรายาง/ลายน้ำรูป ต้องตั้งตรงตามที่เห็นบนจอ (เคยตะแคง 90°)
และเลขหน้า/ลายน้ำข้อความต้องอยู่บนหน้า อ่านได้แนวนอน (เคยหลุดหน้าหายไป)
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
# รูปทดสอบไม่สมมาตร: ครึ่งซ้ายแดง ครึ่งขวาน้ำเงิน (ตะแคง/กลับหัวแล้วจะรู้ทันที)
pm = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 100), False)
pm.set_rect(fitz.IRect(0, 0, 100, 100), (255, 0, 0))
pm.set_rect(fitz.IRect(100, 0, 200, 100), (0, 0, 255))
img = tmp / "lr.png"
pm.save(str(img))
want = fitz.Rect(100, 150, 300, 250)          # บนจอ: กว้าง 200 สูง 100


def make(rot: int) -> Path:
    d = fitz.open()
    p = d.new_page(width=842, height=595) if rot in (90, 270) else d.new_page()
    p.set_rotation(rot)
    path = tmp / f"rot{rot}.pdf"
    d.save(str(path)); d.close()
    return path


def upright(path: Path, page: int = 0) -> bool:
    pix = fitz.open(str(path))[page].get_pixmap()          # ภาพหน้าตามที่ผู้ใช้เห็น
    left, right = pix.pixel(130, 200), pix.pixel(270, 200)
    return left[0] > 200 and left[2] < 80 and right[2] > 200 and right[0] < 80


for rot in (0, 90, 180, 270):
    src = make(rot)
    doc = PdfDocument(src)
    doc.add_stamp(0, img, want)                              # ลายเซ็น/ตรายาง (ฝังตอนบันทึก)
    out = tmp / f"stamp{rot}.pdf"; doc.save(out)
    assert upright(out), f"ลายเซ็นบนหน้าหมุน {rot}° ต้องตั้งตรง"
    doc = PdfDocument(src)
    doc.add_image(0, img, want)                              # แทรกรูปภาพ
    out = tmp / f"image{rot}.pdf"; doc.save(out)
    assert upright(out), f"รูปบนหน้าหมุน {rot}° ต้องตั้งตรง"
print("OK  ลายเซ็น/ตรายาง/รูป บนหน้าที่หมุน 0/90/180/270° บันทึกแล้วตั้งตรงตามที่วาง")


def text_lines(path: Path):
    page = fitz.open(str(path))[0]
    m = page.rotation_matrix
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            dx, dy = line["dir"]
            text = "".join(s["text"] for s in line["spans"])
            out.append((text, (round(dx * m.a + dy * m.c, 2), round(dx * m.b + dy * m.d, 2)),
                        fitz.Rect(line["bbox"]) * m, page.rect))
    return out


for rot in (0, 90, 180, 270):
    doc = PdfDocument(make(rot))
    doc.add_page_numbers(fmt="{page} / {total}", position="bottom-center")
    out = tmp / f"num{rot}.pdf"; doc.save(out)
    lines = text_lines(out)
    assert lines, f"หน้าหมุน {rot}°: เลขหน้าหายไป"
    text, direction, box, view = lines[0]
    assert text.strip() == "1 / 1" and direction == (1.0, 0.0), (rot, lines)
    assert box.y0 > view.height * 0.85 and abs(box.x0 + box.width / 2 - view.width / 2) < 30, \
        f"หน้าหมุน {rot}°: เลขหน้าต้องอยู่ล่างกึ่งกลางของหน้าที่เห็น ได้ {box}"
print("OK  เลขหน้าบนหน้าที่หมุน 0/90/180/270° อยู่ล่างกึ่งกลาง อ่านแนวนอน")

for rot in (0, 90, 270):
    doc = PdfDocument(make(rot))
    doc.set_watermark("CONFIDENTIAL")              # ลายน้ำแบบแก้ได้ (ฝังตอนบันทึก)
    out = tmp / f"wm{rot}.pdf"; doc.save(out)
    lines = text_lines(out)
    assert lines, f"หน้าหมุน {rot}°: ลายน้ำหายไป"
    text, direction, box, view = lines[0]
    assert view.contains(box.tl) and view.contains(box.br), f"หน้าหมุน {rot}°: ลายน้ำต้องอยู่ในหน้า"
    assert abs(box.x0 + box.width / 2 - view.width / 2) < 20 and abs(box.y0 + box.height / 2 - view.height / 2) < 20
    if rot == 0:
        ref = direction
    assert direction == ref, f"หน้าหมุน {rot}°: ลายน้ำต้องเอียงแบบเดียวกับหน้าปกติ"
print("OK  ลายน้ำข้อความบนหน้าที่หมุน อยู่กลางหน้า เอียงเหมือนหน้าปกติ")

print("\nผ่านทั้งหมด")
