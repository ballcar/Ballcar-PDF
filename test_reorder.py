"""ทดสอบการสลับลำดับหน้าด้วยการลากวาง (จำลอง drop ผ่าน model.moveRow)"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, r"D:\Project\PDF")

import fitz
from PySide6.QtCore import QModelIndex, Qt
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


def marks():
    return [w.doc.page_text(i).strip() for i in range(w.doc.page_count)]


assert marks() == ["MARK1", "MARK2", "MARK3", "MARK4", "MARK5"], marks()
print("OK  เริ่มต้น", marks())

# ลากหน้า 1 ไปไว้ท้ายสุด
w.thumbs.model().moveRow(QModelIndex(), 0, QModelIndex(), 5)
assert marks() == ["MARK2", "MARK3", "MARK4", "MARK5", "MARK1"], marks()
print("OK  ลากหน้าแรกไปท้าย ->", marks())

# ลากหน้าสุดท้ายกลับมาไว้บนสุด
w.thumbs.model().moveRow(QModelIndex(), 4, QModelIndex(), 0)
assert marks() == ["MARK1", "MARK2", "MARK3", "MARK4", "MARK5"], marks()
print("OK  ลากกลับที่เดิม ->", marks())

# ลากหน้ากลางไปตำแหน่งอื่น
w.thumbs.model().moveRow(QModelIndex(), 3, QModelIndex(), 1)
assert marks() == ["MARK1", "MARK4", "MARK2", "MARK3", "MARK5"], marks()
print("OK  ลากหน้ากลาง ->", marks())

# thumbnail ต้อง sync กับเอกสารจริง (data ถูก reset เป็น 0..n-1 หลัง refresh)
assert [w.thumbs.item(r).data(Qt.UserRole) for r in range(w.thumbs.count())] == [0, 1, 2, 3, 4]
assert w.thumbs.count() == w.doc.page_count
print("OK  thumbnail sync")

# เมนู "ย้ายหน้าขึ้น/ลง" ยังทำงานปกติ
w.thumbs.setCurrentRow(0)
w.move_selected(1)
assert marks() == ["MARK4", "MARK1", "MARK2", "MARK3", "MARK5"], marks()
w.move_selected(-1)
assert marks() == ["MARK1", "MARK4", "MARK2", "MARK3", "MARK5"], marks()
print("OK  เมนูย้ายขึ้น/ลง")

assert w.doc.dirty
w.doc.save(tmp / "out.pdf")
with fitz.open(tmp / "out.pdf") as v:
    assert [v.load_page(i).get_text().strip() for i in range(5)] == marks()
print("OK  บันทึกแล้วลำดับตรง")

print("\nผ่านทั้งหมด")
