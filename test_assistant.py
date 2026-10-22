"""ทดสอบผู้ช่วยพิมพ์คำสั่ง (parser) + ฟังก์ชันอัตโนมัติ"""
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from app import assistant
from app.pdfops import PdfDocument, find_thai_font, _int_to_roman

tmp = Path(tempfile.mkdtemp())


# ============ parser ============
def act(cmd):
    it = assistant.parse(cmd)
    return it.action if it else None


assert act("ลบหน้าว่างทั้งหมด") == "delete_blank"
assert act("เอาหน้าว่างออก") == "delete_blank"
assert act("หมุนทุกหน้าแนวนอน") == "orientation"
assert assistant.parse("หมุนทุกหน้าแนวนอน").params["orientation"] == "landscape"
assert assistant.parse("หมุนแนวตั้ง").params["orientation"] == "portrait"
assert assistant.parse("หมุนขวา").params["degrees"] == 90
assert act("ใส่เลขหน้าเป็นเลขโรมัน") == "page_numbers"
assert assistant.parse("เลขหน้าโรมัน").params["numeral"] == "roman"
assert act("OCR ทุกหน้า") == "ocr"
assert act("ลบข้อมูลส่วนบุคคล") == "redact_pii"
assert assistant.parse('ดึงเฉพาะหน้าที่มีคำว่า "ใบเสนอราคา"').params["keyword"] == "ใบเสนอราคา"
assert assistant.parse('ใส่ลายน้ำ "สำเนา"').params["text"] == "สำเนา"
print("OK  parser เข้าใจคำสั่งหลัก")

# แปล/สรุป -> ต้องบอกว่าใช้ AI ออนไลน์
tr = assistant.parse("แปล PDF เป็นไทย")
assert tr.needs_online_ai and tr.action == "needs_ai"
sm = assistant.parse("สรุปเอกสารให้หน่อย")
assert sm.needs_online_ai
print("OK  แปล/สรุป บอกว่าต้องใช้ AI ออนไลน์")

# คำสั่งมั่ว -> None
assert assistant.parse("อยากกินข้าว") is None
assert assistant.parse("") is None
print("OK  คำสั่งที่ไม่เข้าใจคืน None")

# ============ ฟังก์ชันอัตโนมัติ ============
assert _int_to_roman(1) == "I" and _int_to_roman(4) == "IV" and _int_to_roman(9) == "IX"
assert _int_to_roman(2024) == "MMXXIV"
print("OK  แปลงเลขโรมัน")


def make(pages_content):
    """pages_content = list of str (ข้อความในหน้า, '' = หน้าว่าง)"""
    doc = fitz.open()
    for content in pages_content:
        p = doc.new_page(width=595, height=842)
        if content:
            p.insert_font(fontname="thai", fontfile=find_thai_font())
            p.insert_text((72, 100), content, fontname="thai", fontsize=13)
    path = tmp / f"t{len(list(tmp.glob('*.pdf')))}.pdf"
    doc.save(str(path)); doc.close()
    return path


# ---- ลบหน้าว่าง ----
src = make(["หน้ามีเนื้อหา", "", "อีกหน้า", ""])
d = PdfDocument(src)
assert d.find_blank_pages() == [1, 3]
n = d.delete_blank_pages()
assert n == 2 and d.page_count == 2
print("OK  ลบหน้าว่าง")

# ไม่ลบถ้าจะเหลือ 0
empty = make(["", ""])
d = PdfDocument(empty)
assert d.delete_blank_pages() == 0 and d.page_count == 2
print("OK  ไม่ลบจนเหลือ 0 หน้า")

# ---- หมุนแนวนอน ----
src = make(["ก", "ข", "ค"])   # ทุกหน้าแนวตั้ง (595x842)
d = PdfDocument(src)
n = d.set_orientation(list(range(3)), "landscape")
assert n == 3
for i in range(3):
    assert d.doc.load_page(i).rect.width > d.doc.load_page(i).rect.height
# สั่งซ้ำ = แนวนอนอยู่แล้ว ไม่เปลี่ยน
assert d.set_orientation(list(range(3)), "landscape") == 0
print("OK  หมุนแนวนอน (และไม่หมุนซ้ำ)")

# ---- เก็บเฉพาะหน้าที่มีคำ ----
src = make(["ใบเสนอราคา A", "ใบกำกับภาษี", "ใบเสนอราคา B", "อื่นๆ"])
d = PdfDocument(src)
assert d.pages_matching("ใบเสนอราคา") == [0, 2]
d.keep_only_pages([0, 2])
assert d.page_count == 2
assert "ใบเสนอราคา" in d.page_text(0) and "ใบเสนอราคา" in d.page_text(1)
print("OK  เก็บเฉพาะหน้าที่มีคำ")

# ---- เลขหน้าโรมัน ----
src = make(["a", "b", "c"])
d = PdfDocument(src)
d.add_page_numbers(fmt="{page}", numeral="roman")
out = tmp / "roman.pdf"; d.save(out)
with fitz.open(out) as v:
    assert "III" in v.load_page(2).get_text(), v.load_page(2).get_text()
print("OK  เลขหน้าโรมัน")

# ---- ลบข้อมูลส่วนบุคคล ----
doc = fitz.open()
p = doc.new_page(width=595, height=842)
p.insert_text((72, 100), "ติดต่อ somchai@email.com โทร 0812345678", fontsize=12)
p.insert_text((72, 130), "เลขบัตร 1234567890123", fontsize=12)
psrc = tmp / "pii.pdf"; doc.save(str(psrc)); doc.close()
d = PdfDocument(psrc)
n = d.redact_personal_info()
assert n >= 3, f"ควรปิด >=3 จุด ได้ {n}"
out = tmp / "clean.pdf"; d.save(out)
with fitz.open(out) as v:
    text = v.load_page(0).get_text()
    assert "somchai@email.com" not in text
    assert "0812345678" not in text
    assert "1234567890123" not in text
print("OK  ลบข้อมูลส่วนบุคคล (อีเมล/เบอร์/เลขบัตร)")

print("\nผ่านทั้งหมด")
