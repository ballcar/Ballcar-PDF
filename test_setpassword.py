"""ทดสอบตั้ง/เปลี่ยน/ลบรหัสผ่าน PDF"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QRadioButton
from app.main import MainWindow
from app.pdfops import PasswordRequired, PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open(); doc.new_page().insert_text((72, 72), "CONFIDENTIAL", fontsize=20)
src = tmp / "doc.pdf"; doc.save(str(src)); doc.close()


# ---- ตั้งรหัสผ่าน ----
d = PdfDocument(src)
assert not d.is_encrypted
locked = tmp / "locked.pdf"
d.save_with_password(locked, "mypass")

# เปิดโดยไม่ใส่รหัส -> ต้องขอรหัส
try:
    PdfDocument(locked)
except PasswordRequired:
    print("OK  ตั้งรหัสแล้ว เปิดต้องใส่รหัส")
else:
    raise AssertionError("ควรมีรหัส")

# เปิดด้วยรหัสถูก
d2 = PdfDocument(locked, password="mypass")
assert d2.is_encrypted
assert "CONFIDENTIAL" in d2.page_text(0)
print("OK  เปิดด้วยรหัสถูกได้")

# ---- เปลี่ยนรหัส ----
relocked = tmp / "relocked.pdf"
d2.save_with_password(relocked, "newpass")
try:
    PdfDocument(relocked, password="mypass")
except PasswordRequired as e:
    assert e.wrong
    print("OK  เปลี่ยนรหัสแล้ว รหัสเก่าใช้ไม่ได้")
d3 = PdfDocument(relocked, password="newpass")
assert d3.page_count == 1
print("OK  รหัสใหม่ใช้เปิดได้")

# ---- ลบรหัส ----
unlocked = tmp / "unlocked.pdf"
d3.save_with_password(unlocked, "")
d4 = PdfDocument(unlocked)   # ไม่ต้องรหัส
assert not d4.is_encrypted
assert "CONFIDENTIAL" in d4.page_text(0)
print("OK  ลบรหัสแล้วเปิดได้เลย")

# ---- ผ่าน UI: ตั้งรหัส ----
app = QApplication(sys.argv)


def drive(pw1_text, pw2_text, remove=False, accept=True):
    def fake_exec(dlg=None):
        if dlg is None:
            dlg = [x for x in app.topLevelWidgets() if isinstance(x, QDialog)][-1]
        edits = dlg.findChildren(QLineEdit)
        radios = dlg.findChildren(QRadioButton)
        if remove:
            for r in radios:
                if "ลบ" in r.text():
                    r.setChecked(True)
        else:
            if len(edits) >= 2:
                edits[0].setText(pw1_text)
                edits[1].setText(pw2_text)
        dlg.accept() if accept else dlg.reject()
        return QDialog.Accepted if accept else QDialog.Rejected
    return fake_exec


w = MainWindow()
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
ui_out = tmp / "ui_locked.pdf"
with patch.object(QDialog, "exec", drive("secret1", "secret1")), \
     patch("app.main.QFileDialog.getSaveFileName", return_value=(str(ui_out), "")), \
     patch("app.main.QMessageBox.information"):
    w.password_dialog()
assert ui_out.exists()
try:
    PdfDocument(ui_out)
except PasswordRequired:
    print("OK  UI ตั้งรหัสได้")
else:
    raise AssertionError("UI ควรตั้งรหัส")
assert PdfDocument(ui_out, password="secret1").page_count == 1

# ---- UI: รหัสสองช่องไม่ตรง -> เตือน ไม่บันทึก ----
w = MainWindow(); w.doc = PdfDocument(src)
w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
with patch.object(QDialog, "exec", drive("aaa", "bbb")), \
     patch("app.main.QMessageBox.warning") as warn, \
     patch("app.main.QFileDialog.getSaveFileName") as savedlg:
    w.password_dialog()
    assert warn.called, "รหัสไม่ตรงต้องเตือน"
    assert not savedlg.called, "ไม่ควรถึงขั้นบันทึก"
print("OK  UI รหัสสองช่องไม่ตรง เตือนไม่บันทึก")

# ---- UI: ยกเลิก ----
w = MainWindow(); w.doc = PdfDocument(src)
w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
with patch.object(QDialog, "exec", drive("x", "x", accept=False)), \
     patch("app.main.QFileDialog.getSaveFileName") as savedlg:
    w.password_dialog()
    assert not savedlg.called
print("OK  UI กดยกเลิกไม่ทำอะไร")

print("\nผ่านทั้งหมด")
