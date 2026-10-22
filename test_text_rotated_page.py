"""ทดสอบพิมพ์ข้อความลงหน้าที่ถูกหมุน (ไฟล์สแกน) — กันบั๊ก "วันที่เพี้ยน"

อาการเดิม (ถึง 1.0.63): หน้าสแกนที่มี /Rotate 90 หรือ 270 พอพิมพ์วันที่ลงช่อง
แล้วบันทึก เปิดใหม่ข้อความจะถูกหั่นเป็นท่อนเรียงลงมาแนวตั้ง
เช่น "25/08/2026" -> "25" / "08" / "202" / "6"
ต้นเหตุ: กรอบที่กว้างในมุมมองจริง กลายเป็นกรอบสูงแคบในพิกัดดิบ แล้ว insert_textbox ตัดบรรทัด
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
DATE = "25/08/2026"


def page_with_rotation(rot: int, name: str) -> Path:
    d = fitz.open()
    p = d.new_page(width=595, height=842)
    p.insert_text((60, 60), "FORM", fontsize=14)
    p.set_rotation(rot)
    path = tmp / name
    d.save(str(path)); d.close()
    return path


def added_lines(path: Path, page: int, needle: str) -> list[str]:
    """บรรทัดข้อความที่เกี่ยวกับ needle ในหน้านั้น"""
    with fitz.open(str(path)) as v:
        out = []
        for blk in v.load_page(page).get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                t = "".join(s["text"] for s in ln["spans"]).strip()
                if t and (t in needle or needle in t):
                    out.append(t)
    return out


def ink_box(path: Path, page: int, clip=None):
    """กรอบหมึกในภาพที่ 'เห็นจริง' (รวมการหมุนแล้ว) — กว้าง>สูง = อ่านหงายปกติ

    clip = ดูเฉพาะบริเวณที่วางข้อความ จะได้ไม่ปนกับข้อความอื่นบนหน้า
    """
    with fitz.open(str(path)) as v:
        px = v.load_page(page).get_pixmap(dpi=70, clip=clip)
    pts = [(x, y) for y in range(px.height) for x in range(px.width)
           if sum(px.pixel(x, y)) < 400]
    if not pts:
        return (0, 0)
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    return (max(xs) - min(xs), max(ys) - min(ys))


# ---- พิมพ์วันที่ลงหน้าทุกมุมหมุน แล้วบันทึก ต้องได้บรรทัดเดียวและอ่านหงาย ----
for rot in (0, 90, 180, 270):
    f = page_with_rotation(rot, f"rot{rot}.pdf")
    doc = PdfDocument(f)
    disp = doc.doc.load_page(0).rect          # ขนาดที่ผู้ใช้เห็นบนจอ
    # ช่องวันที่แนวนอน (กว้าง 170 สูง 26) เหมือนที่ผู้ใช้ลากจริง
    spot = fitz.Rect(disp.width * 0.3, disp.height * 0.5,
                     disp.width * 0.3 + 170, disp.height * 0.5 + 26)
    doc.add_textbox(0, spot, DATE, font_size=14)
    doc.save()
    doc.close()

    lines = added_lines(f, 0, DATE)
    assert lines == [DATE], f"หน้าหมุน {rot}°: ข้อความถูกหั่น -> {lines}"
    w, h = ink_box(f, 0, clip=spot)
    assert w > h, f"หน้าหมุน {rot}°: ข้อความตะแคง (กรอบหมึก {w}x{h})"
print("OK  พิมพ์วันที่ลงหน้าหมุน 0/90/180/270 — ได้บรรทัดเดียว อ่านหงายทุกมุม")

# ---- ข้อความไทยบนหน้าหมุนก็ต้องไม่เพี้ยน ----
f = page_with_rotation(270, "tha.pdf")
doc = PdfDocument(f)
disp = doc.doc.load_page(0).rect
tha_spot = fitz.Rect(60, disp.height * 0.4, 60 + 260, disp.height * 0.4 + 30)
doc.add_textbox(0, tha_spot, "วันที่ 25 สิงหาคม", font_size=15)
doc.save(); doc.close()
with fitz.open(str(f)) as v:
    got = v.load_page(0).get_text()
assert "วันที่" in got, f"ข้อความไทยหาย: {got!r}"
w, h = ink_box(f, 0, clip=tha_spot)
assert w > h, f"ข้อความไทยตะแคง ({w}x{h})"
print("OK  ข้อความไทยบนหน้าหมุน — ไม่เพี้ยน อ่านหงาย")

# ---- ข้อความยาวที่ต้องตัดหลายบรรทัด ต้องยังเรียงถูกทิศ ----
f = page_with_rotation(90, "wrap.pdf")
doc = PdfDocument(f)
disp = doc.doc.load_page(0).rect
long_text = "บรรทัดหนึ่งยาวพอสมควร บรรทัดสองต่อจากนี้ บรรทัดสามปิดท้าย"
wrap_spot = fitz.Rect(50, 50, 50 + 200, 50 + 120)
doc.add_textbox(0, wrap_spot, long_text, font_size=12)
doc.save(); doc.close()
with fitz.open(str(f)) as v:
    pg = v.load_page(0)
    # ดูเฉพาะบรรทัดของข้อความที่เราเพิ่ง วาง (ข้อความเดิมบนหน้ามีทิศของมันเอง)
    dirs = {tuple(round(x) for x in ln["dir"])
            for blk in pg.get_text("dict")["blocks"] for ln in blk.get("lines", [])
            if any(w in "".join(sp["text"] for sp in ln["spans"]) for w in ("บรรทัด", "ปิดท้าย"))}
    text = pg.get_text()
assert "บรรทัดหนึ่ง" in text and "ปิดท้าย" in text, f"ข้อความหาย: {text!r}"
# ทุกบรรทัดต้องไปทางเดียวกัน (ถ้าทิศปนกัน แปลว่าตัดบรรทัดผิดแนว)
assert len(dirs) == 1, f"บรรทัดไปคนละทิศ: {dirs}"
w, h = ink_box(f, 0, clip=wrap_spot)
assert w > h, f"ข้อความยาวตะแคง ({w}x{h})"
print("OK  ข้อความยาวหลายบรรทัดบนหน้าหมุน — เรียงทิศเดียวกัน อ่านหงาย ครบถ้วน")

# ---- วางหลายหน้าที่มุมหมุนต่างกันในไฟล์เดียว (เหมือนไฟล์สแกนจริง) ----
mix = fitz.open()
for i in range(4):
    p = mix.new_page(width=595, height=842)
    p.insert_text((60, 60), f"P{i+1}", fontsize=12)
    p.set_rotation([0, 270, 0, 270][i])
mixed = tmp / "mixed.pdf"
mix.save(str(mixed)); mix.close()

doc = PdfDocument(mixed)
for i in range(4):
    disp = doc.doc.load_page(i).rect
    doc.add_textbox(i, fitz.Rect(disp.width * 0.35, disp.height * 0.55,
                                 disp.width * 0.35 + 170, disp.height * 0.55 + 26),
                    DATE, font_size=14)
doc.save(); doc.close()
for i in range(4):
    lines = added_lines(mixed, i, DATE)
    assert lines == [DATE], f"หน้า {i+1}: {lines}"
print("OK  ไฟล์ที่มีหน้าหมุนสลับกัน — ทุกหน้าได้วันที่ถูกต้อง")

# ---- แก้ข้อความเดิมบนหน้าหมุน แล้วบันทึกซ้ำ ----
f = page_with_rotation(270, "edit.pdf")
doc = PdfDocument(f)
disp = doc.doc.load_page(0).rect
box = doc.add_textbox(0, fitz.Rect(60, disp.height * 0.5, 60 + 180, disp.height * 0.5 + 26),
                      "01/01/2026", font_size=14)
doc.update_textbox_content(box, text=DATE)
doc.save(); doc.close()
assert added_lines(f, 0, DATE) == [DATE], "แก้ข้อความแล้วต้องยังถูกต้อง"
print("OK  แก้ข้อความบนหน้าหมุน แล้วบันทึก — ยังถูกต้อง")

print("\nผ่านทั้งหมด")
