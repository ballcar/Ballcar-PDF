"""ทดสอบ 2.3.1: ไฟล์แบบฟอร์ม (กรอกได้) — คลิกช่องบนหน้าแล้วพิมพ์ได้เลยแบบ Chrome, ภาษาไทยแสดงถูก

เคยมีปัญหา: กรอกได้แค่ผ่านหน้าต่าง ซึ่งโชว์ชื่อช่องเป็น Text1, Text2… (ไม่รู้ว่าช่องไหน)
และค่าภาษาไทยในช่องแสดงเพี้ยน (สระ/วรรณยุกต์หลุด ตัวหนังสือเลื่อน)
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app import i18n
from app.main import MainWindow
from app.pdfops import PdfDocument

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())

# ฟอร์มจำลองแบบไฟล์จริง: ช่องชื่อ Text1.. , ช่องหลายบรรทัด, ช่องติ๊ก, ช่องเลือก
src = tmp / "form.pdf"
d = fitz.open()
page = d.new_page()
page.insert_text((72, 90), "ใบส่งงวดงาน", fontsize=16, fontname="thai",
                 fontfile=r"C:\Windows\Fonts\tahoma.ttf")


def add(kind, name, rect, **kw):
    w = fitz.Widget()
    w.field_type = kind
    w.field_name = name
    w.rect = fitz.Rect(rect)
    w.text_fontsize = kw.pop("size", 12)
    for k, v in kw.items():
        setattr(w, k, v)
    page.add_widget(w)


add(fitz.PDF_WIDGET_TYPE_TEXT, "Text1", (150, 120, 400, 140))
add(fitz.PDF_WIDGET_TYPE_TEXT, "Text2", (150, 150, 400, 170))
add(fitz.PDF_WIDGET_TYPE_CHECKBOX, "Check1", (150, 180, 162, 192))
add(fitz.PDF_WIDGET_TYPE_TEXT, "Text3", (150, 200, 400, 260), field_flags=4096)
add(fitz.PDF_WIDGET_TYPE_COMBOBOX, "Combo1", (150, 270, 300, 290),
    choice_values=["งวดที่ 1", "งวดที่ 2"], field_value="งวดที่ 1")
d.save(str(src)); d.close()

# ---- ระดับเอกสาร: ภาษาไทยเก็บค่าถูก + หน้าตาช่องวาดด้วยฟอนต์ไทย ----
doc = PdfDocument(src)
fields = {f["name"]: f for f in doc.form_widgets_on(0)}
assert set(fields) == {"Text1", "Text2", "Check1", "Text3", "Combo1"}
assert fields["Text3"]["multiline"] and not fields["Text1"]["multiline"]
doc.set_form_field(0, fields["Text1"]["xref"], "บริษัท ซีเอสเอส จำกัด")
doc.set_form_field(0, fields["Text3"]["xref"], "ก่อสร้างฐานราก\nเทพื้นชั้นที่ 1 เรียบร้อยแล้ว")
out = tmp / "filled.pdf"
doc.save(out)
with fitz.open(str(out)) as saved:
    ws = {w.field_name: w for w in saved[0].widgets()}
    assert ws["Text1"].field_value == "บริษัท ซีเอสเอส จำกัด"
    assert ws["Text3"].field_value.startswith("ก่อสร้างฐานราก\n")
    for name in ("Text1", "Text3"):
        ap = saved.xref_get_key(ws[name].xref, "AP/N")[1]
        xobj = int(ap.split()[0])
        fonts = str(saved.xref_object(xobj)) + "".join(
            saved.xref_object(int(x)) for x in
            __import__("re").findall(r"(\d+) 0 R", saved.xref_object(xobj)))
        assert "Helv" not in fonts, f"{name}: ช่องไทยต้องไม่ใช้ Helvetica (ไม่มีสระไทย)"
    # ภาพช่องต้องมีหมึก (ตัวหนังสือออกมาจริง) และไม่เลยขอบขวาของช่อง
    pix = saved[0].get_pixmap(clip=ws["Text1"].rect, dpi=144)
    dark = [x for y in range(pix.height) for x in range(pix.width) if pix.pixel(x, y)[0] < 120]
    assert dark and max(dark) < pix.width - 2
print("OK  กรอกไทยในช่องฟอร์ม: ค่าถูก หน้าตาช่องใช้ฟอนต์ไทย ตัวหนังสือไม่ล้นช่อง")

check = doc.form_widget_at(0, fitz.Point(156, 186))   # บันทึกแล้วเลข xref เปลี่ยน ต้องถามใหม่
assert check["name"] == "Check1"
doc.toggle_form_field(0, check["xref"])
assert [f["value"] for f in doc.form_widgets_on(0) if f["name"] == "Check1"][0] not in ("Off", False)
doc.undo()
assert [f["value"] for f in doc.form_widgets_on(0) if f["name"] == "Check1"][0] in ("Off", False, "")
print("OK  ช่องติ๊ก: คลิกสลับได้ ย้อนกลับได้")

# ---- บนหน้าจอ: คลิกช่องแล้วพิมพ์ ----
w = MainWindow(); w.resize(1200, 900); w.show(); app.processEvents()
w._open_path(str(src)); app.processEvents(); app.processEvents()
v = w.viewer
assert w.statusBar().currentMessage() == i18n.t("form.hint"), "เปิดไฟล์ฟอร์ม = บอกว่าคลิกกรอกได้"


def click_field(name):
    info = [f for f in w.doc.form_widgets_on(0) if f["name"] == name][0]
    g = v._geoms[0]
    c = info["rect"]
    pt = QPoint(int(g.x() + (c.x0 + c.x1) / 2 * v.zoom), int(g.y() + (c.y0 + c.y1) / 2 * v.zoom))
    v._dispatch_press(pt, Qt.LeftButton)
    v._dispatch_release(pt, Qt.LeftButton)
    app.processEvents()
    return info


click_field("Text1")
ed = v._field_editor
assert ed is not None and ed["info"]["name"] == "Text1", "คลิกช่องข้อความ = มีช่องพิมพ์ทับตรงนั้น"
editor = ed["widget"]
assert editor.isVisible() and editor.hasFocus()
editor.setText("นายสมชาย ใจดี")
QTest.keyClick(editor, Qt.Key_Tab)          # Tab = เก็บ + ไปช่องถัดไป
app.processEvents()
assert v._field_editor and v._field_editor["info"]["name"] == "Text2", "Tab ไปช่องถัดไป"
values = {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}
assert values["Text1"] == "นายสมชาย ใจดี" and w.doc.dirty
assert w.tab_bar.tabText(0).endswith("*")
v._field_editor["widget"].setText("ทิ้ง")
QTest.keyClick(v._field_editor["widget"], Qt.Key_Escape)
app.processEvents()
assert v._field_editor is None
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Text2"] in ("", None), "Esc = ไม่เก็บ"
print("OK  คลิกช่อง → พิมพ์ → Tab ไปช่องถัดไป (เก็บค่า) · Esc = ยกเลิก")

click_field("Text2")
v._field_editor["widget"].setText("1,250,000 บาท")
QTest.keyClick(v._field_editor["widget"], Qt.Key_Return)
app.processEvents()
assert v._field_editor is None
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Text2"] == "1,250,000 บาท"
print("OK  Enter = เสร็จ เก็บค่า")

click_field("Check1")
assert v._field_editor is None
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Check1"] not in ("Off", False)
click_field("Check1")
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Check1"] in ("Off", False)
print("OK  คลิกช่องติ๊ก = ติ๊ก/เอาออก")

click_field("Text3")
multi = v._field_editor["widget"]
assert multi.__class__.__name__ == "_FieldText", "ช่องหลายบรรทัด = พิมพ์ขึ้นบรรทัดใหม่ได้"
multi.setPlainText("บรรทัด 1\nบรรทัด 2")
QTest.keyClick(multi, Qt.Key_Return, Qt.ControlModifier)
app.processEvents()
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Text3"] == "บรรทัด 1\nบรรทัด 2"

click_field("Combo1")
combo = v._field_editor["widget"]
assert combo.count() == 2
combo.setCurrentIndex(1)
combo.activated.emit(1)
app.processEvents()
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Combo1"] == "งวดที่ 2"
print("OK  ช่องหลายบรรทัด (Ctrl+Enter) · ช่องเลือกรายการ")

# คลิกที่อื่นบนหน้า = เก็บค่าที่พิมพ์ค้างไว้
click_field("Text1")
v._field_editor["widget"].setText("แก้ชื่อใหม่")
g = v._geoms[0]
v._dispatch_press(QPoint(g.x() + 20, g.y() + 600), Qt.LeftButton)
v._dispatch_release(QPoint(g.x() + 20, g.y() + 600), Qt.LeftButton)
app.processEvents()
assert v._field_editor is None
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Text1"] == "แก้ชื่อใหม่"
assert w.doc.undo()
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Text1"] == "นายสมชาย ใจดี"
print("OK  คลิกที่อื่น = เก็บค่า · ย้อนกลับ (Ctrl+Z) ได้ทีละช่อง")

click_field("Text2")
v._field_editor["widget"].setText("2,000,000 บาท")
w.doc.save(tmp / "mid.pdf")                 # กด Ctrl+S ทั้งที่ช่องพิมพ์ยังเปิดอยู่
QTest.keyClick(v._field_editor["widget"], Qt.Key_Return)
app.processEvents()
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Text2"] == "2,000,000 บาท"
click_field("Check1")
assert {f["name"]: f["value"] for f in w.doc.form_widgets_on(0)}["Check1"] not in ("Off", False),     "บันทึกแล้วคลิกช่องติ๊กต่อได้"
print("OK  บันทึกระหว่างกรอก แล้วกรอก/ติ๊กต่อได้ ค่าไม่หาย")

out2 = tmp / "ui.pdf"
w.doc.save(out2)
with fitz.open(str(out2)) as saved:
    vals = {x.field_name: x.field_value for x in saved[0].widgets()}
assert vals["Text2"] == "2,000,000 บาท" and vals["Combo1"] == "งวดที่ 2"
print("OK  บันทึกแล้วเปิดใน Chrome/Acrobat ได้ค่าที่กรอก (ฟอร์มยังแก้ต่อได้)")

# ไฟล์ฟอร์มจริงที่น้องส่งมา (ถ้ามีในเครื่อง)
real = Path(r"C:\Users\chayakul_b\Downloads\FM-CM-04_Rev.1_ใบส่งงวดงาน RSS.pdf")
if real.exists():
    import shutil
    copy = tmp / "real.pdf"
    shutil.copy(real, copy)
    rd = PdfDocument(copy)
    info = rd.form_widgets_on(0)
    texts = [f for f in info if f["type"] == fitz.PDF_WIDGET_TYPE_TEXT]
    assert len(info) >= 30
    rd.set_form_field(0, texts[1]["xref"], "ทดสอบภาษาไทย")
    rd.save(tmp / "real_out.pdf")
    with fitz.open(str(tmp / "real_out.pdf")) as saved:
        assert saved.page_count == 2, "ห้ามมีหน้าเกินมา (หน้าชั่วคราวตอนวาดช่อง)"
        assert [x.field_value for x in saved[0].widgets() if x.xref == texts[1]["xref"]] == ["ทดสอบภาษาไทย"]
    print("OK  ไฟล์จริง FM-CM-04 กรอกไทยได้ จำนวนหน้าเท่าเดิม")

for tab in w._tabs:
    tab["doc"].dirty = False
print("\nผ่านทั้งหมด")
