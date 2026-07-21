"""ทดสอบการแก้ไขลายเซ็นที่วางไปแล้ว (ย้าย/ปรับขนาด/ลบ) + รองรับ .gif"""
import sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from PIL import Image
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(3):
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 120), f"MARK{i+1}", fontsize=30)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

# ลายเซ็น PNG โปร่งใส
sig_png = tmp / "sig.png"
im = Image.new("RGBA", (200, 80), (0, 0, 0, 0))
for x in range(20, 180):
    im.putpixel((x, 40), (0, 0, 255, 255))
im.save(sig_png)

# ลายเซ็น GIF โปร่งใส (แบบที่พี่จะใช้)
sig_gif = tmp / "sig.gif"
im.convert("P", palette=Image.ADAPTIVE).save(sig_gif, transparency=0)

# GIF เคลื่อนไหว 3 เฟรม
sig_anim = tmp / "anim.gif"
frames = [Image.new("RGB", (120, 60), c) for c in ("red", "green", "blue")]
frames[0].save(sig_anim, save_all=True, append_images=frames[1:], duration=100)

app = QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc)
    w.viewer.set_zoom(1.0)
    w._refresh_all(keep_row=0)
    w.resize(1000, 800)
    w.show()
    return w


def place(w, rect, image=sig_png):
    with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(image), "")):
        w.signature_dialog()
    w.viewer.overlay.setGeometry(
        int(rect.x0), int(rect.y0), int(rect.width), int(rect.height))
    w.commit_placement()
    return w.doc.stamps[-1]


