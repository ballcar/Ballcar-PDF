"""ทดสอบเปิดไฟล์ PDF ที่มีรหัสผ่าน"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import QApplication, QLineEdit
from app.main import MainWindow
from app.pdfops import PasswordRequired, PdfDocument

tmp = Path(tempfile.mkdtemp())

# ไฟล์ปกติ
plain = fitz.open(); plain.new_page().insert_text((72, 72), "hello");
psrc = tmp / "plain.pdf"; plain.save(str(psrc)); plain.close()

# ไฟล์ใส่รหัส (owner+user password = "secret")
enc = fitz.open(); enc.new_page().insert_text((72, 72), "SECRET-DATA", fontsize=20)
esrc = tmp / "locked.pdf"
enc.save(str(esrc), encryption=fitz.PDF_ENCRYPT_AES_256,
         user_pw="secret", owner_pw="secret")
enc.close()


# ---- เปิดไฟล์ปกติ ไม่ต้องรหัส ----
d = PdfDocument(psrc)
assert d.page_count == 1
print("OK  ไฟล์ปกติเปิดได้ตามเดิม")

# ---- ไฟล์มีรหัส เปิดโดยไม่ใส่รหัส -> PasswordRequired ----
try:
    PdfDocument(esrc)
except PasswordRequired as exc:
    assert exc.wrong is False
    print("OK  ไฟล์มีรหัส เปิดเปล่าๆ -> ขอรหัส")
else:
    raise AssertionError("ควรต้องขอรหัส")

# ---- ใส่รหัสผิด -> PasswordRequired(wrong=True) ----
try:
    PdfDocument(esrc, password="wrong")
except PasswordRequired as exc:
    assert exc.wrong is True
    print("OK  รหัสผิดแจ้งว่าผิด")
else:
    raise AssertionError("รหัสผิดควร error")

# ---- ใส่รหัสถูก -> เปิดได้ ----
d = PdfDocument(esrc, password="secret")
assert d.page_count == 1
assert "SECRET-DATA" in d.page_text(0)
print("OK  ใส่รหัสถูกเปิดได้ อ่านเนื้อหาได้")

# ---- บันทึกแล้วเปิดใหม่ได้ (ไม่ติดรหัสแล้ว) ----
out = tmp / "unlocked.pdf"
d.save(out)
d2 = PdfDocument(out)   # ไม่ต้องรหัส
assert "SECRET-DATA" in d2.page_text(0)
print("OK  บันทึกแล้วได้ไฟล์ที่เปิดได้ปกติ")

# ---- ผ่าน UI: ถามรหัสแล้วเปิด ----
app = QApplication(sys.argv)
w = MainWindow()
with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(esrc), "")), \
     patch("app.main.QInputDialog.getText", return_value=("secret", True)):
    w.open_file()
assert w.doc is not None and w.doc.page_count == 1
assert "SECRET-DATA" in w.doc.page_text(0)
print("OK  UI ถามรหัสแล้วเปิดไฟล์ได้")

# ---- UI: ใส่รหัสผิดแล้วถูก (loop) ----
w = MainWindow()
attempts = iter([("bad", True), ("secret", True)])
with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(esrc), "")), \
     patch("app.main.QInputDialog.getText", side_effect=lambda *a, **k: next(attempts)):
    w.open_file()
assert w.doc is not None and w.doc.page_count == 1
print("OK  UI ใส่รหัสผิดแล้วลองใหม่จนถูก")

# ---- UI: กดยกเลิกตอนถามรหัส -> ไม่เปิด ----
w = MainWindow()
before = w.doc
with patch("app.main.QFileDialog.getOpenFileName", return_value=(str(esrc), "")), \
     patch("app.main.QInputDialog.getText", return_value=("", False)):
    w.open_file()
assert w.doc is before, "กดยกเลิกต้องไม่เปลี่ยนเอกสาร"
print("OK  UI กดยกเลิกตอนถามรหัส ไม่เปิด")

print("\nผ่านทั้งหมด")
