"""ทดสอบเลือกฟอนต์ตอนเพิ่ม/แก้ข้อความ"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app import pdfops
from app.pdfops import (PdfDocument, TextBox, available_fonts, default_font_key,
                        font_by_key, resolve_font, draw_textbox, render_textbox_bitmap)

tmp = Path(tempfile.mkdtemp())
doc = fitz.open(); doc.new_page(width=595, height=842); src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

fonts = available_fonts()
assert fonts, "ต้องเจอฟอนต์อย่างน้อย 1 ตัว"
assert all("key" in f and "regular" in f and Path(f["regular"]).exists() for f in fonts)
print(f"OK  เจอฟอนต์ {len(fonts)} ตัว:", ", ".join(f["name"] for f in fonts))

# ค่าเริ่มต้นต้องเป็นฟอนต์ไทย
dk = default_font_key()
assert font_by_key(dk)["thai"], "ฟอนต์เริ่มต้นต้องรองรับไทย"
print(f"OK  ฟอนต์เริ่มต้น = {font_by_key(dk)['name']} (รองรับไทย)")

# ---- resolve_font: ไทยในฟอนต์อังกฤษ -> สลับเป็นฟอนต์ไทยให้ ----
latin = next((f for f in fonts if not f["thai"]), None)
if latin:
    tag, ffile = resolve_font(latin["key"], False, "สวัสดีไทย")
    resolved = None
    for f in fonts:
        if f["regular"] == ffile or f["bold"] == ffile:
            resolved = f
    assert resolved and resolved["thai"], "ข้อความไทยในฟอนต์อังกฤษต้องถูกสลับเป็นฟอนต์ไทย"
    print("OK  ไทยในฟอนต์อังกฤษ -> สลับเป็นฟอนต์ไทยอัตโนมัติ (ตัวหนังสือไม่หาย)")

# ---- ฟอนต์ต่างกัน -> ภาพต่างกัน ----
thai_fonts = [f for f in fonts if f["thai"]]
if len(thai_fonts) >= 2:
    b1 = TextBox(0, fitz.Rect(0, 0, 300, 40), "ทดสอบ ABC", font_size=20, font=thai_fonts[0]["key"])
    b2 = TextBox(0, fitz.Rect(0, 0, 300, 40), "ทดสอบ ABC", font_size=20, font=thai_fonts[1]["key"])
    import hashlib
    h1 = hashlib.md5(render_textbox_bitmap(b1, 2.0).samples).hexdigest()
    h2 = hashlib.md5(render_textbox_bitmap(b2, 2.0).samples).hexdigest()
    assert h1 != h2, "ฟอนต์ต่างกันภาพต้องต่างกัน"
    print(f"OK  เลือกฟอนต์ต่างกันได้ผลต่างกัน ({thai_fonts[0]['name']} vs {thai_fonts[1]['name']})")

# ---- ตัวหนา -> ภาพต่างจากปกติ (ถ้ามีไฟล์ bold) ----
bold_font = next((f for f in fonts if f["bold"]), None)
if bold_font:
    import hashlib
    reg = TextBox(0, fitz.Rect(0, 0, 300, 40), "Bold Test", font_size=20, font=bold_font["key"])
    bld = TextBox(0, fitz.Rect(0, 0, 300, 40), "Bold Test", font_size=20,
                  font=bold_font["key"], bold=True)
    hr = hashlib.md5(render_textbox_bitmap(reg, 2.0).samples).hexdigest()
    hb = hashlib.md5(render_textbox_bitmap(bld, 2.0).samples).hexdigest()
    assert hr != hb, "ตัวหนาต้องต่างจากปกติ"
    print(f"OK  ตัวหนาทำงาน ({bold_font['name']})")

# ---- font/bold เก็บใน TextBox + copy + บันทึกฝังถูก ----
d = PdfDocument(src)
f = thai_fonts[0]["key"] if thai_fonts else fonts[0]["key"]
box = d.add_textbox(0, fitz.Rect(60, 100, 400, 140), "ข้อความมีฟอนต์", font_size=18,
                    font=f, bold=True)
assert box.font == f and box.bold is True
assert box.copy().font == f and box.copy().bold is True
d.update_textbox_content(box, font=fonts[-1]["key"], bold=False)
assert box.font == fonts[-1]["key"] and box.bold is False
# undo คืนค่าฟอนต์เดิม (undo สร้าง TextBox copy ใหม่ ต้องดูจาก doc)
d.undo()
restored = d.textboxes[0]
assert restored.font == f and restored.bold is True, "undo ต้องคืนฟอนต์/ตัวหนาเดิม"
print("OK  เก็บฟอนต์/ตัวหนาใน TextBox + undo ได้")

out = tmp / "saved.pdf"
d.save(out)
with fitz.open(out) as v:
    assert "ข้อความมีฟอนต์" in v.load_page(0).get_text(), "บันทึกแล้วข้อความต้องอยู่"
print("OK  บันทึกแล้วข้อความ (มีฟอนต์เลือกเอง) ฝังลงไฟล์")

# ---- auto (font="") ยังทำงานเหมือนเดิม ----
d2 = PdfDocument(src)
box2 = d2.add_textbox(0, fitz.Rect(60, 100, 400, 140), "auto ไทย", font_size=16)
assert box2.font == ""
o2 = tmp / "auto.pdf"; d2.save(o2)
with fitz.open(o2) as v:
    assert "auto ไทย" in v.load_page(0).get_text()
print("OK  โหมด auto (ไม่เลือกฟอนต์) ยังทำงานเหมือนเดิม")

print("\nผ่านทั้งหมด")


# ============ UI: font picker ============
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QCheckBox
from app.main import MainWindow

_app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow()
w.doc = PdfDocument(src); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)

# _ask_text_content คืน 4 ค่า และเลือกฟอนต์/ตัวหนาได้
pick = fonts[1]["key"]
def fill(dlg):
    from PySide6.QtWidgets import QPlainTextEdit
    dlg.findChild(QPlainTextEdit).setPlainText("มีฟอนต์")
    combo = [c for c in dlg.findChildren(QComboBox)][0]  # ตัวแรก = ฟอนต์
    combo.setCurrentIndex(combo.findData(pick))
    dlg.findChild(QCheckBox).setChecked(True)   # ตัวหนา
with patch.object(QDialog, "exec", lambda self: (fill(self), QDialog.Accepted)[1]):
    text, font_key, bold, ok = w._ask_text_content("t", "")
assert ok and text == "มีฟอนต์" and font_key == pick and bold is True, (text, font_key, bold, ok)
print("OK  UI เลือกฟอนต์ + ตัวหนา ผ่าน _ask_text_content")

# เพิ่มข้อความผ่าน point pick แล้วกล่องได้ฟอนต์ที่เลือก
with patch.object(w, "_ask_text_content", return_value=("ใหม่", pick, True, True)):
    w._on_point_picked(0, 100, 150)
b = w.doc.textboxes[-1]
assert b.font == pick and b.bold is True, (b.font, b.bold)
print("OK  เพิ่มข้อความแล้วกล่องเก็บฟอนต์/ตัวหนาที่เลือก")

print("\nผ่านทั้งหมด (รวม UI)")
