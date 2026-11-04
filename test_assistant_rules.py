"""ทดสอบผู้ช่วย 2.0: กฎที่เก่งขึ้น (ระบุหน้า คำพ้อง สั่งต่อกัน เรียกเครื่องมือ) + ทำงานจริงกับเอกสาร"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app import assistant as A


def act(cmd):
    it = A.parse(cmd)
    return (it.action, it.params) if it else None


# ---- ระบุหน้า ----
assert act("ลบหน้า 3-5") == ("delete_pages", {"pages": "3-5"})
assert act("ลบหน้า 2 และ 4") == ("delete_pages", {"pages": "2,4"})
assert act("ลบหน้า 1, 3, 5") == ("delete_pages", {"pages": "1,3,5"})
assert act("ลบหน้า 2 ถึง 6") == ("delete_pages", {"pages": "2-6"})
assert act("ลบหน้าสุดท้าย") == ("delete_pages", {"pages": "last"})
assert act("ลบหน้า ๓") == ("delete_pages", {"pages": "3"}), "เลขไทยต้องอ่านได้"
assert act("delete page 4") == ("delete_pages", {"pages": "4"})
assert A.resolve_pages("3-5", 10) == [2, 3, 4]
assert A.resolve_pages("even", 5) == [1, 3] and A.resolve_pages("odd", 5) == [0, 2, 4]
assert A.resolve_pages("last", 4) == [3] and A.resolve_pages(None, 3) == [0, 1, 2]
try:
    A.resolve_pages("9", 3)
except ValueError as e:
    assert "3 หน้า" in str(e)
else:
    raise AssertionError("หน้าเกินต้องแจ้ง")
print("OK  ระบุหน้า: ช่วง/หลายหน้า/แรก/สุดท้าย/คู่/คี่/เลขไทย และเกินจำนวนหน้าแจ้งเตือน")

# ---- หมุน ย้าย แทรก แยก ----
assert act("หมุนหน้า 2 ไปทางขวา") == ("rotate", {"degrees": 90, "pages": "2"})
assert act("หมุนหน้าคู่ทวนเข็ม") == ("rotate", {"degrees": -90, "pages": "even"})
assert act("หมุนกลับหัว") == ("rotate", {"degrees": 180, "pages": None})
assert act("หมุนหน้า 3 ตะแคง") == ("orientation", {"orientation": "landscape", "pages": "3"})
assert act("ย้ายหน้า 5 ไปหน้าแรก") == ("move_page", {"source": 5, "dest": 1})
assert act("ย้ายหน้า 1 ไปท้ายสุด") == ("move_page", {"source": 1, "dest": -1})
assert act("ย้ายหน้า 2 ไปหน้า 4") == ("move_page", {"source": 2, "dest": 4})
assert act("แทรกหน้าว่างหลังหน้า 3") == ("insert_blank", {"at": 3})
assert act("แทรกหน้าว่างก่อนหน้า 1") == ("insert_blank", {"at": 0})
assert act("เพิ่มหน้าเปล่า") == ("insert_blank", {"at": None})
assert act("แยกหน้า 1-3 เป็นไฟล์ใหม่") == ("extract_pages", {"pages": "1-3"})
assert act("ดึงหน้า 2-4 ออกมา") == ("extract_pages", {"pages": "2-4"})
assert act("แยกไฟล์ทีละหน้า")[0] == "split_each"
print("OK  หมุน/ย้าย/แทรก/แยกหน้า ระบุหน้าได้")

# ---- คำพ้อง ----
assert act("หน้าเปล่าไม่ต้องเอา")[0] == "delete_blank"
assert act("เอาหน้าว่างออก")[0] == "delete_blank"
assert act("ลดขนาดไฟล์หน่อย") == ("open_tool", {"method": "compress_dialog"})
assert act("แปลงเป็นเวิร์ด") == ("open_tool", {"method": "export_word"})
assert act("ดึงตารางเป็นเอ็กเซล") == ("open_tool", {"method": "export_excel"}), \
    "ต้องไม่กลายเป็น 'เก็บหน้าที่มีคำว่า ตารางเป็นเอ็กเซล'"
assert act("ล็อกไฟล์") == ("open_tool", {"method": "password_dialog"})
assert act("พิมพ์") == ("open_tool", {"method": "print_document"})
assert act("รวมไฟล์") == ("open_tool", {"method": "merge_dialog"})
print("OK  คำพ้อง (หน้าเปล่า, ลดขนาดไฟล์, เวิร์ด, เอ็กเซล, ล็อกไฟล์) และเรียกเครื่องมือในเมนู")

# ---- เลขหน้าเริ่มหน้าไหนก็ได้ / ดึงหน้าที่มีคำว่า ----
assert act("ใส่เลขหน้าเริ่มที่หน้า 3") == ("page_numbers", {"numeral": "arabic", "first_page": 3})
assert act("ใส่เลขหน้าเริ่มหน้า 2 เริ่มเลข 5")[1] == \
    {"numeral": "arabic", "first_page": 2, "start_at": 5}
assert act("เก็บเฉพาะหน้าที่มีคำว่า invoice") == ("keep_matching", {"keyword": "invoice"})
assert act('ดึงเฉพาะหน้าที่มีคำว่า "ใบเสนอราคา"') == ("keep_matching", {"keyword": "ใบเสนอราคา"})
print("OK  เลขหน้าเริ่มหน้าที่ระบุ / ดึงเฉพาะหน้าที่มีคำ (มีหรือไม่มีเครื่องหมายคำพูด)")

# ---- สั่งต่อกัน ----
steps = A.parse_all("ลบหน้าว่าง แล้วใส่เลขหน้า")
assert [s.action for s in steps] == ["delete_blank", "page_numbers"]
steps = A.parse_all("หมุนหน้า 1 ขวา จากนั้นบีบอัดไฟล์")
assert [s.action for s in steps] == ["rotate", "open_tool"]
assert A.parse_all('ใส่ลายน้ำ "ตรวจแล้วจากนั้นส่ง"')[0].params["text"] == "ตรวจแล้วจากนั้นส่ง", \
    "คำในเครื่องหมายคำพูดห้ามถูกแยกเป็นคำสั่ง"
assert A.parse_all("ลบหน้าว่าง แล้วกินข้าว") is None, "มีส่วนที่ไม่เข้าใจ -> ไม่ทำครึ่งๆ กลางๆ"
print("OK  สั่งต่อกันหลายอย่าง (แล้ว/จากนั้น) และไม่ทำครึ่งๆ กลางๆ")

# ---- ไม่เข้าใจ -> เดาคำสั่งใกล้เคียง ----
assert A.parse("หมุนหน้าเอกสารหน่อย") is None
near = A.suggest("หมุนหน้าเอกสารหน่อย")
assert near and all("หมุน" in s for s in near), near
assert A.suggest("") == []
print(f"OK  ไม่เข้าใจแล้วเสนอคำสั่งใกล้เคียง: {near}")

# ---- ทำงานจริงกับเอกสาร ----
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from app import i18n
from app.main import MainWindow, assistant_history
from app.pdfops import PdfDocument

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())


def doc_with(n):
    d = fitz.open()
    for i in range(n):
        d.new_page(width=595, height=842).insert_text((72, 72), f"PAGE-{i + 1}", fontsize=20)
    p = tmp / f"d{len(list(tmp.glob('*.pdf')))}.pdf"
    d.save(str(p)); d.close()
    w = MainWindow()
    w._open_path(str(p))
    return w


def labels(w):
    return [w.doc.page_text(i).strip() for i in range(w.doc.page_count)]


w = doc_with(6)
w.run_assistant_command("ลบหน้า 2-3", confirmed=True)
assert labels(w) == ["PAGE-1", "PAGE-4", "PAGE-5", "PAGE-6"], labels(w)
w.run_assistant_command("ย้ายหน้า 4 ไปหน้าแรก", confirmed=True)
assert labels(w) == ["PAGE-6", "PAGE-1", "PAGE-4", "PAGE-5"], labels(w)
w.run_assistant_command("ย้ายหน้า 1 ไปท้ายสุด", confirmed=True)
assert labels(w) == ["PAGE-1", "PAGE-4", "PAGE-5", "PAGE-6"], labels(w)
w.run_assistant_command("หมุนหน้า 2 ไปทางขวา", confirmed=True)
assert w.doc.doc.load_page(1).rotation == 90 and w.doc.doc.load_page(0).rotation == 0
w.run_assistant_command("แทรกหน้าว่างหลังหน้า 1", confirmed=True)
assert labels(w)[1] == "" and w.doc.page_count == 5
w.run_assistant_command("ลบหน้าว่าง แล้วใส่เลขหน้าเริ่มที่หน้า 2", confirmed=True)
assert w.doc.page_count == 4
assert "1" not in w.doc.page_text(0).replace("PAGE-1", ""), "หน้า 1 ต้องไม่มีเลขหน้า"
assert w.doc.page_text(1).strip().endswith("1"), w.doc.page_text(1)
print("OK  ทำงานจริง: ลบช่วงหน้า ย้ายหน้า หมุนหน้าเดียว แทรกหน้าว่าง และสั่งต่อกัน")

target = tmp / "out.pdf"
with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "")):
    w.run_assistant_command("แยกหน้า 2-3 เป็นไฟล์ใหม่", confirmed=True)
with fitz.open(str(target)) as out:
    assert out.page_count == 2 and "PAGE-4" in out[0].get_text()
assert w.doc.page_count == 4, "ไฟล์ที่เปิดอยู่ต้องไม่เปลี่ยน"
print("OK  แยกหน้าเป็นไฟล์ใหม่ ไฟล์เดิมไม่เปลี่ยน")

with patch.object(QMessageBox, "critical") as err:
    w.run_assistant_command("ลบหน้า 9", confirmed=True)
    assert err.called and "4 หน้า" in err.call_args[0][2]
assert w.doc.page_count == 4
print("OK  สั่งหน้าที่ไม่มี -> แจ้งชัดเจน ไม่ลบอะไร")

with patch.object(MainWindow, "compress_dialog") as tool:
    w.run_assistant_command("ลดขนาดไฟล์", confirmed=True)
    assert tool.called, "ต้องเปิดหน้าต่างบีบอัดตัวเดิม"
print("OK  เรียกเครื่องมือในเมนูผ่านผู้ช่วยได้")

history = assistant_history()
assert history[0] == "ลดขนาดไฟล์" and "แยกหน้า 2-3 เป็นไฟล์ใหม่" in history
assert "ลบหน้า 9" not in history, "คำสั่งที่ทำไม่สำเร็จไม่ต้องจำ"
assert len(history) <= 8
print("OK  จำเฉพาะคำสั่งที่ทำสำเร็จ ล่าสุด 8 คำสั่ง")

# ---- ย้ายหน้าไปท้ายสุด: ลายเซ็น/ข้อความที่เพิ่มไว้ต้องย้ายตามหน้า ----
from app.pdfops import TextBox
w2 = doc_with(3)
box = TextBox(page=0, rect=fitz.Rect(100, 100, 300, 140), text="ติดหน้าแรก")
w2.doc.textboxes.append(box)
w2.run_assistant_command("ย้ายหน้า 1 ไปท้ายสุด", confirmed=True)
assert labels(w2)[-1].startswith("PAGE-1") and box.page == 2, f"ข้อความต้องตามไปหน้าสุดท้าย ({box.page})"
print("OK  ย้ายหน้าไปท้ายสุด ของที่เพิ่มไว้บนหน้านั้นย้ายตาม")

# ---- หน้าต่างผู้ช่วย: ตัวอย่างสด / ปุ่มทำเลย / คำแนะนำ ----
from app.assistant_ui import AssistantDialog
d = AssistantDialog(None, assistant_history())
d.input.setText("ลบหน้า 3-5 แล้วใส่เลขหน้า"); d._update_preview()
assert d.run_button.isEnabled() and "1." in d.preview.text() and "2." in d.preview.text()
d.input.setText("หมุนหน้าเอกสารหน่อย"); d._update_preview()
assert not d.run_button.isEnabled() and not d.suggest_title.isHidden()
d.input.setText("แปลเป็นอังกฤษ"); d._update_preview()
assert not d.run_button.isEnabled() and i18n.t("ai.no_ai") in d.preview.text()
d._use("ลบหน้าสุดท้าย")
assert d.input.text() == "ลบหน้าสุดท้าย" and d.run_button.isEnabled()
d._run()
assert d.command == "ลบหน้าสุดท้าย"
print("OK  หน้าต่างผู้ช่วย: เห็นสิ่งที่จะทำทันที, ไม่เข้าใจเสนอคำสั่ง, กดตัวอย่างเติมให้")

# ---- 2.2-2.3: ผู้ช่วยเปิดเครื่องมือใหม่ได้ (คำเฉพาะมาก่อนคำกว้างอย่าง "ลายเซ็น") ----
import app.main as _main
for text, method in [("ตรายางอนุมัติ", "stamp_dialog"), ("เปรียบเทียบเอกสาร", "compare_dialog"),
                     ("วาดลายเซ็น", "draw_signature"), ("ครอปลายเซ็นจากหน้านี้", "capture_signature_mode"),
                     ("ปิดทับคำว่า 1234", "cover_text_dialog"), ("เพิ่มโน้ต", "add_note_mode"),
                     ("เปิดตั้งค่า", "settings_dialog"), ("ใส่ลายเซ็น", "signature_dialog"),
                     ("ตั้งรหัสผ่าน", "password_dialog"), ("ล้างสคริปต์ในไฟล์", "remove_risks")]:
    it = A.parse(text)
    assert it and it.action == "open_tool" and it.params["method"] == method, (text, it)
    assert hasattr(_main.MainWindow, method), f"MainWindow ต้องมี {method}"
print("OK  ผู้ช่วยเปิดเครื่องมือใหม่ได้: ตรายาง เปรียบเทียบ วาด/ครอปลายเซ็น ปิดทับคำ โน้ต ตั้งค่า")

print("")
print("ผ่านทั้งหมด")
