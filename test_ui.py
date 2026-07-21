"""ทดสอบเมนูคลิกขวา — สร้างเมนูจริงแล้วยิง action ตามชื่อ"""
import sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, r"D:\Project\PDF")

import fitz
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QMessageBox
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(5):
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 120), f"MARK{i+1}", fontsize=30)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

app = QApplication(sys.argv)
w = MainWindow()
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)

marks = lambda: [w.doc.page_text(i).strip() for i in range(w.doc.page_count)]

# คลิกขวาในที่ว่าง (ไม่โดน thumbnail) -> ใช้หน้าที่เลือกไว้อยู่แล้ว
BLANK = QPoint(5, 100000)


def click(menu, name_part):
    for a in menu.actions():
        if name_part in a.text():
            a.trigger()
            return
    raise AssertionError(f"ไม่เจอเมนู '{name_part}' ใน {[a.text() for a in menu.actions()]}")


# ---- เมนูคลิกขวาที่ thumbnail ----
w.thumbs.setCurrentRow(1)
menu = w.build_thumb_menu(BLANK)
texts = [a.text() for a in menu.actions() if a.text()]
assert any("หมุนซ้าย" in t for t in texts), texts
assert any("ลบ" in t for t in texts), texts
assert any("หน้า 2" in t for t in texts), texts
print("OK  เมนู thumbnail:", texts)

# คลิกขวาบนหน้าที่ยังไม่ได้เลือก -> ต้องสลับมาหน้านั้น
w.thumbs.setCurrentRow(0)
on_page3 = w.thumbs.visualItemRect(w.thumbs.item(2)).center()
m3 = w.build_thumb_menu(on_page3)
assert any("หน้า 3" in a.text() for a in m3.actions()), [a.text() for a in m3.actions()]
print("OK  คลิกขวาหน้าที่ยังไม่ได้เลือก -> สลับมาหน้านั้น")

w.thumbs.setCurrentRow(1)
click(w.build_thumb_menu(BLANK), "หมุนขวา")
assert w.doc.doc.load_page(1).rotation == 90
click(w.build_thumb_menu(BLANK), "หมุนซ้าย")
assert w.doc.doc.load_page(1).rotation == 0
print("OK  คลิกขวา -> หมุนซ้าย/ขวา")

click(w.build_thumb_menu(BLANK), "แทรกหน้าว่างหลัง")
assert w.doc.page_count == 6 and w.doc.page_text(2).strip() == ""
print("OK  แทรกหน้าว่างหลังหน้านี้")

# ลบหน้าเดียว = ไม่ถาม
w.thumbs.setCurrentRow(2)
with patch.object(QMessageBox, "question") as q:
    click(w.build_thumb_menu(BLANK), "ลบ")
    assert not q.called, "ลบหน้าเดียวไม่ควรถาม"
assert marks() == ["MARK1", "MARK2", "MARK3", "MARK4", "MARK5"], marks()
print("OK  ลบหน้าเดียวไม่ถามยืนยัน")

# ลบหลายหน้า = ต้องถาม
w.thumbs.setCurrentRow(0)
w.thumbs.item(1).setSelected(True)
w.thumbs.item(0).setSelected(True)
with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes) as q:
    click(w.build_thumb_menu(BLANK), "ลบ")
    assert q.called, "ลบหลายหน้าต้องถามยืนยัน"
assert marks() == ["MARK3", "MARK4", "MARK5"], marks()
print("OK  ลบหลายหน้า (ถามยืนยัน)")

# ยกเลิกการลบต้องไม่ลบจริง
w.thumbs.setCurrentRow(0)
w.thumbs.item(1).setSelected(True)
w.thumbs.item(0).setSelected(True)
with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
    click(w.build_thumb_menu(BLANK), "ลบ")
assert marks() == ["MARK3", "MARK4", "MARK5"], marks()
print("OK  กดยกเลิกแล้วไม่ลบ")

# ---- บันทึกหน้าที่เลือกเป็นไฟล์ใหม่ ----
w.thumbs.clearSelection()
w.thumbs.setCurrentRow(0)
w.thumbs.item(0).setSelected(True)
assert w._selected_rows() == [0], w._selected_rows()
out = tmp / "sel.pdf"
with patch("app.main.QFileDialog.getSaveFileName", return_value=(str(out), "")):
    click(w.build_thumb_menu(BLANK), "เป็นไฟล์ PDF ใหม่")
with fitz.open(out) as v:
    assert v.page_count == 1 and "MARK3" in v.load_page(0).get_text()
print("OK  บันทึกหน้าที่เลือกเป็นไฟล์ใหม่")

# ---- เมนูคลิกขวาบนวิวเออร์ ----
w.viewer.show_page(1)
vm = w.build_viewer_menu()
texts = [a.text() for a in vm.actions() if a.text()]
assert any("หมุนขวา" in t for t in texts) and any("ลบหน้านี้" in t for t in texts), texts
click(vm, "หมุนขวา")
assert w.doc.doc.load_page(1).rotation == 90
print("OK  เมนูวิวเออร์:", texts)

before = w.doc.page_count
click(w.build_viewer_menu(), "ลบหน้านี้")
assert w.doc.page_count == before - 1
print("OK  ลบจากวิวเออร์")

# ลบจนเหลือหน้าเดียวแล้วลบอีก -> ต้องเตือน ไม่ใช่พัง
while w.doc.page_count > 1:
    click(w.build_viewer_menu(), "ลบหน้านี้")
with patch.object(QMessageBox, "warning") as warn:
    click(w.build_viewer_menu(), "ลบหน้านี้")
    assert warn.called, "ลบหน้าสุดท้ายต้องเตือน"
assert w.doc.page_count == 1
print("OK  ลบหน้าสุดท้ายไม่ได้ (เตือนแทน)")

# ไม่มีเอกสาร -> ไม่มีเมนู ไม่พัง
w.doc = None
w.viewer.set_document(None)
assert w.build_thumb_menu(BLANK) is None
assert w.build_viewer_menu() is None
w._thumb_context_menu(BLANK)
w._viewer_context_menu(BLANK)
print("OK  ไม่มีเอกสารก็ไม่พัง")

print("\nผ่านทั้งหมด")