def click_viewer(w, page_pt):
    """คลิกที่จุดบนหน้า (พิกัด PDF)"""
    local = QPoint(int(page_pt.x * w.viewer.zoom), int(page_pt.y * w.viewer.zoom))
    pos = w.viewer._label.mapTo(w.viewer, local)
    w.viewer.mousePressEvent(QMouseEvent(
        QEvent.MouseButtonPress, QPointF(pos), QPointF(pos),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


# ---- วางแล้วยังแก้ได้ (ไม่ฝังลงไฟล์ทันที) ----
w = fresh()
stamp = place(w, fitz.Rect(100, 300, 300, 380))
assert len(w.doc.stamps) == 1
assert len(w.doc.doc.load_page(0).get_images()) == 0, "ยังไม่บันทึก ต้องยังไม่ฝังลงไฟล์"
assert w.doc.dirty
print("OK  วางแล้วเก็บเป็นชั้นลอย ยังไม่ฝังลงไฟล์")

# ---- คลิกโดนลายเซ็น = เลือกได้ ----
w.viewer.selected_stamp = None
w._stamp_bar.hide()
click_viewer(w, fitz.Point(200, 340))
assert w.viewer.selected_stamp is stamp
assert w._stamp_bar.isVisible()
print("OK  คลิกโดนลายเซ็นแล้วเลือกได้ แถบเครื่องมือโผล่")

# ---- คลิกนอกลายเซ็น = ยกเลิกการเลือก ----
click_viewer(w, fitz.Point(500, 700))
assert w.viewer.selected_stamp is None
print("OK  คลิกที่ว่างแล้วเลิกเลือก")

# ---- ย้ายลายเซ็นที่วางไปแล้ว ----
click_viewer(w, fitz.Point(200, 340))
w.edit_selected_stamp()
assert w.viewer.placing and w.viewer.editing_stamp is stamp
assert len(w.doc.stamps) == 1, "ระหว่างแก้ไขต้องไม่เกิดตัวใหม่"
w.viewer.overlay.setGeometry(400, 600, 200, 80)
w.commit_placement()
assert len(w.doc.stamps) == 1, "แก้เสร็จต้องยังมีตัวเดียว"
assert w.doc.stamps[0].rect == fitz.Rect(400, 600, 600, 680), w.doc.stamps[0].rect
print("OK  ย้ายลายเซ็นที่วางไปแล้วได้ ไม่เกิดตัวซ้ำ")

# ---- ปรับขนาดลายเซ็นที่วางไปแล้ว ----
click_viewer(w, fitz.Point(500, 640))
w.edit_selected_stamp()
w.viewer.overlay.setGeometry(400, 600, 100, 40)
w.commit_placement()
assert w.doc.stamps[0].rect == fitz.Rect(400, 600, 500, 640), w.doc.stamps[0].rect
print("OK  ปรับขนาดลายเซ็นที่วางไปแล้วได้")

# ---- undo การย้าย ----
w.undo()
assert w.doc.stamps[0].rect == fitz.Rect(400, 600, 600, 680), w.doc.stamps[0].rect
print("OK  undo การย้าย/ปรับขนาดได้")

# ---- ลบลายเซ็นด้วยปุ่ม ----
w.viewer.selected_stamp = w.doc.stamps[0]
w.delete_selected_stamp()
assert w.doc.stamps == [] and w.viewer.selected_stamp is None
assert not w._stamp_bar.isVisible()
w.undo()
assert len(w.doc.stamps) == 1
print("OK  ลบลายเซ็นได้ และ undo เอากลับได้")

# ---- กด Delete ตอนเลือกลายเซ็น ต้องลบลายเซ็น ไม่ใช่ลบหน้า ----
w = fresh()
place(w, fitz.Rect(100, 300, 300, 380))
pages_before = w.doc.page_count
click_viewer(w, fitz.Point(200, 340))
w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
assert w.doc.stamps == []
assert w.doc.page_count == pages_before, "ต้องไม่เผลอลบหน้า"
print("OK  Delete ตอนเลือกลายเซ็น = ลบลายเซ็น ไม่ใช่ลบหน้า")

# ---- หลายลายเซ็นในหน้าเดียว เลือกถูกตัว ----
w = fresh()
a = place(w, fitz.Rect(50, 50, 150, 90))
b = place(w, fitz.Rect(300, 500, 400, 540))
click_viewer(w, fitz.Point(100, 70))
assert w.viewer.selected_stamp is a
click_viewer(w, fitz.Point(350, 520))
assert w.viewer.selected_stamp is b
print("OK  หลายลายเซ็น เลือกถูกตัว")

# ---- ลายเซ็นคนละหน้า ไม่ปนกัน ----
w = fresh()
place(w, fitz.Rect(100, 300, 300, 380))
w.thumbs.setCurrentRow(2)
place(w, fitz.Rect(100, 300, 300, 380))
assert len(w.doc.stamps_on(0)) == 1 and len(w.doc.stamps_on(2)) == 1
assert len(w.doc.stamps_on(1)) == 0
click_viewer(w, fitz.Point(200, 340))          # อยู่หน้า 3
assert w.viewer.selected_stamp is w.doc.stamps_on(2)[0]
print("OK  ลายเซ็นแยกตามหน้าถูกต้อง")

# ---- บันทึกแล้วจึงฝังลงไฟล์จริง ----
out = tmp / "saved.pdf"
w.doc.save(out)
assert w.doc.stamps == [], "บันทึกแล้วต้องฝังลงไฟล์"
with fitz.open(out) as v:
    assert len(v.load_page(0).get_images()) == 1
    assert len(v.load_page(2).get_images()) == 1
    assert len(v.load_page(1).get_images()) == 0
    bbox = v.load_page(0).get_image_rects(v.load_page(0).get_images()[0][0])[0]
    assert abs(bbox.x0 - 100) < 2 and abs(bbox.y0 - 300) < 2, bbox
print("OK  บันทึกแล้วฝังลงไฟล์ตรงตำแหน่ง")

# ---- .gif ใช้ได้ ----
w = fresh()
prepared = PdfDocument.prepare_image(sig_gif)
assert prepared.endswith(".png") and Path(prepared).exists()
with Image.open(prepared) as p:
    assert p.mode == "RGBA", p.mode
place(w, fitz.Rect(100, 300, 300, 380), image=sig_gif)
assert len(w.doc.stamps) == 1
out = tmp / "gif.pdf"
w.doc.save(out)
with fitz.open(out) as v:
    assert len(v.load_page(0).get_images()) == 1
print("OK  ลายเซ็น .gif ใช้ได้ (แปลงเป็น PNG โปร่งใส)")

# ---- gif เคลื่อนไหว -> ใช้เฟรมแรก ไม่พัง ----
w = fresh()
place(w, fitz.Rect(100, 300, 220, 360), image=sig_anim)
w.doc.save(tmp / "anim.pdf")
with fitz.open(tmp / "anim.pdf") as v:
    assert len(v.load_page(0).get_images()) == 1
print("OK  gif เคลื่อนไหวใช้เฟรมแรก ไม่พัง")

# ---- ไฟล์ png ที่โปร่งใสอยู่แล้ว: เนื้อรูปต้องเหมือนเดิม ----
prepared = PdfDocument.prepare_image(sig_png)
with Image.open(prepared) as a, Image.open(sig_png) as b:
    assert list(a.convert("RGBA").getdata()) == list(b.convert("RGBA").getdata())
print("OK  png โปร่งใสอยู่แล้ว เนื้อรูปไม่เปลี่ยน")

# ---- ลบพื้นหลังขาวอัตโนมัติ ----
# ลายเซ็นสีน้ำเงินบนพื้นขาวทึบ (แบบที่สแกน/บันทึกมาจาก GIF ทั่วไป)
solid = tmp / "solid.gif"
im2 = Image.new("RGB", (100, 50), "white")
for x in range(10, 90):
    im2.putpixel((x, 25), (0, 0, 200))
im2.save(solid)

prepared = PdfDocument.prepare_image(solid)
with Image.open(prepared) as p:
    assert p.mode == "RGBA"
    assert p.getpixel((0, 0))[3] == 0, "มุมซ้ายบน (พื้นขาว) ต้องโปร่งใส"
    assert p.getpixel((95, 5))[3] == 0, "พื้นที่ว่างต้องโปร่งใส"
    r, g, b, a = p.getpixel((50, 25))
    assert a == 255 and b > 150, f"เส้นลายเซ็นต้องทึบและยังเป็นสีน้ำเงิน ได้ {(r,g,b,a)}"
print("OK  ลบพื้นหลังขาวอัตโนมัติ (เส้นยังอยู่ครบ)")

# ---- รูปที่มีความโปร่งใสอยู่แล้ว ต้องไม่ไปยุ่ง ----
prepared = PdfDocument.prepare_image(sig_png)
with Image.open(prepared) as p:
    assert p.getpixel((100, 40))[3] == 255, "เส้นเดิมต้องยังอยู่"
    assert p.getpixel((0, 0))[3] == 0
print("OK  รูปที่โปร่งใสอยู่แล้วไม่ถูกแตะ")

# ---- ปิดการลบพื้นหลังได้ ----
prepared = PdfDocument.prepare_image(solid, remove_background=False)
with Image.open(prepared) as p:
    assert p.getpixel((0, 0))[3] == 255, "ปิดแล้วพื้นหลังต้องยังทึบ"
print("OK  ปิดการลบพื้นหลังได้")

# ---- ดับเบิลคลิกลายเซ็น = เข้าโหมดย้าย/ย่อขยายทันที ----
def dbl_click(w, page_pt):
    local = QPoint(int(page_pt.x * w.viewer.zoom), int(page_pt.y * w.viewer.zoom))
    pos = w.viewer._label.mapTo(w.viewer, local)
    w.viewer.mouseDoubleClickEvent(QMouseEvent(
        QEvent.MouseButtonDblClick, QPointF(pos), QPointF(pos),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


w = fresh()
stamp = place(w, fitz.Rect(100, 300, 300, 380))
dbl_click(w, fitz.Point(200, 340))
assert w.viewer.placing, "ดับเบิลคลิกต้องเข้าโหมดแก้ไขเลย"
assert w.viewer.editing_stamp is stamp
assert w._placing_bar.isVisible()

# ย้ายไปที่ใหม่แล้วยืนยัน
w.viewer.overlay.setGeometry(400, 500, 150, 60)
w.commit_placement()
assert len(w.doc.stamps) == 1
assert w.doc.stamps[0].rect == fitz.Rect(400, 500, 550, 560), w.doc.stamps[0].rect
print("OK  ดับเบิลคลิก -> ย้าย/ย่อขยาย -> ยืนยัน")

# ---- ดับเบิลคลิกซ้ำได้เรื่อยๆ ----
for i in range(3):
    here = w.doc.stamps[0].rect
    dbl_click(w, fitz.Point((here.x0 + here.x1) / 2, (here.y0 + here.y1) / 2))
    assert w.viewer.placing, f"รอบที่ {i+1} เข้าโหมดแก้ไขไม่ได้"
    w.viewer.overlay.setGeometry(200 + i * 10, 200, 150, 60)
    w.commit_placement()
assert len(w.doc.stamps) == 1, "ย้ายซ้ำหลายรอบต้องไม่เกิดตัวซ้ำ"
assert w.doc.stamps[0].rect.x0 == 220
print("OK  ดับเบิลคลิกย้ายซ้ำหลายรอบได้")

# ---- ดับเบิลคลิกที่ว่าง ไม่ทำอะไร ----
w = fresh()
place(w, fitz.Rect(100, 300, 300, 380))
dbl_click(w, fitz.Point(500, 700))
assert not w.viewer.placing
print("OK  ดับเบิลคลิกที่ว่างไม่เข้าโหมดแก้ไข")

print("\nผ่านทั้งหมด")
