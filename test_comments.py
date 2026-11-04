"""ทดสอบโน้ตและแผงความคิดเห็น (2.2)"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication, QInputDialog
from app import i18n
from app.main import MainWindow
from app.pdfops import PdfDocument

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())

# ไฟล์ที่มีโน้ตและไฮไลต์มาจากโปรแกรมอื่นอยู่แล้ว (เช่น Acrobat)
src = tmp / "doc.pdf"
d = fitz.open()
for n in range(3):
    page = d.new_page(width=595, height=842)
    page.insert_text((72, 100), f"Quarterly report page {n + 1}", fontsize=16)
p1, p0 = d[1], d[0]          # เก็บ page ไว้ ไม่งั้น annotation หลุดจากหน้าก่อน update
note = p1.add_text_annot((300, 300), "ช่วยเช็กตัวเลขหน้านี้")
note.set_info(title="Somchai"); note.update()
hl = p0.add_highlight_annot(p0.search_for("Quarterly report"))
hl.update()
d.save(str(src)); d.close()

# ---- อ่านความคิดเห็นที่มากับไฟล์ ----
doc = PdfDocument(src)
cs = doc.comments()
assert [(c["page"], c["kind"]) for c in cs] == [(0, "highlight"), (1, "note")], cs
assert cs[0]["text"].startswith("Quarterly report") and "page 1" not in cs[0]["text"], "ไฮไลต์ไม่มีโน้ต ต้องแสดงข้อความที่ถูกไฮไลต์"
assert cs[1]["text"] == "ช่วยเช็กตัวเลขหน้านี้" and cs[1]["author"] == "Somchai"
print("OK  อ่านโน้ต/ไฮไลต์ที่มากับไฟล์ (พร้อมชื่อผู้เขียน)")

# ---- แปะโน้ต แก้ ลบ ย้อนกลับ บันทึกแล้วเปิดที่อื่นยังเห็น ----
xref = doc.add_note(2, fitz.Point(100, 200), "แก้ชื่อลูกค้าตรงนี้", author="Ball")
assert doc.note_at(2, fitz.Point(105, 205)) == xref, "คลิกไอคอนโน้ตต้องเจอโน้ตนั้น"
assert doc.note_at(2, fitz.Point(400, 600)) is None
doc.edit_comment(2, xref, "แก้ชื่อลูกค้า + ที่อยู่")
assert [c["text"] for c in doc.comments() if c["page"] == 2] == ["แก้ชื่อลูกค้า + ที่อยู่"]
doc.delete_comment([c for c in doc.comments() if c["page"] == 2][0])
assert not [c for c in doc.comments() if c["page"] == 2]
assert doc.undo() and len([c for c in doc.comments() if c["page"] == 2]) == 1, "ลบแล้วย้อนกลับได้"
out = tmp / "out.pdf"
doc.save(out)
with fitz.open(str(out)) as saved:
    annot = next(saved[2].annots(types=[fitz.PDF_ANNOT_TEXT]))
    assert annot.info["content"] == "แก้ชื่อลูกค้า + ที่อยู่" and annot.info["title"] == "Ball"
print("OK  แปะ/แก้/ลบโน้ต ย้อนกลับได้ บันทึกเป็นโน้ตมาตรฐาน PDF (โปรแกรมอื่นเห็น)")

# ---- หน้าหมุน: โน้ตไปอยู่ตรงจุดที่คลิกบนจอ ----
rot = PdfDocument(src)
rot.rotate_pages([0], 90)
x = rot.add_note(0, fitz.Point(50, 80), "หน้าหมุน")
c = [c for c in rot.comments() if c["xref"] == x][0]
assert c["rect"].contains(fitz.Point(52, 82)), c["rect"]
print("OK  หน้าที่หมุนอยู่ โน้ตอยู่ตรงจุดที่คลิก")

# ---- หน้าต่างโปรแกรม: แผงความคิดเห็น ----
w = MainWindow()
w.resize(1300, 800); w.show(); app.processEvents()
w._open_path(str(src)); app.processEvents()
panel = w.comments_panel
assert not panel.isVisible()
w.act_show_comments.setChecked(True); app.processEvents()
assert panel.isVisible() and panel.list.count() == 2
assert panel.title.text() == i18n.t("cm.title", n=2)
print("OK  มุมมอง → แสดงความคิดเห็น เปิดแผงพร้อมรายการทั้งไฟล์")

panel.goRequested.emit(panel.list.item(1).data(0x0100)); app.processEvents()
assert w.viewer.index == 1, "คลิกรายการต้องไปหน้านั้น"

# เพิ่มโน้ตผ่านปุ่ม -> คลิกจุดบนหน้า -> พิมพ์ข้อความ
panel.add_button.click()
assert w.viewer._picking_point and w.viewer._pick_mode == "note"
with patch.object(QInputDialog, "getMultiLineText", return_value=("ส่งให้ฝ่ายบัญชี", True)):
    w.viewer.notePointPicked.emit(2, 120.0, 150.0)
app.processEvents()
assert panel.list.count() == 3 and w.doc.dirty
assert panel.current() and panel.current()["text"] == "ส่งให้ฝ่ายบัญชี", "โน้ตที่เพิ่งแปะต้องถูกเลือกไว้"
assert w.tab_bar.tabText(0).endswith("*")
print("OK  ปุ่ม + โน้ต → คลิกจุด → พิมพ์ → แปะโน้ต แผงเลือกโน้ตใหม่ไว้ให้")

# แก้ผ่านแผง (ดับเบิลคลิก)
with patch.object(QInputDialog, "getMultiLineText", return_value=("ส่งให้ฝ่ายบัญชีภายในวันศุกร์", True)) as ask:
    panel.editRequested.emit(panel.current())
    assert ask.call_args[0][3] == "ส่งให้ฝ่ายบัญชี", "กล่องแก้ต้องเติมข้อความเดิมไว้"
app.processEvents()
assert any(c["text"] == "ส่งให้ฝ่ายบัญชีภายในวันศุกร์" for c in w.doc.comments())

# คลิกไอคอนโน้ตบนหน้า = เลือกในแผง
w.viewer.noteClicked.emit(1, w.doc.comments()[1]["xref"]); app.processEvents()
assert panel.current()["author"] == "Somchai"

# รูปวาดที่ยังไม่บันทึกก็อยู่ในแผง ลบได้
w.doc.add_annotation(0, "rect", [(100, 400), (200, 450)])
w._refresh_all(keep_row=0); app.processEvents()
drawing = [panel.list.item(i).data(0x0100) for i in range(panel.list.count())
           if panel.list.item(i).data(0x0100)["kind"] == "drawing"]
assert len(drawing) == 1 and drawing[0]["floating"] is not None
panel.deleteRequested.emit(drawing[0]); app.processEvents()
assert not w.doc.annotations and panel.list.count() == 3
print("OK  แก้โน้ต / คลิกไอคอนบนหน้า / ลบรูปวาด จากแผงได้")

# สลับแท็บ -> แผงแสดงของไฟล์นั้น
other = tmp / "blank.pdf"
b = fitz.open(); b.new_page(); b.save(str(other)); b.close()
w._open_path(str(other)); app.processEvents()
assert panel.list.count() == 0 and panel.empty.isVisible()
w.tab_bar.setCurrentIndex(0); app.processEvents()
assert panel.list.count() == 3
print("OK  สลับแท็บ แผงความคิดเห็นเปลี่ยนตามไฟล์")

for tab in w._tabs:
    tab["doc"].dirty = False
print("\nผ่านทั้งหมด")
