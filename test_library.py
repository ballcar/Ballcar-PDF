"""ทดสอบคลังลายเซ็น (บันทึกไว้ใช้ซ้ำ)"""
import os
import sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ชี้คลังไปที่โฟลเดอร์ชั่วคราว จะได้ไม่ไปยุ่งกับของจริงในเครื่อง
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PIL import Image
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app import library
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(2):
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 120), f"MARK{i+1}", fontsize=30)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

# ลายเซ็นพื้นขาว (แบบที่ผู้ใช้มีจริง)
sig = tmp / "boss.gif"
im = Image.new("RGB", (200, 80), "white")
for x in range(20, 180):
    im.putpixel((x, 40), (0, 0, 200))
im.save(sig)

app = QApplication(sys.argv)

assert library.library_dir().exists()
assert library.list_signatures() == []
print("OK  เริ่มต้นคลังว่าง")


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc)
    w.viewer.set_zoom(1.0)
    w._refresh_all(keep_row=0)
    w.resize(1000, 800)
    w.show()
    return w


# ---- เพิ่มเข้าคลัง ----
w = fresh()
with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(sig), "")), \
     patch("app.main.QInputDialog.getText", return_value=("ลายเซ็นผู้จัดการ", True)):
    w.add_signature_to_library()

saved = library.list_signatures()
assert len(saved) == 1 and saved[0].stem == "ลายเซ็นผู้จัดการ", saved
print("OK  เพิ่มลายเซ็นเข้าคลังได้")

# พื้นหลังต้องถูกลบตั้งแต่ตอนเก็บ (จะได้ไม่ต้องลบซ้ำตอนใช้)
with Image.open(saved[0]) as p:
    assert p.mode == "RGBA" and p.getpixel((0, 0))[3] == 0, "ในคลังต้องเก็บแบบพื้นหลังโปร่งใส"
print("OK  ในคลังเก็บแบบพื้นหลังโปร่งแล้ว")

# ---- คลิกจากเมนู = เข้าโหมดวางทันที ----
w = fresh()
w._build_signature_menu()
names = [a.text() for a in w.sig_menu.actions()]
assert "ลายเซ็นผู้จัดการ" in names, names
assert any("เพิ่มลายเซ็นเข้าคลัง" in n for n in names), names
assert any("จัดการคลัง" in n for n in names), names
print("OK  เมนูแสดงลายเซ็นในคลัง:", [n for n in names if n])

for a in w.sig_menu.actions():
    if a.text() == "ลายเซ็นผู้จัดการ":
        assert not a.icon().isNull(), "ต้องมีรูปตัวอย่างในเมนู"
        a.trigger()
        break
assert w.viewer.placing, "คลิกจากคลังต้องเข้าโหมดวางทันที"
assert w._placing_bar.isVisible()
w.viewer.overlay.setGeometry(100, 500, 200, 80)
w.commit_placement()
assert len(w.doc.stamps) == 1
assert w.doc.stamps[0].image_path == str(saved[0])
print("OK  คลิกจากคลังแล้ววางได้เลย")

# ---- บันทึกไฟล์แล้วลายเซ็นจากคลังต้องฝังถูก ----
out = tmp / "signed.pdf"
w.doc.save(out)
with fitz.open(out) as v:
    assert len(v.load_page(0).get_images()) == 1
print("OK  ลายเซ็นจากคลังฝังลงไฟล์ได้")

# ---- เก็บลายเซ็นที่วางอยู่เข้าคลังจากแถบเครื่องมือ ----
w = fresh()
prepared = PdfDocument.prepare_image(sig)
stamp = w.doc.add_stamp(0, prepared, fitz.Rect(100, 300, 300, 380))
w.viewer.selected_stamp = stamp
with patch("app.main.QInputDialog.getText", return_value=("ลายเซ็นสำรอง", True)):
    w.save_stamp_to_library()
assert len(library.list_signatures()) == 2
print("OK  เก็บลายเซ็นที่วางอยู่เข้าคลังได้")

# ---- ชื่อซ้ำต้องไม่ทับของเดิม ----
with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(sig), "")), \
     patch("app.main.QInputDialog.getText", return_value=("ลายเซ็นผู้จัดการ", True)):
    w.add_signature_to_library()
names = [p.stem for p in library.list_signatures()]
assert "ลายเซ็นผู้จัดการ" in names and "ลายเซ็นผู้จัดการ (2)" in names, names
print("OK  ชื่อซ้ำเติมเลขให้ ไม่ทับของเดิม")

# ---- เปลี่ยนชื่อ ----
target = [p for p in library.list_signatures() if p.stem == "ลายเซ็นสำรอง"][0]
library.rename_signature(target, "ลายเซ็นรอง")
assert "ลายเซ็นรอง" in [p.stem for p in library.list_signatures()]
try:
    library.rename_signature(
        [p for p in library.list_signatures() if p.stem == "ลายเซ็นรอง"][0], "ลายเซ็นผู้จัดการ")
except ValueError:
    print("OK  เปลี่ยนชื่อได้ และกันชื่อชนกัน")
else:
    raise AssertionError("ชื่อซ้ำควร error")

# ---- ลบออกจากคลัง ----
before = len(library.list_signatures())
library.delete_signature([p for p in library.list_signatures() if p.stem == "ลายเซ็นรอง"][0])
assert len(library.list_signatures()) == before - 1
print("OK  ลบออกจากคลังได้")

# ---- ลบไฟล์นอกคลังไม่ได้ ----
outsider = tmp / "outside.png"
outsider.write_bytes(b"x")
try:
    library.delete_signature(outsider)
except ValueError:
    assert outsider.exists(), "ไฟล์นอกคลังต้องไม่ถูกแตะ"
    print("OK  กันลบไฟล์นอกคลัง")
else:
    raise AssertionError("ต้องไม่ยอมลบไฟล์นอกคลัง")

# ---- ชื่อที่มีอักขระต้องห้าม ----
assert library.safe_name('a/b:c*d?') == "abcd"
assert library.safe_name("   ") == "ลายเซ็น"
print("OK  ชื่อไฟล์ที่มีอักขระต้องห้ามถูกจัดการ")

# ---- ยังไม่เปิดไฟล์: เมนูยังเปิดได้ แต่กดวางไม่ได้ ----
w2 = MainWindow()
w2._build_signature_menu()
for a in w2.sig_menu.actions():
    if a.text() == "ลายเซ็นผู้จัดการ":
        assert not a.isEnabled(), "ยังไม่เปิดไฟล์ ต้องกดวางไม่ได้"
assert any("เพิ่มลายเซ็นเข้าคลัง" in a.text() and a.isEnabled() for a in w2.sig_menu.actions())
print("OK  ยังไม่เปิดไฟล์ก็จัดการคลังได้ แต่วางไม่ได้")

# ---- คลังว่าง เมนูต้องบอกให้รู้ ----
for p in library.list_signatures():
    library.delete_signature(p)
w._build_signature_menu()
texts = [a.text() for a in w.sig_menu.actions()]
assert any("ยังไม่มีลายเซ็น" in t for t in texts), texts
assert not any("จัดการคลัง" in t for t in texts), "คลังว่างไม่ควรมีเมนูจัดการ"
print("OK  คลังว่างแสดงข้อความบอก")

print("\nผ่านทั้งหมด")
