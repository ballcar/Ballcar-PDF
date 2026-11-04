"""ทดสอบปิดทับคำที่ค้นหาทุกหน้า (2.2): ปิดทุกจุด, บันทึกแล้วข้อความหายจากไฟล์จริง, ย้อนกลับได้"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit, QRadioButton
from app import i18n
from app.main import MainWindow
from app.pdfops import PdfDocument

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())
src = tmp / "doc.pdf"
d = fitz.open()
for n in range(3):
    p = d.new_page(width=595, height=842)
    p.insert_text((72, 100), f"Customer ID 1234567890123 page {n + 1}", fontsize=14)
    p.insert_text((72, 140), "Account 555-1-23456 keep this line", fontsize=14)
d[2].set_rotation(90)
d.save(str(src)); d.close()

# ---- ปิดทุกจุดของหลายคำ ----
doc = PdfDocument(src)
found = doc.find_text_rects(["1234567890123", "555-1-23456"])
assert sum(len(v) for v in found.values()) == 6 and sorted(found) == [0, 1, 2]
n = doc.cover_text(["1234567890123", "555-1-23456"])
assert n == 6 and len(doc.erasers) == 6 and doc.dirty
assert all(e.color == (0.0, 0.0, 0.0) for e in doc.erasers)
print("OK  ปิดทับทุกจุดของหลายคำพร้อมกัน (3 หน้า รวมหน้าหมุน)")

# ---- ย้อนกลับได้ก่อนบันทึก ----
assert doc.undo() and not doc.erasers
assert doc.redo()
assert len(doc.erasers) == 6
print("OK  Ctrl+Z ย้อนกลับได้")

# ---- บันทึกแล้วข้อความใต้แผ่นปิดหายจริง (คัดลอก/ค้นหาไม่ได้) แต่ข้อความอื่นยังอยู่ ----
out = tmp / "covered.pdf"
doc.save(out)
with fitz.open(str(out)) as saved:
    text = "".join(pg.get_text() for pg in saved)
    assert "1234567890123" not in text and "555-1-23456" not in text, "ข้อความที่ปิดต้องหายจากไฟล์"
    assert text.count("Customer ID") == 3 and text.count("keep this line") == 3
print("OK  บันทึกแล้วข้อความใต้แผ่นปิดถูกลบออกจริง ข้อความรอบข้างยังอยู่")

# ---- สีพื้นกระดาษ ----
doc2 = PdfDocument(src)
doc2.cover_text(["1234567890123"], color=None)
assert all(min(e.color) > 0.9 for e in doc2.erasers), "พื้นขาว -> แผ่นปิดสีขาว"
assert doc2.cover_text(["ไม่มีคำนี้"]) == 0
print("OK  เลือกสีพื้นกระดาษได้ · ไม่เจอคำ = ไม่ทำอะไร")

# ---- ผ่านหน้าต่างโปรแกรม: พิมพ์คำ เห็นจำนวน แล้วกดปิดทับ ----
w = MainWindow(); w.resize(1200, 800); w.show(); app.processEvents()
w._open_path(str(src)); app.processEvents()
w.search_box.setText("1234567890123")


def fill_and_accept(dialog):
    edit = dialog.findChild(QPlainTextEdit)
    assert edit.toPlainText() == "1234567890123", "ต้องเติมคำจากช่องค้นหาไว้ให้"
    edit.setPlainText("1234567890123\n555-1-23456")
    app.processEvents()
    paper = [r for r in dialog.findChildren(QRadioButton) if r.text() == i18n.t("cover.paper")][0]
    paper.setChecked(True)
    return QDialog.Accepted


with patch.object(QDialog, "exec", fill_and_accept):
    w.cover_text_dialog()
app.processEvents()
assert len(w.doc.erasers) == 6 and min(w.doc.erasers[0].color) > 0.9
acts = {a.text(): a for a in w.tool_actions}
assert i18n.t("tools.cover_text") in acts
print("OK  เมนูเครื่องมือ → ปิดทับคำที่ค้นหา: เติมคำจากช่องค้นหา เลือกสี แล้วปิดทุกจุด")

for tab in w._tabs:
    tab["doc"].dirty = False
print("\nผ่านทั้งหมด")
