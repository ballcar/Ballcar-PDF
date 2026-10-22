"""ทดสอบยางลบ/ปิดทับ (สำหรับไฟล์สแกน) + พิมพ์ข้อความใหม่ทับ"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp / "appdata")

import fitz
from app.pdfops import PdfDocument, Eraser, sample_background_color, find_thai_font

# หน้าจำลอง "ไฟล์สแกน": พื้นครีม (ไม่ขาวสนิท) + ข้อความ
doc = fitz.open()
page = doc.new_page(width=400, height=200)
page.draw_rect(page.rect, color=None, fill=(0.96, 0.95, 0.91), width=0)   # กระดาษสแกนสีครีม
page.insert_text((40, 60), "OLD TEXT 12345", fontsize=18, color=(0, 0, 0))
page.insert_text((40, 120), "KEEP THIS LINE", fontsize=14, color=(0, 0, 0))
src = tmp / "scan.pdf"; doc.save(str(src)); doc.close()

TARGET = fitz.Rect(35, 42, 250, 70)     # กรอบคลุม OLD TEXT


# ---- ดูดสีพื้นหลังได้ใกล้เคียงสีกระดาษ ----
d = PdfDocument(src)
col = sample_background_color(d.doc.load_page(0), TARGET)
assert all(0.85 < c < 1.0 for c in col), f"ควรได้สีครีมใกล้กระดาษ ได้ {col}"
assert abs(col[0] - 0.96) < 0.08 and abs(col[2] - 0.91) < 0.08, f"สีเพี้ยนไป {col}"
print(f"OK  ดูดสีพื้นหลังได้ใกล้สีกระดาษจริง {tuple(round(c,2) for c in col)}")

# ---- เพิ่มยางลบ (auto สี) ----
er = d.add_eraser(0, TARGET)
assert len(d.erasers) == 1 and d.erasers_on(0) == [er]
assert er.color != (1.0, 1.0, 1.0), "auto ต้องไม่ใช่ขาวล้วน (กระดาษเป็นครีม)"
# ยังไม่บันทึก -> ข้อความเดิมยังอยู่ในไฟล์
assert "OLD TEXT" in d.page_text(0), "ยังไม่บันทึก ไม่ควรแตะเอกสารจริง"
print("OK  เพิ่มยางลบเป็นวัตถุลอย (ยังไม่แตะไฟล์)")

# ---- บันทึก -> ข้อความเดิมถูกปิดทับหายไป แต่บรรทัดอื่นอยู่ครบ ----
out = tmp / "erased.pdf"
d.save(out)
with fitz.open(out) as v:
    text = v.load_page(0).get_text()
    assert "OLD TEXT" not in text, "ข้อความที่ปิดทับต้องหายไป"
    assert "KEEP THIS LINE" in text, "บรรทัดอื่นต้องอยู่ครบ"
assert d.erasers == [], "บันทึกแล้ว eraser ต้องถูกฝัง"
print("OK  บันทึกแล้วข้อความที่ปิดทับหายจริง (บรรทัดอื่นอยู่ครบ)")

# ---- สีขาวล้วน (ไม่ auto) ----
d2 = PdfDocument(src)
d2.add_eraser(0, TARGET, color=(1.0, 1.0, 1.0))
assert d2.erasers[0].color == (1.0, 1.0, 1.0)
print("OK  เลือกปิดด้วยสีขาวล้วนได้")

# ---- undo / ลบทีละแผ่น / eraser_at ----
d3 = PdfDocument(src)
e1 = d3.add_eraser(0, TARGET)
assert d3.eraser_at(0, fitz.Point(100, 55)) is e1
assert d3.eraser_at(0, fitz.Point(380, 190)) is None
d3.remove_eraser(e1)
assert d3.erasers == []
d3.undo()
assert len(d3.erasers) == 1, "undo ต้องเอาแผ่นปิดกลับมา"
d3.undo()
assert d3.erasers == [], "undo อีกครั้งต้องกลับไปตอนยังไม่มี"
print("OK  หาแผ่นปิดจากจุดคลิก / ลบ / undo ได้")

# ---- ปิดทับแล้วพิมพ์ใหม่ทับ = ได้ข้อความใหม่ ไม่มีของเก่า ----
d4 = PdfDocument(src)
d4.add_eraser(0, TARGET)
d4.add_textbox(0, fitz.Rect(38, 44, 250, 68), "ข้อความใหม่ 999", font_size=14)
out2 = tmp / "replaced.pdf"
d4.save(out2)
with fitz.open(out2) as v:
    text = v.load_page(0).get_text()
    assert "OLD TEXT" not in text, "ของเก่าต้องหาย"
    assert "ข้อความใหม่ 999" in text, "ของใหม่ต้องอยู่"
print("OK  ลบของเก่า + พิมพ์ใหม่ทับ ได้ผลถูกต้อง")

# ---- flattened() (พิมพ์/ออกรูป) รวมยางลบด้วย ----
d5 = PdfDocument(src)
d5.add_eraser(0, TARGET)
with d5.flattened() as flat:
    assert "OLD TEXT" not in flat.load_page(0).get_text(), "ตอนพิมพ์ต้องเห็นผลการปิดทับด้วย"
assert "OLD TEXT" in d5.page_text(0), "ต้นฉบับต้องไม่ถูกแตะ"
print("OK  พิมพ์/ออกรูป รวมการปิดทับ (ต้นฉบับไม่ถูกแตะ)")

# ============ UI ============
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QMessageBox
from app.main import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
    w.resize(900, 700); w.show()
    return w


# เข้า/ออกโหมด
w = fresh()
w.toggle_erase_mode()
assert w.viewer._erasing and w._erase_bar.isVisible()
w.toggle_erase_mode()
assert not w.viewer._erasing and not w._erase_bar.isVisible()
print("OK  เปิด/ปิดโหมดลบ-ปิดทับ")

# ลากกรอบ -> เกิดแผ่นปิด (ตอบ No ไม่พิมพ์ต่อ)
w = fresh()
w.toggle_erase_mode()
with patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    w._on_erase_dragged(0, TARGET)
assert len(w.doc.erasers) == 1
print("OK  ลากกรอบแล้วได้แผ่นปิด")

# คลิกเฉยๆ บนแผ่นปิด -> เอาออก
w._on_erase_dragged(0, fitz.Rect(100, 55, 101, 56))
assert w.doc.erasers == [], "คลิกที่แผ่นปิดต้องเอาออก"
print("OK  คลิกที่แผ่นปิดเพื่อเอาออก")

# ลากกรอบ + ตอบ Yes -> เด้งกล่องพิมพ์ข้อความ แล้วได้ textbox ตรงตำแหน่งเดิม
w = fresh()
w.toggle_erase_mode()
with patch("app.main.QMessageBox.question", return_value=QMessageBox.Yes), \
     patch.object(w, "_ask_text_content", return_value=("ใหม่ทับเลย", "", False, True)):
    w._on_erase_dragged(0, TARGET)
assert len(w.doc.erasers) == 1
assert len(w.doc.textboxes) == 1 and w.doc.textboxes[0].text == "ใหม่ทับเลย"
assert w.doc.textboxes[0].rect == TARGET, "ข้อความใหม่ควรอยู่ตรงกรอบที่ลบ"
assert not w.viewer._erasing, "พิมพ์ข้อความต่อแล้วควรออกจากโหมดลบ"
print("OK  ลบแล้วพิมพ์ใหม่ต่อทันที (ตำแหน่งเดียวกัน)")

# ล้างแผ่นปิดทั้งหน้า
w = fresh()
w.doc.add_eraser(0, TARGET)
w.doc.add_eraser(0, fitz.Rect(40, 110, 200, 135))
w.clear_erasers_page()
assert w.doc.erasers_on(0) == []
print("OK  ล้างแผ่นปิดทั้งหน้า")

print("\nผ่านทั้งหมด")
