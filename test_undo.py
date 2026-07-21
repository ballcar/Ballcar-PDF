"""ทดสอบ undo / redo"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from PySide6.QtWidgets import QApplication
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
ORIG = ["MARK1", "MARK2", "MARK3", "MARK4", "MARK5"]

assert not w.doc.can_undo and not w.doc.can_redo
assert not w.act_undo.isEnabled()
print("OK  เริ่มต้นยังย้อนกลับไม่ได้")

# ลบแล้วย้อนกลับ
w.thumbs.setCurrentRow(1)
w.delete_selected()
assert marks() == ["MARK1", "MARK3", "MARK4", "MARK5"], marks()
assert w.act_undo.isEnabled()
w.undo()
assert marks() == ORIG, marks()
print("OK  ลบ -> undo กลับมาครบ")

w.redo()
assert marks() == ["MARK1", "MARK3", "MARK4", "MARK5"], marks()
w.undo()
assert marks() == ORIG
print("OK  redo แล้ว undo อีกที")

# หมุนแล้วย้อนกลับ
w.thumbs.setCurrentRow(0)
w.rotate_selected(90)
assert w.doc.doc.load_page(0).rotation == 90
w.undo()
assert w.doc.doc.load_page(0).rotation == 0
print("OK  หมุน -> undo")

# ลากสลับลำดับแล้วย้อนกลับ
from PySide6.QtCore import QModelIndex
w.thumbs.model().moveRow(QModelIndex(), 0, QModelIndex(), 5)
assert marks() == ["MARK2", "MARK3", "MARK4", "MARK5", "MARK1"], marks()
w.undo()
assert marks() == ORIG, marks()
print("OK  ลากสลับลำดับ -> undo")

# หลายขั้นซ้อนกัน
w.thumbs.setCurrentRow(0); w.delete_selected()
w.thumbs.setCurrentRow(0); w.delete_selected()
w.thumbs.setCurrentRow(0); w.delete_selected()
assert marks() == ["MARK4", "MARK5"], marks()
w.undo(); w.undo(); w.undo()
assert marks() == ORIG, marks()
assert not w.doc.can_undo
print("OK  undo หลายขั้นติดกัน")

# แก้ไขใหม่หลัง undo -> redo ต้องหายไป
w.thumbs.setCurrentRow(0); w.delete_selected()
w.undo()
assert w.doc.can_redo
w.thumbs.setCurrentRow(4); w.delete_selected()
assert not w.doc.can_redo, "แก้ไขใหม่แล้ว redo ต้องถูกล้าง"
w.undo()
assert marks() == ORIG
print("OK  แก้ไขใหม่แล้ว redo ถูกล้าง")

# undo แล้วบันทึกทับไฟล์เดิม (เอกสารอยู่ในหน่วยความจำ)
w.thumbs.setCurrentRow(0); w.delete_selected()
w.undo()
w.doc.save()
with fitz.open(src) as v:
    assert [v.load_page(i).get_text().strip() for i in range(v.page_count)] == ORIG
assert not w.doc.dirty
print("OK  undo แล้วบันทึกทับไฟล์เดิมได้")

# บันทึกแล้วยังแก้ต่อ + undo ได้อีก
w.thumbs.setCurrentRow(0); w.delete_selected()
w.doc.save()
with fitz.open(src) as v:
    assert v.page_count == 4
w.undo()
w.doc.save()
with fitz.open(src) as v:
    assert v.page_count == 5
print("OK  บันทึก -> แก้ต่อ -> undo -> บันทึกอีก")

# เพิ่มเลขหน้าแล้ว undo
w.doc.add_page_numbers(fmt="{page}/{total}")
assert "/5" in w.doc.page_text(4)
w.undo()
assert "/5" not in w.doc.page_text(4)
print("OK  เพิ่มเลขหน้า -> undo")

# กด undo รัวๆ เกินประวัติต้องไม่พัง
for _ in range(30):
    w.undo()
assert marks() == ORIG, marks()
for _ in range(30):
    w.redo()
print("OK  กด undo/redo รัวๆ ไม่พัง")

print("\nผ่านทั้งหมด")
