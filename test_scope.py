"""ทดสอบตัวเลือกขอบเขตหน้า (ทุกหน้า/หน้าปัจจุบัน/ที่เลือก/ระบุช่วง)"""
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
for i in range(8):
    doc.new_page(width=595, height=842)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

app = QApplication(sys.argv)


def fresh():
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc)
    w._refresh_all(keep_row=0)
    return w


w = fresh()
w.thumbs.setCurrentRow(2)   # อยู่หน้า 3

# ---- ทุกหน้า ----
with patch("app.main.QInputDialog.getItem", return_value=("ทุกหน้า (8 หน้า)", True)):
    assert w._ask_scope("t") == list(range(8))
print("OK  ทุกหน้า")

# ---- หน้าปัจจุบัน ----
with patch("app.main.QInputDialog.getItem", return_value=("หน้าปัจจุบัน (หน้า 3)", True)):
    assert w._ask_scope("t") == [2], "หน้าปัจจุบันคือ index 2 (หน้า 3)"
print("OK  หน้าปัจจุบัน")

# ---- ระบุช่วงหน้าเอง: หน้าเดียว ----
with patch("app.main.QInputDialog.getItem", return_value=("ระบุช่วงหน้าเอง…", True)), \
     patch("app.main.QInputDialog.getText", return_value=("5", True)):
    assert w._ask_scope("t") == [4], "หน้า 5 = index 4"
print("OK  ระบุหน้าเดียว (5)")

# ---- ระบุช่วงหน้า: หลายช่วง ----
with patch("app.main.QInputDialog.getItem", return_value=("ระบุช่วงหน้าเอง…", True)), \
     patch("app.main.QInputDialog.getText", return_value=("2-4,7", True)):
    assert w._ask_scope("t") == [1, 2, 3, 6], w._ask_scope
print("OK  ระบุช่วงหน้า (2-4,7)")

# ---- ระบุช่วงผิด -> เตือน คืน None ----
with patch("app.main.QInputDialog.getItem", return_value=("ระบุช่วงหน้าเอง…", True)), \
     patch("app.main.QInputDialog.getText", return_value=("99", True)), \
     patch("app.main.QMessageBox.warning") as warn:
    assert w._ask_scope("t") is None
    assert warn.called, "ช่วงผิดต้องเตือน"
print("OK  ระบุช่วงผิดเตือนไม่พัง")

# ---- เลือกหลายหน้าใน thumbnail -> มีตัวเลือก 'ที่เลือก' ----
w.thumbs.clearSelection()
w.thumbs.item(0).setSelected(True)
w.thumbs.item(1).setSelected(True)
w.thumbs.item(5).setSelected(True)
captured = {}
def grab_items(parent, title, label, items, *a, **k):
    captured["items"] = items
    return (items[0], True)
with patch("app.main.QInputDialog.getItem", side_effect=grab_items):
    w._ask_scope("t")
assert any("เฉพาะหน้าที่เลือกไว้ (3 หน้า)" in it for it in captured["items"]), captured["items"]
print("OK  เลือกหลายหน้าใน thumbnail มีตัวเลือก 'ที่เลือก'")

# เลือกตัวเลือก 'ที่เลือก'
sel = [it for it in captured["items"] if "เฉพาะหน้าที่เลือกไว้" in it][0]
with patch("app.main.QInputDialog.getItem", return_value=(sel, True)):
    assert sorted(w._ask_scope("t")) == [0, 1, 5]
print("OK  เลือกหน้าที่เลือกไว้ได้ถูก")

# ---- ยกเลิก -> None ----
with patch("app.main.QInputDialog.getItem", return_value=("", False)):
    assert w._ask_scope("t") is None
print("OK  ยกเลิกคืน None")

print("\nผ่านทั้งหมด")
