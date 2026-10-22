"""ทดสอบ UI ผู้ช่วยพิมพ์คำสั่ง"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import QApplication, QMessageBox
from app.main import MainWindow
from app.pdfops import PdfDocument, find_thai_font

tmp = Path(tempfile.mkdtemp())


def make(contents):
    doc = fitz.open()
    for c in contents:
        p = doc.new_page(width=595, height=842)
        if c:
            p.insert_font(fontname="thai", fontfile=find_thai_font())
            p.insert_text((72, 100), c, fontname="thai", fontsize=13)
    path = tmp / f"t{len(list(tmp.glob('*.pdf')))}.pdf"
    doc.save(str(path)); doc.close()
    return path


app = QApplication(sys.argv)


def fresh(src):
    w = MainWindow()
    w.doc = PdfDocument(src)
    w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
    return w


def YES(*a, **k):
    return QMessageBox.Yes


# ---- ลบหน้าว่างผ่านคำสั่ง ----
w = fresh(make(["เนื้อหา", "", "เนื้อหา2", ""]))
with patch("app.main.QMessageBox.question", YES):
    w.run_assistant_command("ลบหน้าว่างทั้งหมด")
assert w.doc.page_count == 2
print("OK  สั่งลบหน้าว่าง -> ทำจริง")

# ---- หมุนแนวนอน ----
w = fresh(make(["ก", "ข"]))
with patch("app.main.QMessageBox.question", YES):
    w.run_assistant_command("หมุนทุกหน้าแนวนอน")
assert w.doc.doc.load_page(0).rect.width > w.doc.doc.load_page(0).rect.height
print("OK  สั่งหมุนแนวนอน")

# ---- เก็บเฉพาะหน้าที่มีคำ ----
w = fresh(make(["ใบเสนอราคา 1", "ใบกำกับ", "ใบเสนอราคา 2"]))
with patch("app.main.QMessageBox.question", YES):
    w.run_assistant_command('ดึงเฉพาะหน้าที่มีคำว่า "ใบเสนอราคา"')
assert w.doc.page_count == 2
print("OK  สั่งเก็บเฉพาะหน้าที่มีคำ")

# ---- เลขหน้าโรมัน ----
w = fresh(make(["a", "b", "c"]))
with patch("app.main.QMessageBox.question", YES):
    w.run_assistant_command("ใส่เลขหน้าเป็นเลขโรมัน")
out = tmp / "r.pdf"; w.doc.save(out)
with fitz.open(out) as v:
    assert "III" in v.load_page(2).get_text()
print("OK  สั่งใส่เลขหน้าโรมัน")

# ---- ลบข้อมูลส่วนบุคคล ----
doc = fitz.open(); p = doc.new_page(width=595, height=842)
p.insert_text((72, 100), "email test@x.com tel 0891234567", fontsize=12)
psrc = tmp / "pii.pdf"; doc.save(str(psrc)); doc.close()
w = fresh(psrc)
with patch("app.main.QMessageBox.question", YES):
    w.run_assistant_command("ลบข้อมูลส่วนบุคคล")
out = tmp / "clean.pdf"; w.doc.save(out)
with fitz.open(out) as v:
    assert "test@x.com" not in v.load_page(0).get_text()
print("OK  สั่งลบข้อมูลส่วนบุคคล")

# ---- แปล -> บอกว่าต้องใช้ AI ออนไลน์ ไม่ทำ ----
w = fresh(make(["hello"]))
with patch("app.main.QMessageBox.information") as info, \
     patch("app.main.QMessageBox.question", return_value=QMessageBox.Yes) as q:
    w.run_assistant_command("แปล PDF เป็นไทย")
    assert info.called
    assert not q.called, "งาน AI ต้องไม่ถามยืนยัน (ตอบก่อนเลย)"
print("OK  แปล -> แจ้งต้องใช้ AI ออนไลน์ ไม่ทำ")

# ---- คำสั่งมั่ว -> แจ้งตัวอย่าง ----
w = fresh(make(["x"]))
with patch("app.main.QMessageBox.information") as info:
    w.run_assistant_command("อยากได้พิซซ่า")
    assert info.called
print("OK  คำสั่งไม่เข้าใจ -> แนะนำตัวอย่าง")

# ---- ยกเลิกตอนยืนยัน -> ไม่ทำ ----
w = fresh(make(["เนื้อหา", ""]))
with patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    w.run_assistant_command("ลบหน้าว่าง")
assert w.doc.page_count == 2, "กดยกเลิกต้องไม่ลบ"
print("OK  กดยกเลิกไม่ทำอะไร")

# ---- ไม่พบหน้าว่าง -> แจ้ง ไม่พัง ----
w = fresh(make(["a", "b"]))
with patch("app.main.QMessageBox.question", YES):
    w.run_assistant_command("ลบหน้าว่าง")
assert w.doc.page_count == 2
print("OK  ไม่พบหน้าว่างก็ไม่พัง")

print("\nผ่านทั้งหมด")
