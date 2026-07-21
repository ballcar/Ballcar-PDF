"""ทดสอบการวางลายเซ็นแบบลากย้าย/ย่อขยายก่อนยืนยัน"""
import sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument
from app.viewer import HANDLE, MIN_SIZE

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(3):
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 120), f"MARK{i+1}", fontsize=30)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

sig = tmp / "sig.png"
pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 80), True)
pix.clear_with(0)
pix.save(str(sig))

app = QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc)
    w.viewer.set_zoom(1.0)
    w._refresh_all(keep_row=0)
    w.resize(1000, 800)
    w.show()  # ต้อง show ก่อน ไม่งั้น isVisible() ของ widget ลูกเป็น False เสมอ
    return w


def start(w):
    with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(sig), "")):
        w.signature_dialog()
    return w.viewer.overlay


def press_drag(widget, local, global_from, global_to):
    """จำลองกดค้าง-ลาก-ปล่อย

    local = จุดที่กดในพิกัดของ widget (ตัวตัดสินว่าเป็นย้ายหรือย่อขยาย)
    global_from/to = ระยะที่เมาส์เคลื่อนจริง
    """
    widget.mousePressEvent(QMouseEvent(
        QEvent.MouseButtonPress, QPointF(local), QPointF(global_from),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    widget.mouseMoveEvent(QMouseEvent(
        QEvent.MouseMove, QPointF(local), QPointF(global_to),
        Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    widget.mouseReleaseEvent(QMouseEvent(
        QEvent.MouseButtonRelease, QPointF(local), QPointF(global_to),
        Qt.LeftButton, Qt.NoButton, Qt.NoModifier))


def center_of(widget):
    return QPoint(widget.width() // 2, widget.height() // 2)


# ---- เริ่มวาง: ต้องมีตัวอย่างโผล่ + แถบยืนยันโผล่ ----
w = fresh()
ov = start(w)
assert ov is not None and ov.isVisible()
assert w.viewer.placing
assert w._placing_bar.isVisible()
assert len(w.doc.doc.load_page(0).get_images()) == 0, "ยังไม่กดยืนยัน ต้องยังไม่ลงไฟล์"
print("OK  ตัวอย่างโผล่ ยังไม่เขียนลงไฟล์")

# สัดส่วนรูปต้องคงเดิม (200x80 -> 2.5:1)
geo = ov.geometry()
assert abs(geo.width() / geo.height() - 2.5) < 0.15, (geo.width(), geo.height())
print("OK  ขนาดเริ่มต้นได้สัดส่วนรูป")

# ---- ลากย้าย ----
before = ov.geometry()
press_drag(ov, center_of(ov), QPoint(500, 500), QPoint(560, 540))
after = ov.geometry()
assert after.topLeft() == before.topLeft() + QPoint(60, 40), (before, after)
assert after.size() == before.size(), "ย้ายแล้วขนาดต้องไม่เปลี่ยน"
print("OK  ลากตรงกลางเพื่อย้าย")

# ---- ลากมุมขวาล่างเพื่อขยาย ----
before = ov.geometry()
corner = QPoint(before.width() - 2, before.height() - 2)   # ในพิกัดของตัว overlay
press_drag(ov, corner, QPoint(700, 700), QPoint(750, 730))
after = ov.geometry()
assert after.topLeft() == before.topLeft(), "ลากมุมขวาล่าง มุมซ้ายบนต้องอยู่ที่เดิม"
assert after.width() == before.width() + 50 and after.height() == before.height() + 30, (before, after)
print("OK  ลากมุมขวาล่างเพื่อขยาย")

# ---- ลากมุมซ้ายบนเพื่อย่อ ----
before = ov.geometry()
press_drag(ov, QPoint(2, 2), QPoint(700, 700), QPoint(720, 715))
after = ov.geometry()
assert after.bottomRight() == before.bottomRight(), "ลากมุมซ้ายบน มุมขวาล่างต้องอยู่ที่เดิม"
assert after.width() == before.width() - 20, (before, after)
print("OK  ลากมุมซ้ายบนเพื่อย่อ")

# ---- ย่อจนเล็กมากต้องไม่หายไป ----
ov.setGeometry(100, 100, 200, 80)
press_drag(ov, QPoint(198, 78), QPoint(500, 500), QPoint(100, 100))
assert ov.geometry().width() >= MIN_SIZE and ov.geometry().height() >= MIN_SIZE, ov.geometry()
print("OK  ย่อเล็กสุดยังไม่หาย")

# ---- ซูมแล้วกรอบต้องขยับตาม ----
ov.setGeometry(200, 300, 200, 80)
w.viewer.set_zoom(2.0)
assert ov.geometry().topLeft() == QPoint(400, 600), ov.geometry()
assert ov.geometry().width() == 400
w.viewer.set_zoom(1.0)
assert ov.geometry().topLeft() == QPoint(200, 300), ov.geometry()
print("OK  ซูมแล้วกรอบตัวอย่างขยับตาม")

# ---- กดยืนยัน: ตำแหน่งบนไฟล์ต้องตรงกับกรอบที่ปรับไว้ ----
ov.setGeometry(150, 400, 200, 80)
w.commit_placement()
# ลายเซ็นเก็บเป็นชั้นลอยก่อน (ยังแก้ได้) ฝังลงไฟล์ตอนบันทึก
assert len(w.doc.stamps) == 1, w.doc.stamps
assert w.doc.stamps[0].rect == fitz.Rect(150, 400, 350, 480), w.doc.stamps[0].rect

out = tmp / "committed.pdf"
w.doc.save(out)
with fitz.open(out) as v:
    page = v.load_page(0)
    imgs = page.get_images()
    assert len(imgs) == 1, imgs
    bbox = page.get_image_rects(imgs[0][0])[0]
    assert abs(bbox.x0 - 150) < 2 and abs(bbox.y0 - 400) < 2, bbox
    # PyMuPDF รักษาสัดส่วนรูป จึงอาจพอดีกรอบไม่เป๊ะ แต่ต้องไม่ล้นออกนอกกรอบ
    assert bbox.width <= 201 and bbox.height <= 81, bbox
    assert bbox.width > 190 and bbox.height > 75, bbox
    assert abs(bbox.width / bbox.height - 2.5) < 0.05, "สัดส่วนรูปต้องไม่เพี้ยน"
assert not w.viewer.placing and not w._placing_bar.isVisible()
print(f"OK  ยืนยันแล้ววางตรงตำแหน่ง (bbox={bbox})")

w.undo()
assert len(w.doc.stamps) == 0
print("OK  undo ได้")

# ---- Esc ยกเลิก ----
w = fresh()
start(w)
w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
assert not w.viewer.placing and not w._placing_bar.isVisible()
assert len(w.doc.stamps) == 0
assert not w.doc.dirty, "ยกเลิกแล้วต้องไม่นับว่าแก้ไข"
print("OK  Esc ยกเลิก ไม่มีอะไรตกค้าง")

# ---- Enter ยืนยัน ----
w = fresh()
start(w)
w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
assert len(w.doc.stamps) == 1
print("OK  Enter ยืนยัน")

# ---- ดับเบิลคลิกยืนยัน ----
w = fresh()
ov = start(w)
ov.mouseDoubleClickEvent(QMouseEvent(
    QEvent.MouseButtonDblClick, QPointF(QPoint(20, 20)), QPointF(20, 20),
    Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
assert len(w.doc.stamps) == 1
print("OK  ดับเบิลคลิกยืนยัน")

# ---- เลือกหน้าอื่นแล้ววาง ต้องลงหน้านั้น ----
w = fresh()
w.thumbs.setCurrentRow(2)
start(w)
w.commit_placement()
assert len(w.doc.stamps_on(2)) == 1
assert len(w.doc.stamps_on(0)) == 0
print("OK  วางลงหน้าที่กำลังดูอยู่")

# ---- เริ่มวางซ้อนสองครั้ง ต้องเหลือตัวเดียว ----
w = fresh()
start(w)
first = w.viewer.overlay
start(w)
assert w.viewer.overlay is not first
w.commit_placement()
assert len(w.doc.stamps) == 1
print("OK  เริ่มวางซ้ำไม่ทิ้งตัวอย่างค้าง")

# ---- กรอบตัวอย่างต้องโปร่งใส (เห็นเนื้อหาใต้ลายเซ็นตอนจัดตำแหน่ง) ----
# เคยพลาด: stylesheet พื้นเทาของวิวเออร์ตกทอดมาที่ QLabel ลูก จนบังเส้นในเอกสาร
lined = tmp / "lined.pdf"
d2 = fitz.open()
pg = d2.new_page(width=595, height=300)
pg.draw_line((50, 150), (550, 150), width=2)
d2.save(str(lined)); d2.close()

w = MainWindow()
w.doc = PdfDocument(lined)
w.viewer.set_document(w.doc)
w.viewer.set_zoom(1.0)
w._refresh_all(keep_row=0)
w.resize(900, 500)
w.show()

# รูปลายเซ็นที่มีพื้นโปร่ง (sig ด้านบนเป็นสี่เหลี่ยมทึบเต็มกรอบ วัดพื้นหลังไม่ได้)
clear_sig = tmp / "clear.png"
cp = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 80), True)
cp.clear_with()          # โปร่งใสทั้งแผ่น
cp.save(str(clear_sig))
with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(clear_sig), "")):
    w.signature_dialog()
w.viewer.overlay.setGeometry(100, 110, 200, 80)   # คร่อมเส้นที่ y=150
app.processEvents()

image = w.viewer.grab().toImage()
spot = image.pixelColor(140, 120)                 # จุดว่างในกรอบ
assert spot.red() > 240 and spot.green() > 240 and spot.blue() > 240, \
    f"กรอบตัวอย่างต้องโปร่งใส แต่เจอสี {spot.red(), spot.green(), spot.blue()}"
print("OK  กรอบตัวอย่างโปร่งใส เห็นเนื้อหาใต้ลายเซ็น")

print("\nผ่านทั้งหมด")
