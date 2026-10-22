"""ทดสอบ UI ของการเพิ่ม/แก้ไขข้อความ"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(2):
    doc.new_page(width=595, height=842)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

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


def click(w, page_pt, dbl=False):
    off = w.viewer._page_offset()   # ภาพหน้าอาจถูกวางกึ่งกลาง ต้องบวกด้วย
    local = QPoint(int(page_pt.x * w.viewer.zoom) + off.x(),
                   int(page_pt.y * w.viewer.zoom) + off.y())
    pos = w.viewer._label.mapTo(w.viewer, local)
    etype = QEvent.MouseButtonDblClick if dbl else QEvent.MouseButtonPress
    handler = w.viewer.mouseDoubleClickEvent if dbl else w.viewer.mousePressEvent
    handler(QMouseEvent(etype, QPointF(pos), QPointF(pos),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


# ---- เพิ่มข้อความ: เข้าโหมดคลิกจุด ----
w = fresh()
w.add_text_dialog()
assert w.viewer._picking_point, "ต้องเข้าโหมดรอคลิกจุด"
print("OK  กด 'เพิ่มข้อความ' เข้าโหมดรอคลิกจุด")

# คลิกจุด -> เด้ง dialog กรอกข้อความ
with patch.object(w, "_ask_text_content", return_value=("ทดสอบข้อความ", "", False, True)):
    click(w, fitz.Point(150, 200))
assert not w.viewer._picking_point, "คลิกแล้วต้องออกจากโหมดคลิกจุด"
assert len(w.doc.textboxes) == 1
box = w.doc.textboxes[0]
assert box.text == "ทดสอบข้อความ"
assert box.page == 0
assert w.viewer.selected_textbox is box
assert w._text_bar.isVisible()
print("OK  คลิกจุดแล้วกรอกข้อความ -> เพิ่มกล่อง + แถบเครื่องมือโผล่")

# ---- ยังไม่ฝังลงไฟล์ ----
assert "ทดสอบ" not in w.doc.page_text(0)
print("OK  ยังไม่บันทึก ยังไม่ฝังลงไฟล์")

# ---- คลิกที่ว่าง = เลิกเลือก ----
click(w, fitz.Point(400, 600))
assert w.viewer.selected_textbox is None
print("OK  คลิกที่ว่างเลิกเลือก")

# ---- คลิกโดนกล่อง = เลือกได้ ----
click(w, fitz.Point(160, 210))
assert w.viewer.selected_textbox is box
assert w._text_bar.isVisible()
print("OK  คลิกโดนกล่องข้อความเลือกได้")

# ---- ดับเบิลคลิก = แก้คำ ----
with patch.object(w, "_ask_text_content", return_value=("แก้ไขแล้ว", "", False, True)):
    click(w, fitz.Point(160, 210), dbl=True)
assert box.text == "แก้ไขแล้ว", box.text
print("OK  ดับเบิลคลิกแก้คำได้")

# ---- ปุ่มแก้คำบนแถบ ----
with patch.object(w, "_ask_text_content", return_value=("จากปุ่ม", "", False, True)):
    w.edit_selected_textbox()
assert box.text == "จากปุ่ม"
print("OK  ปุ่มแก้คำบนแถบทำงาน")

# ---- ย้าย/ปรับขนาด ----
w.viewer.selected_textbox = box
w.move_selected_textbox()
assert w.viewer.placing and w.viewer.editing_textbox is box
assert len(w.doc.textboxes) == 1, "ระหว่างแก้ต้องไม่เกิดกล่องใหม่"
w.viewer.overlay.setGeometry(300 + w.viewer._page_offset().x(), 400 + w.viewer._page_offset().y(), 250, 60)
w.commit_placement()
assert len(w.doc.textboxes) == 1
assert w.doc.textboxes[0].rect == fitz.Rect(300, 400, 550, 460), w.doc.textboxes[0].rect
print("OK  ย้าย/ปรับขนาดข้อความ ไม่เกิดกล่องซ้ำ")

# ---- ลากมุมย่อ/ขยาย -> ตัวอักษรปรับตาม ----
w = fresh()
with patch.object(w, "_ask_text_content", return_value=("ปรับขนาด", "", False, True)):
    w.add_text_dialog()
    click(w, fitz.Point(100, 100))
box = w.doc.textboxes[0]
orig_size = box.font_size
orig_h = box.rect.height
w.viewer.selected_textbox = box
w.move_selected_textbox()
# ขยายกล่องให้สูงเป็น 2 เท่า
g = w.viewer.overlay.geometry()
w.viewer.overlay.setGeometry(g.x(), g.y(), g.width() * 2, g.height() * 2)
w.commit_placement()
new_size = w.doc.textboxes[0].font_size
assert new_size > orig_size * 1.7, f"ขยายกล่องแล้วฟอนต์ต้องใหญ่ขึ้น {orig_size}->{new_size}"
print(f"OK  ลากมุมขยาย ตัวอักษรใหญ่ตาม ({orig_size:.0f}->{new_size:.0f})")

# ย่อกลับ
box = w.doc.textboxes[0]
big = box.font_size
w.viewer.selected_textbox = box
w.move_selected_textbox()
g = w.viewer.overlay.geometry()
w.viewer.overlay.setGeometry(g.x(), g.y(), g.width() // 2, g.height() // 2)
w.commit_placement()
assert w.doc.textboxes[0].font_size < big * 0.7, "ย่อกล่องแล้วฟอนต์ต้องเล็กลง"
print("OK  ลากมุมย่อ ตัวอักษรเล็กตาม")

# ---- ย้ายเฉยๆ (ไม่เปลี่ยนขนาด) ฟอนต์ต้องเท่าเดิม ----
box = w.doc.textboxes[0]
same = box.font_size
w.viewer.selected_textbox = box
w.move_selected_textbox()
g = w.viewer.overlay.geometry()
w.viewer.overlay.setGeometry(g.x() + 40, g.y() + 40, g.width(), g.height())  # ย้ายอย่างเดียว
w.commit_placement()
assert abs(w.doc.textboxes[0].font_size - same) < 0.6, "ย้ายเฉยๆ ฟอนต์ต้องไม่เปลี่ยน"
print("OK  ย้ายเฉยๆ ฟอนต์คงเดิม")

# ---- เปลี่ยนสี ----
from PySide6.QtGui import QColor
w.viewer.selected_textbox = box
with patch("PySide6.QtWidgets.QColorDialog.getColor", return_value=QColor(255, 0, 0)):
    w.color_selected_textbox()
assert box.color[0] > 0.9 and box.color[1] < 0.1, box.color
print("OK  เปลี่ยนสีข้อความได้")

# ---- undo (หลัง undo อ็อบเจกต์กล่องถูกสร้างใหม่ ต้องอ่านจาก doc) ----
w.undo()
assert w.doc.textboxes[0].color[0] < 0.1, "undo สีกลับเป็นเดิม"
print("OK  undo การเปลี่ยนสี")

# ---- Delete = ลบกล่อง (ไม่ใช่ลบหน้า) ----
pages_before = w.doc.page_count
w.viewer.selected_textbox = w.doc.textboxes[0]
w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
assert w.doc.textboxes == []
assert w.doc.page_count == pages_before
print("OK  Delete ลบกล่องข้อความ ไม่เผลอลบหน้า")

# ---- บันทึกแล้วฝังลงไฟล์ ----
w = fresh()
with patch.object(w, "_ask_text_content", return_value=("Invoice 2023", "", False, True)):
    w.add_text_dialog()
    click(w, fitz.Point(100, 150))
out = tmp / "saved.pdf"
w.doc.save(out)
with fitz.open(out) as v:
    assert "Invoice 2023" in v.load_page(0).get_text()
print("OK  บันทึกแล้วฝังลงไฟล์")

# ---- Esc ยกเลิกโหมดคลิกจุด ----
w = fresh()
w.add_text_dialog()
w.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
assert not w.viewer._picking_point
print("OK  Esc ยกเลิกโหมดคลิกจุด")

# ---- ยกเลิก dialog = ไม่เพิ่มกล่อง ----
w = fresh()
w.add_text_dialog()
with patch.object(w, "_ask_text_content", return_value=("", "", False, False)):
    click(w, fitz.Point(150, 200))
assert w.doc.textboxes == []
print("OK  ยกเลิก dialog ไม่เพิ่มกล่อง")

print("\nผ่านทั้งหมด")
