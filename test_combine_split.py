"""ทดสอบ: รวมไฟล์หลายไฟล์, แยกหน้าละไฟล์, แทรกหลายไฟล์"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp / "appdata")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app.pdfops import PdfDocument, merge_files


def make(name, pages, tag=None):
    doc = fitz.open()
    for i in range(pages):
        doc.new_page(width=400, height=300).insert_text(
            (50, 60), f"{tag or name}-p{i + 1}", fontsize=14)
    path = tmp / f"{name}.pdf"
    doc.save(str(path)); doc.close()
    return path


a = make("A", 3)
b = make("B", 2)
c = make("C", 4)

# ============ แยกหน้าละไฟล์ ============
big = make("BIG", 12)
d = PdfDocument(big)
out = tmp / "each"
prog = []
files = d.split_to_files(out, progress=lambda done, total: prog.append((done, total)))
assert len(files) == 12, f"12 หน้า ต้องได้ 12 ไฟล์ ได้ {len(files)}"
assert all(f.exists() for f in files)
# แต่ละไฟล์ต้องมี 1 หน้า และเป็นหน้าที่ถูกต้อง
for i, f in enumerate(files):
    with fitz.open(f) as v:
        assert v.page_count == 1, f"{f.name} ต้องมี 1 หน้า"
        assert f"BIG-p{i + 1}" in v.load_page(0).get_text(), f"{f.name} เนื้อหาไม่ตรงหน้า {i+1}"
# ชื่อไฟล์เรียงเลขให้เรียงถูก (zero-padded)
names = [f.name for f in files]
assert names == sorted(names), f"ชื่อไฟล์ต้องเรียงถูกตามเลขหน้า: {names[:3]}"
assert prog and prog[-1] == (12, 12), prog
print(f"OK  แยกหน้าละไฟล์ 12 หน้า = 12 ไฟล์ ({names[0]} … {names[-1]})")

# ต้นฉบับไม่ถูกแตะ
assert d.page_count == 12
print("OK  แยกไฟล์ไม่แตะต้นฉบับ")

# ---- แยกทุกๆ N หน้า ----
out5 = tmp / "every5"
files5 = d.split_to_files(out5, per_file=5)
assert len(files5) == 3, f"12 หน้า ทุก 5 หน้า = 3 ไฟล์ ได้ {len(files5)}"
with fitz.open(files5[0]) as v:
    assert v.page_count == 5
with fitz.open(files5[-1]) as v:
    assert v.page_count == 2, "ไฟล์สุดท้ายมี 2 หน้าที่เหลือ"
print("OK  แยกทุกๆ 5 หน้า = 3 ไฟล์ (5+5+2)")

# ---- แยกไฟล์รวมข้อความที่เพิ่มไว้ (ยังไม่บันทึก) ----
d2 = PdfDocument(a)
d2.add_textbox(0, fitz.Rect(40, 150, 350, 190), "ข้อความที่เพิ่ม", font_size=14)
outx = tmp / "withtext"
fx = d2.split_to_files(outx)
with fitz.open(fx[0]) as v:
    assert "ข้อความที่เพิ่ม" in v.load_page(0).get_text(), "ของที่เพิ่มไว้ต้องติดไปในไฟล์ที่แยก"
print("OK  แยกไฟล์รวมข้อความที่เพิ่มไว้ด้วย")

# ============ รวมไฟล์ ============
merged = tmp / "merged.pdf"
merge_files([a, b, c], merged)
with fitz.open(merged) as v:
    assert v.page_count == 9, f"3+2+4 = 9 หน้า ได้ {v.page_count}"
    # ลำดับต้องตามที่ส่งมา
    assert "A-p1" in v.load_page(0).get_text()
    assert "B-p1" in v.load_page(3).get_text()
    assert "C-p1" in v.load_page(5).get_text()
print("OK  รวม 3 ไฟล์ตามลำดับถูกต้อง (9 หน้า)")

# ============ แทรกหลายไฟล์ ============
d3 = PdfDocument(a)                      # 3 หน้า
added = d3.insert_pdfs(1, [b, c])        # แทรก B(2) + C(4) ที่ตำแหน่งหน้า 2
assert added == 6, f"ต้องแทรก 6 หน้า ได้ {added}"
assert d3.page_count == 9
# ลำดับ: A1, B1, B2, C1..C4, A2, A3
assert "A-p1" in d3.page_text(0)
assert "B-p1" in d3.page_text(1) and "B-p2" in d3.page_text(2)
assert "C-p1" in d3.page_text(3) and "C-p4" in d3.page_text(6)
assert "A-p2" in d3.page_text(7)
print("OK  แทรกหลายไฟล์เรียงลำดับถูก (A1,B1,B2,C1-4,A2,A3)")

# undo ครั้งเดียวเอาออกหมด
d3.undo()
assert d3.page_count == 3, "undo ต้องเอาทุกไฟล์ที่แทรกออกในครั้งเดียว"
print("OK  undo แทรกหลายไฟล์ = ครั้งเดียว")

# แทรกรายการว่าง ไม่พัง
assert d3.insert_pdfs(0, []) == 0
print("OK  แทรกรายการว่างไม่พัง")

# ============ UI ============
from PySide6.QtWidgets import (QApplication, QDialog, QListWidget, QMessageBox,
                               QRadioButton, QSpinBox)
from app.main import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def fresh(path=a):
    w = MainWindow()
    w.doc = PdfDocument(path); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
    w.resize(1000, 700); w.show()
    return w


# ---- แทรกหลายไฟล์ผ่าน UI ----
w = fresh()
with patch("app.main.QFileDialog.getOpenFileNames", return_value=([str(b), str(c)], "")):
    w.insert_pdf_file()
assert w.doc.page_count == 9, f"ต้องได้ 9 หน้า ได้ {w.doc.page_count}"
print("OK  แทรกหลายไฟล์ผ่าน UI (เลือกหลายไฟล์ได้)")

# ---- รวมไฟล์ผ่าน UI (มีไฟล์ปัจจุบันเป็นตัวแรก + จัดลำดับ) ----
w = fresh()
target = tmp / "ui_merged.pdf"

def fill_merge(dlg):
    lw = dlg.findChild(QListWidget)
    assert lw.count() == 1 and lw.item(0).text() == str(a), "ควรมีไฟล์ที่เปิดอยู่เป็นตัวแรก"
    lw.addItem(str(b)); lw.addItem(str(c))

with patch.object(QDialog, "exec", lambda self: (fill_merge(self), QDialog.Accepted)[1]), \
     patch("app.main.QFileDialog.getSaveFileName", return_value=(str(target), "")), \
     patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    w.merge_dialog()
assert target.exists()
with fitz.open(target) as v:
    assert v.page_count == 9
print("OK  รวมไฟล์ผ่าน UI (ไฟล์ที่เปิดอยู่เป็นตัวแรก)")

# ---- รวมไฟล์: ไฟล์เดียวต้องเตือน ----
w = fresh()
with patch.object(QDialog, "exec", lambda self: QDialog.Accepted), \
     patch("app.main.QMessageBox.information") as info:
    w.merge_dialog()
    assert info.called, "มีไฟล์เดียวต้องเตือน"
print("OK  รวมไฟล์: ไฟล์เดียวเตือน ไม่ทำต่อ")

# ---- แยกหน้าละไฟล์ผ่าน UI ----
w = fresh(big)
folder = tmp / "ui_split"
def fill_split(dlg):
    radios = dlg.findChildren(QRadioButton)
    radios[0].setChecked(True)      # หน้าละไฟล์
with patch.object(QDialog, "exec", lambda self: (fill_split(self), QDialog.Accepted)[1]), \
     patch("app.main.QFileDialog.getExistingDirectory", return_value=str(folder)), \
     patch("app.main.QMessageBox.information") as info:
    w.split_dialog()
made = sorted(folder.glob("*.pdf"))
assert len(made) == 12, f"ต้องได้ 12 ไฟล์ ได้ {len(made)}"
assert info.called
print("OK  แยกหน้าละไฟล์ผ่าน UI (12 ไฟล์)")

# ---- แยกทุกๆ N หน้า ผ่าน UI ----
w = fresh(big)
folder2 = tmp / "ui_split_n"
def fill_split_n(dlg):
    radios = dlg.findChildren(QRadioButton)
    radios[1].setChecked(True)      # ทุกๆ N หน้า
    dlg.findChild(QSpinBox).setValue(4)
with patch.object(QDialog, "exec", lambda self: (fill_split_n(self), QDialog.Accepted)[1]), \
     patch("app.main.QFileDialog.getExistingDirectory", return_value=str(folder2)), \
     patch("app.main.QMessageBox.information"):
    w.split_dialog()
made2 = sorted(folder2.glob("*.pdf"))
assert len(made2) == 3, f"12 หน้า ทุก 4 = 3 ไฟล์ ได้ {len(made2)}"
print("OK  แยกทุกๆ N หน้า ผ่าน UI")

# ---- แยกช่วงหน้าเป็นไฟล์เดียว (แบบเดิม) ยังใช้ได้ ----
w = fresh(big)
one = tmp / "range.pdf"
def fill_range(dlg):
    from PySide6.QtWidgets import QLineEdit
    dlg.findChildren(QRadioButton)[2].setChecked(True)
    dlg.findChild(QLineEdit).setText("1-3,5")
with patch.object(QDialog, "exec", lambda self: (fill_range(self), QDialog.Accepted)[1]), \
     patch("app.main.QFileDialog.getSaveFileName", return_value=(str(one), "")):
    w.split_dialog()
with fitz.open(one) as v:
    assert v.page_count == 4, f"1-3,5 = 4 หน้า ได้ {v.page_count}"
print("OK  แยกช่วงหน้าเป็นไฟล์เดียว (แบบเดิม) ยังใช้ได้")

print("\nผ่านทั้งหมด")


# ============ คลิกขวาใน Explorer -> รวมไฟล์ ============
from app.main import pdf_files_from_argv, initial_file_from_argv, COMBINE_FLAG

# เก็บทุกไฟล์ pdf ที่มีจริง ข้ามสวิตช์
argv = ["app.exe", COMBINE_FLAG, str(a), str(b), str(c)]
got = pdf_files_from_argv(argv)
assert got == [str(a), str(b), str(c)], got
print("OK  อ่านหลายไฟล์จาก argument (ข้ามสวิตช์ --combine)")

# ไฟล์ไม่มีจริง/ไม่ใช่ pdf ต้องถูกข้าม
other = tmp / "x.txt"; other.write_text("hi")
assert pdf_files_from_argv(["app.exe", str(other), str(tmp / "ghost.pdf"), str(a)]) == [str(a)]
print("OK  ข้ามไฟล์ที่ไม่ใช่ .pdf และไฟล์ที่ไม่มีอยู่")

# เปิดไฟล์เดียว (double-click) ยังได้ไฟล์แรก
assert initial_file_from_argv(["app.exe", str(b)]) == str(b)
assert initial_file_from_argv(["app.exe"]) is None
print("OK  เปิดไฟล์เดียวยังทำงานเหมือนเดิม")

# ---- merge_dialog รับ preset_files (ใส่ไฟล์ที่คลิกขวาไว้ให้เลย) ----
w = MainWindow()          # ไม่เปิดไฟล์ใดๆ (เหมือนตอนเรียกจาก Explorer)
w.doc = None
target2 = tmp / "from_explorer.pdf"
seen = {}

def check_preset(dlg):
    lw = dlg.findChild(QListWidget)
    seen["items"] = [lw.item(i).text() for i in range(lw.count())]

with patch.object(QDialog, "exec", lambda self: (check_preset(self), QDialog.Accepted)[1]), \
     patch("app.main.QFileDialog.getSaveFileName", return_value=(str(target2), "")), \
     patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    w.merge_dialog(preset_files=[str(a), str(b), str(c)])

assert seen["items"] == [str(a), str(b), str(c)], seen
assert target2.exists()
with fitz.open(target2) as v:
    assert v.page_count == 9, f"3+2+4=9 ได้ {v.page_count}"
print("OK  merge_dialog รับไฟล์จาก Explorer แล้วรวมได้ (9 หน้า)")

print("\nผ่านทั้งหมด (รวมคลิกขวา Explorer)")


# ---- ตัวรวบไฟล์: ตัวอื่นส่งไฟล์มาแล้วเติมเข้าหน้าต่างเดียว ----
from app.main import _try_become_collector, _attach_combine_handler, _send_to_combine_collector, _COMBINE_KEY
from PySide6.QtNetwork import QLocalServer

QLocalServer.removeServer(_COMBINE_KEY)

w = MainWindow(); w.doc = None
# ยังไม่มีตัวรวบ -> ส่งไม่ได้
assert _send_to_combine_collector([str(a)], timeout_ms=200) is False
print("OK  ยังไม่มีตัวรวบ -> ส่งไม่ได้ (ตัวนี้เป็นตัวรวบเอง)")

server = _try_become_collector()
assert server is not None
_attach_combine_handler(server, w)
assert server is not None, "ต้องเปิดช่องรับได้"
app.processEvents()

# จำลองหน้าต่างรวมไฟล์เปิดอยู่พร้อมไฟล์แรก
w._merge_list = QListWidget()
w._merge_list.addItem(str(a))

# ตัวอื่นส่งไฟล์ที่ 2 และ 3 มา (เหมือน Windows เรียกทีละไฟล์)
assert _send_to_combine_collector([str(b)]) is True
assert _send_to_combine_collector([str(c)]) is True
for _ in range(20):
    app.processEvents()

items = [w._merge_list.item(i).text() for i in range(w._merge_list.count())]
assert len(items) == 3, f"ต้องรวบได้ 3 ไฟล์ ได้ {len(items)}: {items}"
assert set(items) == {str(a), str(b), str(c)}, items
assert items == sorted(items), f"ควรเรียงตามชื่อไฟล์: {items}"
print(f"OK  ตัวรวบได้ครบ 3 ไฟล์ในหน้าต่างเดียว ({len(items)} ไฟล์ เรียงตามชื่อ)")

# ส่งไฟล์ซ้ำ ไม่เพิ่มซ้ำ
_send_to_combine_collector([str(b)])
for _ in range(20):
    app.processEvents()
assert w._merge_list.count() == 3, "ไฟล์ซ้ำไม่ควรเพิ่ม"
print("OK  ส่งไฟล์ซ้ำไม่เพิ่มรายการซ้ำ")

# ปิดหน้าต่างแล้วไม่รับเพิ่ม (ไม่ crash)
w._merge_list = None
_send_to_combine_collector([str(a)])
for _ in range(10):
    app.processEvents()
print("OK  ปิดหน้าต่างแล้วส่งมาไม่พัง")

server.close()
QLocalServer.removeServer(_COMBINE_KEY)
print("\nผ่านทั้งหมด (รวมตัวรวบไฟล์)")


# ---- คลิกขวาที่หน้าที่เลือก -> เมนู "แยกเป็นไฟล์ละหน้า" ----
from PySide6.QtCore import QPoint

w = fresh(big)          # 12 หน้า
# เลือก 3 หน้า (1, 3, 5)
w.thumbs.clearSelection()
for r in (0, 2, 4):
    w.thumbs.item(r).setSelected(True)
menu = w.build_thumb_menu(QPoint(5, 5))
labels = [a.text() for a in menu.actions() if a.text()]
assert any("แยก" in x and "ไฟล์ละหน้า" in x for x in labels), labels
assert any("3 หน้าที่เลือก" in x and "แยก" in x for x in labels), labels
print("OK  เมนูคลิกขวามีรายการ 'แยกเป็นไฟล์ละหน้า' (บอกจำนวนหน้าที่เลือก)")

# กดแล้วได้ไฟล์ละหน้า เฉพาะหน้าที่เลือก
folder3 = tmp / "sel_each"
with patch("app.main.QFileDialog.getExistingDirectory", return_value=str(folder3)), \
     patch("app.main.QMessageBox.information") as info:
    w.split_selected_each_page()
made3 = sorted(folder3.glob("*.pdf"))
assert len(made3) == 3, f"เลือก 3 หน้า ต้องได้ 3 ไฟล์ ได้ {len(made3)}"
assert info.called
# ต้องเป็นหน้าที่เลือกจริง (หน้า 1, 3, 5)
texts = []
for f in made3:
    with fitz.open(f) as v:
        assert v.page_count == 1
        texts.append(v.load_page(0).get_text().strip())
assert any("BIG-p1" in x for x in texts) and any("BIG-p3" in x for x in texts) \
    and any("BIG-p5" in x for x in texts), texts
assert not any("BIG-p2" in x for x in texts), "ไม่ควรมีหน้าที่ไม่ได้เลือก"
print(f"OK  แยกเฉพาะหน้าที่เลือกเป็นไฟล์ละหน้า ({[f.name for f in made3]})")

# กดยกเลิกตอนเลือกโฟลเดอร์ -> ไม่สร้างไฟล์ ไม่พัง
with patch("app.main.QFileDialog.getExistingDirectory", return_value=""):
    w.split_selected_each_page()
print("OK  กดยกเลิกเลือกโฟลเดอร์ ไม่พัง")

print("\nผ่านทั้งหมด (รวมเมนูแยกไฟล์)")
