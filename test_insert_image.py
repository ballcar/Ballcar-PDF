"""ทดสอบแทรกรูปภาพ — ลากย้าย/ย่อขยายได้ และต้องคงพื้นหลังเดิมของรูป"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PIL import Image
from PySide6.QtCore import QRect
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())

d = fitz.open()
for i in range(2):
    d.new_page(width=595, height=842).insert_text((60, 80), f"PAGE {i+1}", fontsize=16)
src = tmp / "doc.pdf"
d.save(str(src)); d.close()

# รูปถ่าย: มีพื้นขาวรอบๆ + สี่เหลี่ยมแดงตรงกลาง (จะได้รู้ว่าพื้นขาวถูกลบไหม)
photo = Image.new("RGB", (200, 120), (255, 255, 255))
for y in range(40, 80):
    for x in range(70, 130):
        photo.putpixel((x, y), (220, 30, 30))
photo_path = tmp / "photo.png"
photo.save(photo_path)

app = QApplication.instance() or QApplication(sys.argv)

# ================= คงพื้นหลังเดิม (ต่างจากลายเซ็น) =================

as_photo = PdfDocument.prepare_image(photo_path, remove_background=False)
with Image.open(as_photo) as im:
    rgba = im.convert("RGBA")
    assert rgba.getpixel((5, 5))[3] == 255, "แทรกรูป: พื้นขาวต้องยังทึบอยู่ ไม่ถูกลบ"

as_sig = PdfDocument.prepare_image(photo_path, remove_background=True)
with Image.open(as_sig) as im:
    rgba2 = im.convert("RGBA")
    assert rgba2.getpixel((5, 5))[3] == 0, "ลายเซ็น: พื้นขาวต้องถูกลบเป็นโปร่งใส"
print("OK  แทรกรูปคงพื้นหลังเดิม · ลายเซ็นลบพื้นขาว (แยกกันถูกต้อง)")

# png/jpg ที่คงพื้นหลัง ใช้ไฟล์เดิมได้เลย ไม่สร้างไฟล์ชั่วคราวซ้ำ
assert as_photo == str(photo_path), "png/jpg ควรใช้ไฟล์เดิม ไม่ต้องแปลง"
print("OK  ไฟล์ png/jpg ใช้ไฟล์เดิม ไม่แปลงซ้ำซ้อน")

# ================= เข้าโหมดวาง แล้วลากย้าย/ย่อขยาย =================

w = MainWindow()
w.resize(1000, 700)
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)
w.show()
w.viewer.set_zoom(1.0)
app.processEvents()

with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(photo_path), "")):
    w.insert_image_dialog()
app.processEvents()
assert w.viewer.placing, "ต้องเข้าโหมดวางรูป (มีกรอบตัวอย่างให้ลาก)"
assert w._placing_bar.isVisible(), "ต้องมีแถบยืนยัน/ยกเลิก"
overlay = w.viewer.overlay
assert overlay is not None and not overlay.source.isNull(), "ต้องเห็นตัวอย่างรูป"
# สัดส่วนเริ่มต้นต้องตรงกับรูปจริง (200x120)
ratio = overlay.height() / overlay.width()
assert abs(ratio - 120 / 200) < 0.06, f"สัดส่วนเริ่มต้นเพี้ยน {ratio:.3f}"
print("OK  เข้าโหมดวางรูป มีตัวอย่างให้ลาก สัดส่วนตรงกับรูปจริง")

# ย้าย + ย่อขยายผ่านการตั้งกรอบ แล้วยืนยัน
overlay.setGeometry(QRect(120, 200, 260, 156))
app.processEvents()
w.commit_placement()
app.processEvents()
assert not w.viewer.placing, "ยืนยันแล้วต้องออกจากโหมดวาง"
assert len(w.doc.stamps) == 1, f"ต้องได้รูป 1 ชิ้น ได้ {len(w.doc.stamps)}"
img = w.doc.stamps[0]
assert img.page == 0
assert abs(img.rect.width - 260) < 3 and abs(img.rect.height - 156) < 3, \
    f"ขนาดที่วางไม่ตรงกับที่ลาก {img.rect}"
print(f"OK  ยืนยันแล้วได้รูปตามขนาดที่ลาก ({img.rect.width:.0f}x{img.rect.height:.0f})")

# คลิกที่รูปแล้วเลือกได้ (เพื่อย้าย/ย่อขยายอีกครั้ง)
hit = w.doc.stamp_at(0, fitz.Point(img.rect.x0 + 5, img.rect.y0 + 5))
assert hit is img, "คลิกที่รูปต้องเลือกได้"
w.viewer.selected_stamp = img
w.edit_selected_stamp()
app.processEvents()
assert w.viewer.placing and w.viewer.editing_stamp is img, "ต้องกลับเข้าโหมดย้าย/ย่อขยายได้"
w.viewer.overlay.setGeometry(QRect(50, 60, 300, 180))
w.commit_placement()
app.processEvents()
assert abs(w.doc.stamps[0].rect.width - 300) < 3, "ย้าย/ย่อขยายรอบสองต้องมีผล"
assert len(w.doc.stamps) == 1, "ย้ายแล้วต้องไม่เกิดรูปใหม่"
print("OK  คลิกรูปเพื่อย้าย/ย่อขยายได้อีก ไม่เกิดซ้ำ")

# ================= ยังไม่บันทึก / บันทึกแล้วฝังจริง =================

assert not w.doc.doc.load_page(0).get_images(), "ยังไม่บันทึก ไม่ควรฝังลงไฟล์"
out = tmp / "with_image.pdf"
w.doc.save(out)
with fitz.open(str(out)) as v:
    assert v.load_page(0).get_images(), "บันทึกแล้วต้องมีรูปฝังในหน้า 1"
    assert not v.load_page(1).get_images(), "หน้า 2 ไม่ได้วางรูป ต้องไม่มี"
assert w.doc.stamps == [], "บันทึกแล้วของลอยต้องถูกฝัง"
print("OK  ยังไม่บันทึกไม่ฝัง · บันทึกแล้วมีรูปในไฟล์จริง")

# ================= ลบ / undo / ยกเลิก =================

w2 = MainWindow()
w2.doc = PdfDocument(src)
w2.viewer.set_document(w2.doc)
w2._refresh_all(keep_row=0)
st = w2.doc.add_stamp(0, str(photo_path), fitz.Rect(100, 100, 300, 220))
w2.viewer.selected_stamp = st
w2.delete_selected_stamp()
assert w2.doc.stamps == [], "ลบรูปได้"
w2.undo()
assert len(w2.doc.stamps) == 1, "Ctrl+Z เอารูปกลับได้"
print("OK  ลบรูปได้ และ undo เอากลับได้")

# กดยกเลิกตอนกำลังวาง -> ไม่มีรูปเพิ่ม
before = len(w2.doc.stamps)
with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(photo_path), "")):
    w2.insert_image_dialog()
w2.cancel_placement()
assert not w2.viewer.placing and len(w2.doc.stamps) == before, "ยกเลิกแล้วต้องไม่เพิ่มรูป"
print("OK  ยกเลิกตอนวาง -> ไม่เพิ่มรูป")

# เลือกไฟล์แล้วกดยกเลิกในกล่องเลือกไฟล์ -> ไม่พัง
with patch("app.main.QFileDialog.getOpenFileName", return_value=("", "")):
    w2.insert_image_dialog()
assert not w2.viewer.placing
print("OK  ไม่เลือกไฟล์ -> ไม่พัง")

# ================= วางรูปเดิมทุกหน้าได้ (ใช้กลไกเดียวกับลายเซ็น) =================

w3 = MainWindow()
w3.doc = PdfDocument(src)
w3.viewer.set_document(w3.doc)
w3._refresh_all(keep_row=0)
s3 = w3.doc.add_stamp(0, str(photo_path), fitz.Rect(400, 700, 520, 772))
w3.viewer.selected_stamp = s3
with patch.object(w3, "_ask_scope", return_value=[0, 1]):
    w3.stamp_selected_all_pages()
assert len(w3.doc.stamps_on(1)) == 1, "วางรูปเดิมทุกหน้าได้"
print("OK  วางรูปเดิมตำแหน่งเดิมทุกหน้าได้")

# ================= มีเมนูให้กดจริง =================

menu_action = next((a for a in w3.findChildren(QAction)
                    if "แทรกรูปภาพ" in a.text() or "Insert Image" in a.text()), None)
assert menu_action is not None, "ต้องมีเมนู 'แทรกรูปภาพ'"
# เมนูต้องไม่ส่งค่า checked เข้าไปเป็นพารามิเตอร์ (กับดัก Qt เดิม)
with patch("app.main.QFileDialog.getOpenFileName", return_value=("", "")) as picker:
    menu_action.trigger()
assert picker.called, "กดเมนูแล้วต้องเปิดกล่องเลือกไฟล์"
print("OK  มีเมนู 'แทรกรูปภาพ' และกดใช้งานได้")

print("\nผ่านทั้งหมด")
