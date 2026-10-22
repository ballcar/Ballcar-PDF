"""ทดสอบ 2 อย่าง: จำข้อความที่เคยพิมพ์ (เดาคำ) และใส่ข้อความตำแหน่งเดิมทุกหน้า"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()      # settings.json แยก ไม่กวนของจริง
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from app import assistant, i18n
from app import main as M
from app.main import MainWindow, date_suggestions, remember_text, text_history
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
d = fitz.open()
for i in range(4):
    d.new_page(width=595, height=842).insert_text((60, 80), f"PAGE {i+1}", fontsize=16)
src = tmp / "doc.pdf"
d.save(str(src)); d.close()

app = QApplication.instance() or QApplication(sys.argv)

# ================= ความจำข้อความที่เคยพิมพ์ =================

assert text_history() == [], "เครื่องใหม่ยังไม่มีประวัติ"
remember_text("03/08/2026")
remember_text("บริษัท ออมใจ จำกัด")
assert text_history() == ["บริษัท ออมใจ จำกัด", "03/08/2026"], text_history()
print("OK  จำข้อความที่พิมพ์ ใหม่สุดอยู่บนสุด")

# พิมพ์ซ้ำต้องเลื่อนขึ้นมาบนสุด ไม่เก็บซ้ำ
remember_text("03/08/2026")
assert text_history() == ["03/08/2026", "บริษัท ออมใจ จำกัด"]
assert text_history().count("03/08/2026") == 1, "ต้องไม่เก็บซ้ำ"
print("OK  พิมพ์ซ้ำ -> เลื่อนขึ้นบนสุด ไม่เก็บซ้ำ")

# ไม่เก็บของที่ไม่เหมาะ (ว่าง / หลายบรรทัด / ยาวเกิน)
before = text_history()
remember_text("")
remember_text("   ")
remember_text("บรรทัด1\nบรรทัด2")
remember_text("x" * 200)
assert text_history() == before, "ค่าว่าง/หลายบรรทัด/ยาวเกิน ไม่ควรเก็บ"
print("OK  ไม่เก็บข้อความว่าง/หลายบรรทัด/ยาวเกินไป")

# เก็บไม่เกินเพดาน และไม่ลบค่าตั้งอื่นในไฟล์
i18n.set_setting("language", "th")
for n in range(M.TEXT_HISTORY_MAX + 15):
    remember_text(f"ข้อความ {n}")
assert len(text_history()) <= M.TEXT_HISTORY_MAX, len(text_history())
assert i18n.get_setting("language") == "th", "ต้องไม่ลบค่าตั้งอื่น"
print(f"OK  เก็บไม่เกิน {M.TEXT_HISTORY_MAX} รายการ และไม่กระทบค่าตั้งอื่น")

# ---- วันที่วันนี้ต้องมีให้เลือกตั้งแต่ครั้งแรก ----
from datetime import date
today = date.today()
sugg = date_suggestions()
assert f"{today.day:02d}/{today.month:02d}/{today.year}" in sugg, sugg
assert any(str(today.year + 543) in s for s in sugg), "ต้องมีแบบ พ.ศ. ด้วย"
assert len(set(sugg)) == len(sugg), "ต้องไม่ซ้ำ"
print(f"OK  มีวันที่วันนี้ให้เลือกหลายรูปแบบ: {sugg[0]} / {sugg[1]}")

# ---- ตัวเดาคำ: พิมพ์ต้นๆ แล้วต้องเสนอข้อความเต็ม ----
editor = M.CompletingTextEdit("", ["03/08/2026", "บริษัท ออมใจ จำกัด", "04/08/2026"])
editor.setPlainText("03")
editor._update_popup()
comp = editor._completer
assert comp.completionCount() >= 1, "พิมพ์ 03 ต้องมีตัวเลือก"
assert comp.currentCompletion() == "03/08/2026", comp.currentCompletion()
print(f"OK  พิมพ์ '03' -> เสนอ '{comp.currentCompletion()}'")

# เลือกแล้วต้องแทนที่ทั้งบรรทัด (ไม่ใช่ต่อท้ายกลายเป็น 0303/08/2026)
editor._insert_completion("03/08/2026")
assert editor.toPlainText() == "03/08/2026", repr(editor.toPlainText())
print("OK  เลือกแล้วแทนที่ทั้งบรรทัด ไม่ซ้อนกัน")

# พิมพ์ครบพอดีแล้วไม่ต้องเสนอซ้ำ
editor.setPlainText("03/08/2026")
editor._update_popup()
assert not comp.popup().isVisible(), "ตรงกับที่พิมพ์แล้ว ไม่ควรเด้งตัวเลือก"
# คำที่ไม่มีในประวัติ ก็ไม่เด้ง
editor.setPlainText("zzzz")
editor._update_popup()
assert not comp.popup().isVisible()
print("OK  ไม่เด้งตัวเลือกเมื่อไม่จำเป็น")

# ---- กล่องเพิ่มข้อความใช้ตัวเดาคำจริง + จำสิ่งที่พิมพ์ ----
w = MainWindow()
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)

captured = {}
_real = M.CompletingTextEdit


class Spy(_real):
    def __init__(self, text="", history=None):
        captured["history"] = list(history or [])
        super().__init__(text, history)
        self.setPlainText("22/12/2026")


with patch.object(M, "CompletingTextEdit", Spy), \
     patch("app.main.QDialog.exec", return_value=M.QDialog.Accepted):
    text, font_key, bold, ok = w._ask_text_content("t", "")
assert ok and text == "22/12/2026"
assert any("/" in h for h in captured["history"]), "ต้องส่งประวัติ+วันที่เข้าไปให้เดาคำ"
assert text_history()[0] == "22/12/2026", "ต้องจำสิ่งที่พิมพ์ล่าสุด"
print("OK  กล่องเพิ่มข้อความ ใช้ตัวเดาคำ + จำสิ่งที่พิมพ์")

# ================= ใส่ข้อความตำแหน่งเดิมทุกหน้า =================

doc = PdfDocument(src)
box = doc.add_textbox(0, fitz.Rect(400, 700, 520, 730), "03/08/2026", font_size=14)
n = doc.add_textbox_all_pages(box)
assert n == 3, f"เอกสาร 4 หน้า มีอยู่แล้ว 1 -> ควรเพิ่ม 3 ได้ {n}"
for i in range(4):
    on = [b for b in doc.textboxes_on(i) if b.text == "03/08/2026"]
    assert len(on) == 1, f"หน้า {i+1} ควรมี 1 กล่อง ได้ {len(on)}"
    assert on[0].rect == box.rect, f"หน้า {i+1} ตำแหน่งต้องตรงกัน"
    assert on[0].font_size == box.font_size
print("OK  ใส่ข้อความทุกหน้า ตำแหน่ง/ขนาดตรงกันทุกหน้า")

# สั่งซ้ำต้องไม่วางทับซ้อน
assert doc.add_textbox_all_pages(box) == 0, "มีอยู่แล้วต้องไม่วางซ้ำ"
print("OK  สั่งซ้ำไม่วางทับซ้อน")

# เลือกเฉพาะบางหน้าได้
doc2 = PdfDocument(src)
b2 = doc2.add_textbox(0, fitz.Rect(10, 10, 80, 30), "X", font_size=12)
assert doc2.add_textbox_all_pages(b2, [1, 2]) == 2
assert doc2.textboxes_on(3) == [], "หน้าที่ไม่ได้เลือกต้องไม่มี"
print("OK  จำกัดเฉพาะหน้าที่เลือกได้")

# undo คืนสภาพ
doc3 = PdfDocument(src)
b3 = doc3.add_textbox(0, fitz.Rect(10, 10, 80, 30), "Y", font_size=12)
doc3.add_textbox_all_pages(b3)
doc3.undo()
assert len(doc3.textboxes) == 1, f"undo ต้องเหลือกล่องเดิม 1 ได้ {len(doc3.textboxes)}"
print("OK  undo คืนสภาพได้")

# ฝังลงไฟล์จริงครบทุกหน้า
doc4 = PdfDocument(src)
b4 = doc4.add_textbox(0, fitz.Rect(400, 700, 540, 730), "03/08/2026", font_size=14)
doc4.add_textbox_all_pages(b4)
out = tmp / "dated.pdf"
doc4.save(out)
with fitz.open(str(out)) as v:
    for i in range(v.page_count):
        assert "03/08/2026" in v.load_page(i).get_text(), f"หน้า {i+1} ไม่มีวันที่"
print("OK  บันทึกแล้วมีวันที่ครบทุกหน้าในไฟล์จริง")

# ---- ปุ่มบนแถบข้อความ ----
w2 = MainWindow()
w2.doc = PdfDocument(src)
w2.viewer.set_document(w2.doc)
w2._refresh_all(keep_row=0)
tb = w2.doc.add_textbox(0, fitz.Rect(400, 700, 520, 730), "03/08/2026", font_size=14)
w2.viewer.selected_textbox = tb
with patch.object(w2, "_ask_scope", return_value=[0, 1, 2, 3]):
    w2.textbox_selected_all_pages()
assert all(w2.doc.textboxes_on(i) for i in range(4)), "ปุ่มต้องใส่ครบทุกหน้า"
print("OK  ปุ่ม 'ใส่ทุกหน้า' บนแถบข้อความทำงาน")

# ไม่ได้เลือกข้อความ -> ไม่พัง
w2.viewer.selected_textbox = None
w2.textbox_selected_all_pages()
print("OK  ยังไม่เลือกข้อความ -> ไม่พัง")

# ================= สั่งด้วยคำพิมพ์ =================

for cmd, want_text in [("ใส่วันที่ทุกหน้า", None),
                       ("ใส่วันที่ 03/08/2026 ทุกหน้า", "03/08/2026"),
                       ('เพิ่ม "ต้นฉบับ" ทุกหน้า', "ต้นฉบับ")]:
    it = assistant.parse(cmd)
    assert it is not None and it.action == "text_all_pages", f"{cmd!r} -> {it}"
    assert it.params.get("text") == want_text, f"{cmd!r} -> {it.params}"
assert assistant.parse("ใส่วันที่") is None, "ไม่มีคำว่าทุกหน้า ไม่ควรจับ"
print("OK  ตีความคำสั่ง 'ใส่วันที่ทุกหน้า' ได้ (ระบุวันที่เองก็ได้)")

# สั่งแล้วต้องใช้ตำแหน่งของข้อความที่เลือกอยู่
w3 = MainWindow()
w3.doc = PdfDocument(src)
w3.viewer.set_document(w3.doc)
w3._refresh_all(keep_row=0)
anchor = w3.doc.add_textbox(0, fitz.Rect(300, 650, 460, 680), "ตรงนี้", font_size=13)
w3.viewer.selected_textbox = anchor
msg = w3._execute_intent(assistant.parse("ใส่วันที่ 09/09/2026 ทุกหน้า"))
placed = [b for b in w3.doc.textboxes if b.text == "09/09/2026"]
assert len(placed) == 4, f"ควรได้ 4 หน้า ได้ {len(placed)}"
assert all(b.rect == anchor.rect for b in placed), "ต้องใช้ตำแหน่งเดียวกับข้อความที่เลือก"
assert text_history()[0] == "09/09/2026", "สั่งด้วยคำพิมพ์ก็ต้องจำวันที่ไว้"
print(f"OK  สั่งคำสั่ง -> ใส่ 4 หน้าตำแหน่งเดียวกัน ({msg})")

# ยังไม่เลือกข้อความต้นแบบ -> บอกวิธีทำ ไม่ใช่เงียบหรือพัง
w3.viewer.selected_textbox = None
try:
    w3._execute_intent(assistant.parse("ใส่วันที่ทุกหน้า"))
    raise AssertionError("ควรแจ้งเตือนว่ายังไม่ได้เลือกข้อความ")
except RuntimeError as exc:
    assert "เพิ่มข้อความ" in str(exc), str(exc)
print("OK  ยังไม่เลือกต้นแบบ -> บอกวิธีทำให้ชัด")

# ไม่ระบุวันที่ -> ใช้วันที่วันนี้
w4 = MainWindow()
w4.doc = PdfDocument(src)
w4.viewer.set_document(w4.doc)
w4._refresh_all(keep_row=0)
a4 = w4.doc.add_textbox(0, fitz.Rect(300, 650, 460, 680), "-", font_size=13)
w4.viewer.selected_textbox = a4
w4._execute_intent(assistant.parse("ใส่วันที่ทุกหน้า"))
todays = date_suggestions()[0]
assert any(b.text == todays for b in w4.doc.textboxes), f"ควรใช้วันที่วันนี้ {todays}"
print(f"OK  ไม่ระบุวันที่ -> ใช้วันที่วันนี้ ({todays})")


# ================= ใส่ข้อความต่อท้าย "ป้าย" ในเอกสาร =================
# เช่น 'ใส่วันที่หลัง Date' — อ้างตำแหน่งจากป้ายในเอกสาร ไม่ต้องวางต้นแบบก่อน

lb = fitz.open()
for i in range(3):
    pg = lb.new_page(width=595, height=842)
    pg.insert_text((60, 60), f"Sheet {i+1}", fontsize=16)
    pg.insert_text((70, 750), "Name      :", fontsize=11)
    pg.insert_text((70, 775), "Date      :", fontsize=11)
lb.new_page(width=595, height=842).insert_text((60, 60), "no fields here", fontsize=14)
lbp = tmp / "labels.pdf"; lb.save(str(lbp)); lb.close()

doc = PdfDocument(lbp)
anchor = doc.label_anchor(0, "Date")
assert anchor is not None, "ต้องหาป้าย Date เจอ"
# ต้องรวมโคลอนไว้ในกรอบ (ไม่งั้นข้อความไปทับ :)
colons = [c for c in doc.doc.load_page(0).search_for(":")
          if abs((c.y0 + c.y1) / 2 - (anchor.y0 + anchor.y1) / 2) < 4]
assert colons and anchor.x1 >= max(c.x1 for c in colons) - 1, \
    "กรอบป้ายต้องครอบโคลอนด้วย"
assert doc.label_anchor(0, "ไม่มีคำนี้") is None
print("OK  หาป้ายในเอกสารได้ และรวมโคลอนไว้ในกรอบ")

n, missing = doc.add_textbox_after_label("Date", "03/08/2026")
assert n == 3, f"3 หน้าแรกมีคำว่า Date -> ควรได้ 3 ได้ {n}"
assert missing == [3], f"หน้า 4 ไม่มีคำนี้ ต้องรายงานไว้ ได้ {missing}"
for i in range(3):
    placed = doc.textboxes_on(i)
    assert len(placed) == 1, f"หน้า {i+1} ควรมี 1 กล่อง"
    a = doc.label_anchor(i, "Date")
    assert placed[0].rect.x0 >= a.x1, "ต้องวางถัดจากป้ายไปทางขวา"
    assert abs(placed[0].rect.y0 - a.y0) < 6, "ต้องอยู่บรรทัดเดียวกับป้าย"
assert doc.textboxes_on(3) == []
print("OK  วางข้อความต่อท้ายป้าย ตรงบรรทัด ทุกหน้าที่พบ (ข้ามหน้าที่ไม่มี)")

# ขนาดตัวอักษรควรใกล้เคียงกับป้าย (กลืนกับเอกสาร)
size = doc.textboxes_on(0)[0].font_size
assert 6 <= size <= 20, size
print(f"OK  ขนาดตัวอักษรอิงความสูงของป้าย ({size:.1f})")

# ไม่พบป้ายเลย -> ไม่แก้เอกสาร ไม่ push undo
doc2 = PdfDocument(lbp)
n2, miss2 = doc2.add_textbox_after_label("ไม่มีคำนี้เลย", "x")
assert n2 == 0 and len(miss2) == 4
assert doc2.textboxes == [] and not doc2.can_undo, "ไม่พบป้าย ต้องไม่แตะเอกสาร"
print("OK  ไม่พบป้าย -> ไม่แก้เอกสาร")

# บันทึกแล้วมีข้อความจริงในไฟล์
doc3 = PdfDocument(lbp)
doc3.add_textbox_after_label("Date", "03/08/2026")
out3 = tmp / "labeled.pdf"
doc3.save(out3)
with fitz.open(str(out3)) as v:
    for i in range(3):
        assert "03/08/2026" in v.load_page(i).get_text(), f"หน้า {i+1} ไม่มีวันที่ในไฟล์"
print("OK  บันทึกแล้วมีข้อความครบในไฟล์จริง")

# หน้าที่ถูกหมุนไว้ (เอกสารจริงจะเห็นป้ายหงายปกติ) ต้องวางต่อท้ายป้ายได้ถูกที่
rt = fitz.open()
pg = rt.new_page(width=595, height=842)
pg.set_rotation(90)
# เขียนป้ายให้ "อ่านหงาย" ในมุมมองจริง เหมือนเอกสารที่สแกนมาแล้วหมุนให้ตั้งตรง
pg.insert_text((70, 700), "Date      :", fontsize=12, rotate=90)
rtp = tmp / "rot.pdf"; rt.save(str(rtp)); rt.close()
doc4 = PdfDocument(rtp)
n4, _ = doc4.add_textbox_after_label("Date", "01/01/2027")
assert n4 == 1
out4 = tmp / "rotlabel.pdf"; doc4.save(out4)
with fitz.open(str(out4)) as v:
    page = v.load_page(0)
    assert "01/01/2027" in page.get_text(), "หน้าที่หมุนก็ต้องใส่ได้"
    m = page.rotation_matrix
    got = [r * m for r in page.search_for("01/01/2027")]
    lab = [r * m for r in page.search_for("Date")]
    assert got and lab, "ต้องหาเจอทั้งคู่หลังบันทึก"
    # เทียบในพิกัดที่แสดงจริง: ต้องอยู่บรรทัดเดียวกับป้าย และอยู่ทางขวาของป้าย
    mid_got = (got[0].y0 + got[0].y1) / 2
    mid_lab = (lab[0].y0 + lab[0].y1) / 2
    assert abs(mid_got - mid_lab) < 10, f"ไม่อยู่บรรทัดเดียวกับป้าย {got[0]} vs {lab[0]}"
    assert got[0].x0 >= lab[0].x0, "ต้องอยู่ทางขวาของป้าย (ในมุมมองจริง)"
print("OK  หน้าที่ถูกหมุน — วางต่อท้ายป้ายถูกที่ (เทียบในมุมมองจริง)")

# ---- คำสั่งพิมพ์แบบที่ผู้ใช้พิมพ์จริง ----
cases = {
    "ใส่วันที่หลัง Date  03/08/2026": ("Date", "03/08/2026"),
    "ใส่วันที่หลัง Date": ("Date", None),
    "ใส่ 03/08/2026 หลัง Date": ("Date", "03/08/2026"),
    "ใส่วันที่หลังคำว่า วันที่ ทุกหน้า": ("วันที่", None),
    "add date after Date": ("Date", None),
    'ใส่ "ต้นฉบับ" หลัง Name': ("Name", "ต้นฉบับ"),
    "ใส่วันที่หลัง Date ให้หน่อยครับ": ("Date", None),
}
for cmd, (want_label, want_text) in cases.items():
    it = assistant.parse(cmd)
    assert it is not None and it.action == "text_after_label", f"{cmd!r} -> {it}"
    assert it.params["label"] == want_label, f"{cmd!r} -> label {it.params['label']!r}"
    assert it.params.get("text") == want_text, f"{cmd!r} -> text {it.params.get('text')!r}"
print("OK  ตีความคำสั่งแบบ 'ใส่วันที่หลัง Date' ได้ทุกรูปแบบที่ลอง")

# ทำงานจริงผ่านคำสั่ง
w5 = MainWindow()
w5.doc = PdfDocument(lbp)
w5.viewer.set_document(w5.doc)
w5._refresh_all(keep_row=0)
msg = w5._execute_intent(assistant.parse("ใส่วันที่หลัง Date  03/08/2026"))
assert len([b for b in w5.doc.textboxes if b.text == "03/08/2026"]) == 3, w5.doc.textboxes
assert "Date" in msg
assert text_history()[0] == "03/08/2026", "ต้องจำวันที่ที่สั่งไว้ด้วย"
print(f"OK  สั่งคำสั่งแล้วใส่ได้จริง ({msg.split('—')[0].strip()})")

# ป้ายที่ไม่มีในเอกสาร -> บอกให้ชัด ไม่เงียบ
try:
    w5._execute_intent(assistant.parse("ใส่วันที่หลัง Datee"))
    raise AssertionError("ควรแจ้งว่าไม่พบคำนี้")
except RuntimeError as exc:
    assert "Datee" in str(exc), str(exc)
print("OK  ไม่พบป้าย -> แจ้งเตือนพร้อมบอกทางเลือก")

print("\nผ่านทั้งหมด")
