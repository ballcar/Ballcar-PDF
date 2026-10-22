"""ทดสอบ UI Batch Processing"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QListWidget
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
srcdir = tmp / "in"; srcdir.mkdir()
files = []
for n in range(3):
    doc = fitz.open()
    doc.new_page(width=595, height=842).insert_text((72, 100), f"file {n}", fontsize=12)
    p = srcdir / f"f{n}.pdf"; doc.save(str(p)); doc.close()
    files.append(str(p))

app = QApplication(sys.argv)


def run_batch_dialog(op_key, out_dir, params_patches=None):
    """เปิด batch dialog, ใส่ไฟล์, เลือกงาน, เลือกปลายทาง, รัน"""
    w = MainWindow()
    w.doc = PdfDocument(files[0])
    w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)

    def fake_exec(dlg=None):
        if dlg is None:
            dlg = [x for x in app.topLevelWidgets() if isinstance(x, QDialog)][-1]
        lw = dlg.findChild(QListWidget)
        for f in files:
            lw.addItem(f)
        combo = dlg.findChild(QComboBox)
        # เลือกงานตาม key
        for i in range(combo.count()):
            if combo.itemData(i) == op_key:
                combo.setCurrentIndex(i)
                break
        dlg.accept()
        return QDialog.Accepted

    patches = [
        patch.object(QDialog, "exec", fake_exec),
        patch("app.main.QFileDialog.getExistingDirectory", return_value=str(out_dir)),
        patch("app.main.QMessageBox.information"),
    ]
    for p in (params_patches or []):
        patches.append(p)
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        w.batch_dialog()
    return w


# ---- ลายน้ำผ่าน UI ----
out = tmp / "o_wm"
run_batch_dialog("watermark_text", out,
                 [patch("app.main.QInputDialog.getText", return_value=("ลับ", True))])
assert len(list(out.glob("*-watermark.pdf"))) == 3
with fitz.open(next(out.glob("*-watermark.pdf"))) as v:
    assert "ลับ" in v.load_page(0).get_text()
print("OK  ลายน้ำ batch ผ่าน UI (ไทยติด)")

# ---- เพิ่มเลขหน้าผ่าน UI (ไม่ต้องถามพารามิเตอร์) ----
out = tmp / "o_num"
run_batch_dialog("page_numbers", out)
assert len(list(out.glob("*-numbered.pdf"))) == 3
print("OK  เพิ่มเลขหน้า batch ผ่าน UI")

# ---- แปลง Word ผ่าน UI ----
out = tmp / "o_word"
run_batch_dialog("to_word", out)
assert len(list(out.glob("*.docx"))) == 3
print("OK  แปลง Word batch ผ่าน UI")

# ---- ตั้งรหัสผ่าน UI ----
out = tmp / "o_pw"
run_batch_dialog("set_password", out,
                 [patch("app.main.QInputDialog.getText", return_value=("secret", True))])
from app.pdfops import PasswordRequired
locked = next(out.glob("*-locked.pdf"))
try:
    PdfDocument(locked)
except PasswordRequired:
    pass
else:
    raise AssertionError("ควรมีรหัส")
print("OK  ตั้งรหัส batch ผ่าน UI")

# ---- รวมไฟล์ผ่าน UI ----
w = MainWindow()
w.doc = PdfDocument(files[0]); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
merged = tmp / "merged.pdf"

def fake_exec_merge(dlg=None):
    if dlg is None:
        dlg = [x for x in app.topLevelWidgets() if isinstance(x, QDialog)][-1]
    lw = dlg.findChild(QListWidget)
    for f in files:
        lw.addItem(f)
    combo = dlg.findChild(QComboBox)
    for i in range(combo.count()):
        if combo.itemData(i) == "merge":
            combo.setCurrentIndex(i); break
    dlg.accept()
    return QDialog.Accepted

with patch.object(QDialog, "exec", fake_exec_merge), \
     patch("app.main.QFileDialog.getSaveFileName", return_value=(str(merged), "")), \
     patch("app.main.QMessageBox.information"):
    w.batch_dialog()
with fitz.open(merged) as v:
    assert v.page_count == 3
print("OK  รวมไฟล์ batch ผ่าน UI")

# ---- ไม่เลือกไฟล์ -> แจ้ง ----
w = MainWindow()
w.doc = PdfDocument(files[0]); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
def fake_exec_empty(dlg=None):
    if dlg is None:
        dlg = [x for x in app.topLevelWidgets() if isinstance(x, QDialog)][-1]
    dlg.accept()
    return QDialog.Accepted
with patch.object(QDialog, "exec", fake_exec_empty), \
     patch("app.main.QMessageBox.information") as info:
    w.batch_dialog()
    assert info.called
print("OK  ไม่เลือกไฟล์แจ้งเตือน")

print("\nผ่านทั้งหมด")
