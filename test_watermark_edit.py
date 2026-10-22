"""ทดสอบลายน้ำแบบแก้ไขได้ (วัตถุลอย ปรับได้จนกว่าจะบันทึก)"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app.pdfops import PdfDocument, Watermark

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(3):
    doc.new_page(width=595, height=842).insert_text((72, 72), f"page {i+1}")
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()


# ---- ตั้งลายน้ำ = ยังไม่ฝังลงไฟล์ ----
d = PdfDocument(src)
d.set_watermark("สำเนา")
assert d.watermark is not None and d.watermark.text == "สำเนา"
# ยังไม่บันทึก -> ในเอกสารยังไม่มีข้อความลายน้ำ
assert "สำเนา" not in d.page_text(0), "ยังไม่บันทึก ไม่ควรฝังลงไฟล์"
print("OK  ตั้งลายน้ำแล้วยังไม่ฝังลงไฟล์ (ยังแก้ได้)")

# ---- แก้ไขค่าได้ ----
d.update_watermark(text="ตัวอย่าง", opacity=0.4, angle=30.0)
assert d.watermark.text == "ตัวอย่าง"
assert abs(d.watermark.opacity - 0.4) < 1e-6
assert abs(d.watermark.angle - 30.0) < 1e-6
print("OK  แก้ข้อความ/ความเข้ม/องศาได้")

# ---- แก้สีและขนาด ----
d.update_watermark(color=(1.0, 0.0, 0.0), font_size=100.0)
assert d.watermark.color == (1.0, 0.0, 0.0) and d.watermark.font_size == 100.0
print("OK  แก้สี/ขนาดได้")

# ---- geometry คำนวณได้ + ขนาดตายตัวมีผลจริง ----
geo = d.watermark_geometry(0)
assert geo is not None
cx, cy, size, width = geo
assert abs(size - 100.0) < 1e-6, f"ขนาดต้องเป็น 100 ได้ {size}"
assert cx > 0 and cy > 0 and width > 0
# auto size -> คำนวณเอง
d.update_watermark(font_size=None)
auto_size = d.watermark_geometry(0)[2]
assert auto_size != 100.0 and auto_size > 8
print(f"OK  คำนวณตำแหน่ง/ขนาด (auto={auto_size:.0f})")

# ---- undo กลับค่าเดิมได้ ----
d.update_watermark(text="ก่อนย้อน")
assert d.watermark.text == "ก่อนย้อน"
d.undo()
assert d.watermark.text == "ตัวอย่าง", f"undo ต้องได้ข้อความเดิม ได้ {d.watermark.text}"
print("OK  undo การแก้ลายน้ำได้")

# ---- ลบลายน้ำ + undo เอากลับ ----
assert d.remove_watermark() is True
assert d.watermark is None
d.undo()
assert d.watermark is not None and d.watermark.text == "ตัวอย่าง"
print("OK  ลบลายน้ำ + undo เอากลับได้")

# ---- บันทึก = ฝังลงไฟล์จริง ----
d2 = PdfDocument(src)
d2.set_watermark("ลับมาก")
out = tmp / "wm.pdf"
d2.save(out)
with fitz.open(out) as v:
    for i in range(3):
        assert "ลับมาก" in v.load_page(i).get_text(), f"หน้า {i+1} ต้องมีลายน้ำ"
assert d2.watermark is None, "บันทึกแล้วลายน้ำต้องถูกฝัง (ไม่ลอยแล้ว)"
print("OK  บันทึกแล้วฝังลงไฟล์ทุกหน้า")

# ---- เฉพาะบางหน้า ----
d3 = PdfDocument(src)
d3.set_watermark("เฉพาะหน้า2", indexes=[1])
assert d3.watermark_geometry(0) is None, "หน้า 1 ไม่ควรมีลายน้ำ"
assert d3.watermark_geometry(1) is not None
out2 = tmp / "wm2.pdf"
d3.save(out2)
with fitz.open(out2) as v:
    assert "เฉพาะหน้า2" not in v.load_page(0).get_text()
    assert "เฉพาะหน้า2" in v.load_page(1).get_text()
    assert "เฉพาะหน้า2" not in v.load_page(2).get_text()
print("OK  ใส่เฉพาะหน้าที่เลือกได้")

# ---- ตั้งซ้ำ = แทนที่ของเดิม ไม่ซ้อน ----
d4 = PdfDocument(src)
d4.set_watermark("แรก")
d4.set_watermark("สอง")
assert d4.watermark.text == "สอง"
out3 = tmp / "wm3.pdf"; d4.save(out3)
with fitz.open(out3) as v:
    text = v.load_page(0).get_text()
    assert "สอง" in text and "แรก" not in text, "ตั้งใหม่ต้องแทนที่ ไม่ซ้อนทับ"
print("OK  ตั้งลายน้ำซ้ำ = แทนที่ ไม่ซ้อนกัน")

# ---- ข้อความว่าง -> error ----
d5 = PdfDocument(src)
try:
    d5.set_watermark("   ")
except ValueError:
    print("OK  ข้อความว่างแจ้ง error")
else:
    raise AssertionError("ควร error")

print("\nผ่านทั้งหมด")
