"""ทดสอบ UI แก้ไขลายน้ำ (dialog ปรับค่า + ตัวอย่างสด)"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox,
                               QLineEdit, QSlider, QSpinBox)
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(3):
    doc.new_page(width=595, height=842).insert_text((72, 72), f"page {i+1}")
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

app = QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
    return w


def find_dialog():
    dlgs = [x for x in app.topLevelWidgets() if isinstance(x, QDialog) and x.isVisible()]
    return dlgs[-1] if dlgs else None


def drive(fill, result=QDialog.Accepted):
    """แทน exec ด้วยการกรอกค่าลงใน dialog แล้วปิดด้วยผลที่ต้องการ"""
    def fake_exec(dlg=None):
        d = dlg if isinstance(dlg, QDialog) else find_dialog()
        if d is None:
            d = [x for x in app.topLevelWidgets() if isinstance(x, QDialog)][-1]
        fill(d)
        return result
    return fake_exec


# ---- เพิ่มลายน้ำผ่าน dialog ----
w = fresh()
def fill_new(d):
    d.findChild(QLineEdit).setText("สำเนา")
    sliders = d.findChildren(QSlider)
    sliders[0].setValue(35)     # ความเข้ม
    sliders[1].setValue(30)     # องศา
with patch("app.main.QInputDialog.getItem", return_value=("ทุกหน้า (3 หน้า)", True)), \
     patch.object(QDialog, "exec", drive(fill_new)):
    w.watermark_dialog()
wm = w.doc.watermark
assert wm is not None and wm.text == "สำเนา", wm
assert abs(wm.opacity - 0.35) < 1e-6, wm.opacity
assert abs(wm.angle - 30) < 1e-6, wm.angle
assert wm.indexes is None, "ทุกหน้า -> indexes ควรเป็น None"
print("OK  เพิ่มลายน้ำผ่าน dialog (ข้อความ/ความเข้ม/องศา)")

# ยังไม่ฝังลงไฟล์
assert "สำเนา" not in w.doc.page_text(0)
print("OK  ยังไม่บันทึก ยังไม่ฝัง (แก้ต่อได้)")

# ---- เปิดอีกครั้ง = โหมดแก้ไข ค่าเดิมถูกเติมไว้ ----
seen = {}
def fill_edit(d):
    seen["text"] = d.findChild(QLineEdit).text()
    sl = d.findChildren(QSlider)
    seen["op"] = sl[0].value()
    seen["ang"] = sl[1].value()
    d.findChild(QLineEdit).setText("ตัวอย่าง")
    sl[0].setValue(60)
with patch.object(QDialog, "exec", drive(fill_edit)):
    w.watermark_dialog()
assert seen["text"] == "สำเนา", f"ต้องเติมค่าเดิม ได้ {seen}"
assert seen["op"] == 35 and seen["ang"] == 30, seen
assert w.doc.watermark.text == "ตัวอย่าง"
assert abs(w.doc.watermark.opacity - 0.60) < 1e-6
print("OK  เปิดซ้ำ = แก้ไข (ค่าเดิมถูกเติม + แก้ได้)")

# ---- ปรับขนาดเอง แล้วกลับเป็นอัตโนมัติ ----
def fill_size(d):
    d.findChild(QCheckBox).setChecked(False)      # ปิดอัตโนมัติ
    d.findChild(QSpinBox).setValue(120)
with patch.object(QDialog, "exec", drive(fill_size)):
    w.watermark_dialog()
assert w.doc.watermark.font_size == 120.0, w.doc.watermark.font_size
assert abs(w.doc.watermark_geometry(0)[2] - 120.0) < 1e-6
print("OK  ตั้งขนาดเองได้")

def fill_auto(d):
    d.findChild(QCheckBox).setChecked(True)       # กลับเป็นอัตโนมัติ
with patch.object(QDialog, "exec", drive(fill_auto)):
    w.watermark_dialog()
assert w.doc.watermark.font_size is None, "ต้องกลับเป็นขนาดอัตโนมัติได้"
print("OK  สลับกลับเป็นขนาดอัตโนมัติได้")

# ---- กดยกเลิก = ไม่เปลี่ยนอะไร ----
before = w.doc.watermark.copy()
def fill_cancel(d):
    d.findChild(QLineEdit).setText("ไม่เอาอันนี้")
with patch.object(QDialog, "exec", drive(fill_cancel, QDialog.Rejected)):
    w.watermark_dialog()
assert w.doc.watermark.text == before.text, "ยกเลิกต้องคืนค่าเดิม"
print("OK  กดยกเลิก คืนค่าเดิม ไม่เปลี่ยน")

# ---- ลบลายน้ำ (ปุ่มลบคืนค่า 2) ----
with patch.object(QDialog, "exec", drive(lambda d: None, 2)):
    w.watermark_dialog()
assert w.doc.watermark is None, "ต้องลบลายน้ำออก"
print("OK  ปุ่มลบลายน้ำทำงาน")

# undo เอากลับได้
w.doc.undo()
assert w.doc.watermark is not None
print("OK  undo เอาลายน้ำที่ลบกลับมาได้")

# ---- บันทึกแล้วฝังลงไฟล์จริง ----
out = tmp / "saved.pdf"
w.doc.save(out)
with fitz.open(out) as v:
    assert any(w.doc.watermark is None for _ in [0])
    assert "ตัวอย่าง" in v.load_page(0).get_text()
print("OK  บันทึกแล้วลายน้ำฝังลงไฟล์")

# ---- เฉพาะหน้าปัจจุบัน ----
w2 = fresh()
w2.thumbs.setCurrentRow(1)
def fill_p(d):
    d.findChild(QLineEdit).setText("หน้าเดียว")
with patch("app.main.QInputDialog.getItem", return_value=("หน้าปัจจุบัน (หน้า 2)", True)), \
     patch.object(QDialog, "exec", drive(fill_p)):
    w2.watermark_dialog()
assert w2.doc.watermark.indexes == [1], w2.doc.watermark.indexes
assert w2.doc.watermark_geometry(0) is None and w2.doc.watermark_geometry(1) is not None
print("OK  ใส่เฉพาะหน้าปัจจุบันได้")

print("\nผ่านทั้งหมด")
