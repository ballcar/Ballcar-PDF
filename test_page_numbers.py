"""ทดสอบเพิ่มเลขหน้า: เริ่มใส่ที่หน้าไหนก็ได้ + กำหนดเลขเริ่มต้น (เช่น หน้า 8 ได้เลข 1)"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())


def make_pdf(pages: int) -> Path:
    d = fitz.open()
    for _ in range(pages):
        d.new_page(width=400, height=500)
    p = tmp / f"n{pages}.pdf"
    d.save(str(p)); d.close()
    return p


def bottom_text(doc: PdfDocument, i: int) -> str:
    page = doc.doc.load_page(i)
    clip = fitz.Rect(0, page.rect.height - 60, page.rect.width, page.rect.height)
    return page.get_text(clip=clip).strip()


# ---- หน้า 8 ของไฟล์ 13 หน้า ได้เลข 1 (หน้า 1–7 ไม่มีเลข) ----
doc = PdfDocument(make_pdf(13))
doc.add_page_numbers(fmt="{page}/{total}", first_page=7, start_at=1)
for i in range(7):
    assert bottom_text(doc, i) == "", f"หน้า {i + 1} ต้องไม่มีเลข แต่ได้ {bottom_text(doc, i)!r}"
assert bottom_text(doc, 7) == "1/6", bottom_text(doc, 7)
assert bottom_text(doc, 12) == "6/6", bottom_text(doc, 12)
print("OK  เริ่มที่หน้า 8 ได้เลข 1/6 ถึง 6/6 และหน้า 1–7 ไม่มีเลข")

# ---- ย้อนกลับได้ในขั้นเดียว ----
doc.undo()
assert all(bottom_text(doc, i) == "" for i in range(13)), "Ctrl+Z ต้องลบเลขหน้าออกหมด"
print("OK  ย้อนกลับได้ในขั้นเดียว")

# ---- เลขเริ่มต้นไม่ใช่ 1 ----
doc = PdfDocument(make_pdf(5))
doc.add_page_numbers(fmt="{page}", first_page=2, start_at=10)
assert [bottom_text(doc, i) for i in range(5)] == ["", "", "10", "11", "12"]
print("OK  เริ่มที่หน้า 3 ด้วยเลข 10")

# ---- ค่าเดิม (ไม่ระบุ) ยังใส่ทุกหน้าเหมือนเดิม ----
doc = PdfDocument(make_pdf(3))
doc.add_page_numbers()
assert [bottom_text(doc, i) for i in range(3)] == ["1/3", "2/3", "3/3"]
print("OK  ค่าเริ่มต้นใส่ทุกหน้าเหมือนเดิม")

# ---- รูปแบบภาษาไทยต้องอ่านออก (เดิมใช้ฟอนต์ helv ที่ไม่มีอักษรไทย) ----
doc = PdfDocument(make_pdf(2))
doc.add_page_numbers(fmt="หน้า {page}")
assert bottom_text(doc, 1) == "หน้า 2", bottom_text(doc, 1)
print("OK  รูปแบบ \"หน้า {page}\" แสดงภาษาไทยถูกต้อง")

# ---- รูปแบบผิด / หน้าเริ่มต้นเกิน ต้องไม่แตะไฟล์ ----
doc = PdfDocument(make_pdf(3))
for kwargs in ({"fmt": "{pages}"}, {"first_page": 3}, {"first_page": -1}):
    try:
        doc.add_page_numbers(**kwargs)
    except (KeyError, ValueError):
        pass
    else:
        raise AssertionError(f"{kwargs} ต้องล้ม")
assert all(bottom_text(doc, i) == "" for i in range(3)) and not doc.dirty
print("OK  รูปแบบผิด/หน้าเกิน ล้มก่อนแตะไฟล์")

# ---- หน้าต่างเพิ่มเลขหน้า: ค่าที่เลือกส่งไปถูกต้อง ----
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QSpinBox
from app import main as M

app = QApplication.instance() or QApplication(sys.argv)
w = M.MainWindow()
w.doc = PdfDocument(make_pdf(13))
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)

seen = {}


def fake_exec(dialog):
    spins = dialog.findChildren(QSpinBox)
    combos = dialog.findChildren(QComboBox)
    seen["first_max"] = spins[0].maximum()
    spins[0].setValue(8)          # เริ่มใส่ที่หน้า 8
    spins[1].setValue(1)          # เลข 1
    combos[0].setCurrentIndex(1)  # ล่างขวา
    seen["hint"] = [l.text() for l in dialog.findChildren(M.QLabel) if "–" in l.text()]
    return QDialog.Accepted


with patch.object(QDialog, "exec", fake_exec), \
     patch.object(w.doc, "add_page_numbers", wraps=w.doc.add_page_numbers) as spy:
    w.add_numbers_dialog()

assert seen["first_max"] == 13, "เลือกหน้าเริ่มได้ไม่เกินจำนวนหน้า"
kw = spy.call_args.kwargs
assert kw["first_page"] == 7 and kw["start_at"] == 1 and kw["position"] == "bottom-right", kw
assert any("8–13" in h and "1–6" in h for h in seen["hint"]), seen["hint"]
print("OK  หน้าต่างส่งค่า หน้า 8 = เลข 1 และคำอธิบายบอกช่วงหน้าถูกต้อง")

print("")
print("ผ่านทั้งหมด")
