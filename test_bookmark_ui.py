"""ทดสอบ UI Bookmarks"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(6):
    doc.new_page(width=595, height=842).insert_text((72, 72), f"page {i+1}")
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

app = QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc)
    w._refresh_all(keep_row=0)
    w.resize(1100, 800)
    w.show()
    return w


# ---- เปิด panel ----
w = fresh()
w._toggle_bookmark_panel(True)
assert w._bookmark_panel.isVisible()
print("OK  เปิด panel bookmark")

# ---- เพิ่ม bookmark หน้าปัจจุบัน ----
w.thumbs.setCurrentRow(2)   # หน้า 3
with patch("app.main.QInputDialog.getText", return_value=("บทที่ 2", True)):
    w.add_bookmark_current()
bms = w.doc.get_bookmarks()
assert len(bms) == 1 and bms[0]["title"] == "บทที่ 2" and bms[0]["page"] == 2
assert w._bookmark_tree.topLevelItemCount() == 1
print("OK  เพิ่ม bookmark หน้าปัจจุบัน")

# ---- คลิก bookmark กระโดดไปหน้า ----
w.thumbs.setCurrentRow(0)   # กลับหน้า 1
item = w._bookmark_tree.topLevelItem(0)
w._on_bookmark_clicked(item, 0)
assert w.viewer.index == 2, f"ต้องกระโดดไปหน้า 3 ได้ {w.viewer.index}"
print("OK  คลิก bookmark กระโดดไปหน้าถูก")

# ---- เพิ่มอีกอัน + เปลี่ยนชื่อ ----
w.thumbs.setCurrentRow(4)
w._bookmark_tree.clearSelection()      # ไม่เลือกอะไร -> ต่อท้าย
with patch("app.main.QInputDialog.getText", return_value=("บทที่ 3", True)):
    w.add_bookmark_current()
assert len(w.doc.get_bookmarks()) == 2
# เลือกตัวแรกแล้วเปลี่ยนชื่อ
w._bookmark_tree.setCurrentItem(w._bookmark_tree.topLevelItem(0))
with patch("app.main.QInputDialog.getText", return_value=("บทที่ 1 บทนำ", True)):
    w.rename_bookmark()
assert w.doc.get_bookmarks()[0]["title"] == "บทที่ 1 บทนำ"
print("OK  เปลี่ยนชื่อ bookmark")

# ---- ปรับระดับย่อย ----
w._refresh_bookmarks()
# เลือกตัวที่ 2 แล้วทำเป็นระดับย่อย
items = [w._bookmark_tree.topLevelItem(i) for i in range(w._bookmark_tree.topLevelItemCount())]
# หา item ที่ index ข้อมูล = 1
def find_item(idx):
    for i in range(w._bookmark_tree.topLevelItemCount()):
        it = w._bookmark_tree.topLevelItem(i)
        if it.data(0, 1000) == idx or it.data(0, 0x0100) == idx:
            return it
    return None
w._bookmark_tree.setCurrentItem(w._bookmark_tree.topLevelItem(1))
w._change_bookmark_level(+1)
assert w.doc.get_bookmarks()[1]["level"] == 2
print("OK  ปรับระดับ bookmark ย่อยได้ (แสดงเป็น tree)")

# tree ต้องแสดงแบบมีลูก
w._refresh_bookmarks()
assert w._bookmark_tree.topLevelItemCount() == 1
assert w._bookmark_tree.topLevelItem(0).childCount() == 1
print("OK  tree แสดง bookmark ย่อยเป็นลูก")

# ---- ลบ ----
w._bookmark_tree.setCurrentItem(w._bookmark_tree.topLevelItem(0))
n_before = len(w.doc.get_bookmarks())
w.remove_bookmark()
assert len(w.doc.get_bookmarks()) == n_before - 1
print("OK  ลบ bookmark")

# ---- ไม่เลือกอะไรแล้วกดลบ/เปลี่ยนชื่อ ไม่พัง ----
w._bookmark_tree.clearSelection()
w._bookmark_tree.setCurrentItem(None)
w.remove_bookmark()   # ไม่ควร error
w.rename_bookmark()
print("OK  ไม่เลือกอะไรก็ไม่พัง")

# ---- บันทึกแล้วเปิดใหม่ bookmark ยังอยู่ ----
w.thumbs.setCurrentRow(0)
with patch("app.main.QInputDialog.getText", return_value=("ทดสอบบันทึก", True)):
    w.add_bookmark_current()
out = tmp / "saved.pdf"
w.doc.save(out)
d2 = PdfDocument(out)
assert any(b["title"] == "ทดสอบบันทึก" for b in d2.get_bookmarks())
print("OK  บันทึกแล้ว bookmark ติดไปในไฟล์")

print("\nผ่านทั้งหมด")
