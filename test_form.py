"""ทดสอบเติมข้อมูลในแบบฟอร์ม PDF"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())


def make_form() -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    specs = [
        ("customer_name", fitz.PDF_WIDGET_TYPE_TEXT, (100, 100, 300, 120), None),
        ("agree", fitz.PDF_WIDGET_TYPE_CHECKBOX, (100, 150, 115, 165), None),
        ("payment", fitz.PDF_WIDGET_TYPE_COMBOBOX, (100, 200, 250, 220),
         ["Cash", "Credit", "Transfer"]),
    ]
    for name, ftype, rect, choices in specs:
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

# ---- ตรวจว่าเป็นฟอร์ม ----
d = PdfDocument(src)
assert d.is_form(), "ต้องรู้ว่าเป็นไฟล์ฟอร์ม"
plain = fitz.open(); plain.new_page(); pp = tmp / "plain.pdf"; plain.save(str(pp)); plain.close()
assert not PdfDocument(pp).is_form()
print("OK  ตรวจว่าเป็นไฟล์ฟอร์ม")

# ---- อ่านรายการช่อง ----
fields = d.form_fields()
assert len(fields) == 3, fields
names = {f["name"]: f for f in fields}
assert names["customer_name"]["type_str"] == "Text"
assert names["agree"]["type_str"] == "CheckBox"
assert names["payment"]["choices"] == ["Cash", "Credit", "Transfer"]
print("OK  อ่านรายการช่องกรอกได้:", [f["name"] for f in fields])

# ---- เติมทีละช่อง ----
name_f = names["customer_name"]
assert d.set_form_field(name_f["page"], name_f["xref"], "สมชาย ใจดี")
after = {f["name"]: f for f in d.form_fields()}
assert after["customer_name"]["value"] == "สมชาย ใจดี", after["customer_name"]["value"]
print("OK  เติมช่องข้อความ (ไทย) ได้")

# ---- เติมหลายช่องพร้อมกัน ----
d = PdfDocument(src)
fmap = {f["name"]: f for f in d.form_fields()}
n = d.set_form_fields([
    (fmap["customer_name"]["page"], fmap["customer_name"]["xref"], "บริษัท ทดสอบ จำกัด"),
    (fmap["agree"]["page"], fmap["agree"]["xref"], True),
    (fmap["payment"]["page"], fmap["payment"]["xref"], "Credit"),
])
assert n == 3, n
after = {f["name"]: f for f in d.form_fields()}
assert after["customer_name"]["value"] == "บริษัท ทดสอบ จำกัด"
assert after["agree"]["value"] in ("Yes", "On", True), after["agree"]["value"]
assert after["payment"]["value"] == "Credit"
print("OK  เติมหลายช่องพร้อมกันได้ (ข้อความ/เช็คบ็อกซ์/dropdown)")

# ---- บันทึกแล้วค่ายังอยู่ ----
out = tmp / "filled.pdf"
d.save(out)
with fitz.open(out) as v:
    vals = {w.field_name: w.field_value for w in v[0].widgets()}
    assert vals["customer_name"] == "บริษัท ทดสอบ จำกัด", vals
    assert vals["payment"] == "Credit"
    assert v.is_form_pdf, "บันทึกแล้วยังเป็นฟอร์มแก้ต่อได้"
print("OK  บันทึกแล้วค่าฟอร์มยังอยู่ + ยังแก้ต่อได้")

# ---- undo ----
d.undo()
after = {f["name"]: f for f in d.form_fields()}
assert after["customer_name"]["value"] in ("", None), after["customer_name"]["value"]
print("OK  undo ล้างค่าที่กรอกได้")

# ---- กรอกแบบตรึง (รองรับไทย) ----
d = PdfDocument(src)
fmap = {f["name"]: f for f in d.form_fields()}
n = d.fill_form_flatten([
    (fmap["customer_name"]["page"], fmap["customer_name"]["xref"], "สมชาย ใจดี"),
    (fmap["agree"]["page"], fmap["agree"]["xref"], True),
    (fmap["payment"]["page"], fmap["payment"]["xref"], "Credit"),
])
assert n == 3, n
assert not d.is_form(), "ตรึงแล้วต้องไม่เหลือ field"
flat = tmp / "flat.pdf"
d.save(flat)
with fitz.open(flat) as v:
    assert not v.is_form_pdf
    text = v.load_page(0).get_text()
    assert "สมชาย" in text, f"ค่าภาษาไทยต้องกลายเป็นเนื้อหาถาวร: {text!r}"
    assert "Credit" in text
    assert "X" in text, "เช็คบ็อกซ์ที่ติ๊กต้องมีเครื่องหมาย"
print("OK  กรอกแบบตรึง รองรับไทย (วาดเป็นเนื้อหาถาวร)")

# flatten_form เปล่าๆ ก็ยังใช้ได้ (ตรึงค่าที่กรอกแบบ native)
d = PdfDocument(src)
fmap = {f["name"]: f for f in d.form_fields()}
d.set_form_fields([(fmap["customer_name"]["page"], fmap["customer_name"]["xref"], "ABC")])
d.flatten_form()
assert not d.is_form()
print("OK  flatten_form ตรึงค่า native ได้")

# ---- xref ผิดคืน False ไม่พัง ----
d = PdfDocument(src)
assert d.set_form_field(0, 99999, "x") is False
print("OK  xref ผิดคืน False ไม่พัง")

print("\nผ่านทั้งหมด")
