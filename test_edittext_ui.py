"""ทดสอบ UI ของการแก้ข้อความเดิม"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument, find_thai_font

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
page = doc.new_page(width=595, height=842)
page.insert_font(fontname="thai", fontfile=find_thai_font())
page.insert_text((100, 100), "Invoice No. ABC123", fontsize=14)
page.insert_text((100, 200), "ชื่อ สมชาย", fontname="thai", fontsize=16)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

# ไฟล์สแกน
scan = fitz.open()
sp = scan.new_page(width=595, height=842)
sp.insert_image(sp.rect, pixmap=fitz.open(src)[0].get_pixmap(dpi=100))
scan_src = tmp / "scan.pdf"
scan.save(str(scan_src)); scan.close()

app = QApplication(sys.argv)


def fresh(path=src):
    w = MainWindow()
    w.doc = PdfDocument(path)
    w.viewer.set_document(w.doc)
    w.viewer.set_zoom(1.0)
    w._refresh_all(keep_row=0)
    w.resize(1000, 800)
    w.show()
    return w


def click(w, page_pt):
    local = QPoint(int(page_pt.x * w.viewer.zoom), int(page_pt.y * w.viewer.zoom))
    pos = w.viewer._label.mapTo(w.viewer, local)
    w.viewer.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(pos), QPointF(pos),
                                         Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


# ---- เข้าโหมดแก้ข้อความ ----
w = fresh()
w.edit_text_dialog()
assert w.viewer._picking_point and w.viewer._pick_mode == "edit"
print("OK  เข้าโหมดคลิกข้อความเดิม")

# ---- คลิกข้อความ -> เด้ง dialog เติมคำเดิม -> แก้ ----
with patch.object(w, "_ask_text_content", return_value=("Invoice No. XYZ999", True)):
    click(w, fitz.Point(150, 96))
assert not w.viewer._picking_point
assert len(w.doc.textboxes) == 1
assert "ABC123" not in w.doc.page_text(0), "ข้อความเดิมต้องถูกลบ"
assert w.viewer.selected_textbox.text == "Invoice No. XYZ999"
assert w._text_bar.isVisible()
print("OK  คลิกข้อความเดิม -> ลบ + เติมคำใหม่")

# ---- บันทึกแล้วเป็นคำใหม่ ----
out = tmp / "out.pdf"
w.doc.save(out)
with fitz.open(out) as v:
    text = v.load_page(0).get_text()
    assert "XYZ999" in text and "ABC123" not in text, text
print("OK  บันทึกแล้วคำใหม่แทนที่คำเดิม")

# ---- ยกเลิก dialog = คงคำเดิมไว้ในกล่อง (แต่เดิมถูกลบไปแล้ว จึงเท่าเดิม) ----
w = fresh()
w.edit_text_dialog()
with patch.object(w, "_ask_text_content", return_value=("", False)):
    click(w, fitz.Point(150, 196))
assert len(w.doc.textboxes) == 1
assert "สมชาย" in w.doc.textboxes[0].text, "ยกเลิกแล้วยังคงคำเดิมในกล่อง"
print("OK  ยกเลิก dialog ยังคงคำเดิมในกล่อง")

# ---- คลิกที่ว่าง -> แจ้งไม่มีข้อความ ----
w = fresh()
w.edit_text_dialog()
click(w, fitz.Point(450, 600))
assert w.doc.textboxes == []
print("OK  คลิกที่ว่างไม่มีข้อความให้แก้")

# ---- ไฟล์สแกน -> เตือน ไม่เข้าโหมด ----
w = fresh(scan_src)
with patch("app.main.QMessageBox.information") as info:
    w.edit_text_dialog()
    assert info.called, "ไฟล์สแกนต้องเตือน"
assert not w.viewer._picking_point
print("OK  ไฟล์สแกนเตือน ไม่เข้าโหมดแก้")

print("\nผ่านทั้งหมด")
