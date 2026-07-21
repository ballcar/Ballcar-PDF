"""ทดสอบ UI กรอกแบบฟอร์ม"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QLineEdit
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())


def make_form() -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    for name, ftype, rect, choices in [
        ("customer", fitz.PDF_WIDGET_TYPE_TEXT, (100, 100, 300, 118), None),
        ("agree", fitz.PDF_WIDGET_TYPE_CHECKBOX, (100, 150, 114, 164), None),
        ("payment", fitz.PDF_WIDGET_TYPE_COMBOBOX, (100, 200, 250, 218),
         ["Cash", "Credit"]),
    ]:
        w = fitz.Widget()
        w.field_name = name
        w.field_type = ftype
        w.rect = fitz.Rect(rect)
        if choices:
            w.choice_values = choices
        page.add_widget(w)
    path = tmp / "form.pdf"
    doc.save(str(path)); doc.close()
    return path


src = make_form()
plain = fitz.open(); plain.new_page(); pp = tmp / "plain.pdf"; plain.save(str(pp)); plain.close()

app = QApplication(sys.argv)


def fresh(path=src):
    w = MainWindow()
    w.doc = PdfDocument(path)
    w.viewer.set_document(w.doc)
    w._refresh_all(keep_row=0)
    w.resize(900, 700)
    return w


def drive_dialog(fill_values, click="editable"):
    """คืนฟังก์ชันแทน QDialog.exec — หา dialog ที่เปิดอยู่ กรอกค่า แล้วกดปุ่ม"""
    from PySide6.QtWidgets import QPushButton

    def fake_exec(dlg=None):
        if dlg is None:
            dialogs = [x for x in app.topLevelWidgets() if isinstance(x, QDialog)]
            dlg = dialogs[-1] if dialogs else None
        assert dlg is not None, "ไม่เจอ dialog"
        edits = dlg.findChildren(QLineEdit)
        checks = dlg.findChildren(QCheckBox)
        combos = dlg.findChildren(QComboBox)
        if "customer" in fill_values and edits:
            edits[0].setText(fill_values["customer"])
        if "agree" in fill_values and checks:
            checks[0].setChecked(fill_values["agree"])
        if "payment" in fill_values and combos:
            combos[0].setCurrentText(fill_values["payment"])
        target = "ตรึง" if click == "flatten" else "ยังแก้ได้"
        for b in dlg.findChildren(QPushButton):
            if target in b.text():
                b.click()
                break
        return QDialog.Accepted if dlg.result() == QDialog.Accepted else QDialog.Rejected
    return fake_exec


# ---- ไฟล์ไม่มีฟอร์ม -> แจ้ง ----
w = fresh(pp)
with patch("app.main.QMessageBox.information") as info:
    w.fill_form_dialog()
    assert info.called
print("OK  ไฟล์ไม่มีฟอร์มแจ้งผู้ใช้")

# ---- กรอกแบบแก้ต่อได้ ----
w = fresh()
with patch.object(QDialog, "exec",
                  drive_dialog({"customer": "John Smith", "agree": True, "payment": "Credit"}, "editable")):
    w.fill_form_dialog()
vals = {f["name"]: f["value"] for f in w.doc.form_fields()}
assert vals["customer"] == "John Smith", vals
assert vals["payment"] == "Credit"
assert w.doc.is_form(), "แบบแก้ต่อได้ ต้องยังเป็นฟอร์ม"
print("OK  กรอกแบบแก้ต่อได้ (ยังเป็นฟอร์ม)")

# ---- กรอกแล้วตรึง (ไทย) ----
w = fresh()
with patch.object(QDialog, "exec",
                  drive_dialog({"customer": "สมชาย ใจดี", "agree": True, "payment": "Credit"}, "flatten")):
    w.fill_form_dialog()
assert not w.doc.is_form(), "ตรึงแล้วต้องไม่เป็นฟอร์ม"
out = tmp / "flat.pdf"
w.doc.save(out)
with fitz.open(out) as v:
    text = v.load_page(0).get_text()
    assert "สมชาย" in text, f"ไทยต้องแสดงเป็นเนื้อหา: {text!r}"
    assert "Credit" in text
print("OK  กรอกแล้วตรึง ภาษาไทยแสดงถูก")

# ---- ยกเลิก dialog ไม่กรอก ----
w = fresh()
with patch.object(QDialog, "exec", return_value=QDialog.Rejected):
    w.fill_form_dialog()
vals = {f["name"]: f["value"] for f in w.doc.form_fields()}
assert vals["customer"] in ("", None)
print("OK  ยกเลิก dialog ไม่กรอกอะไร")

print("\nผ่านทั้งหมด")
