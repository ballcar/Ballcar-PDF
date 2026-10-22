"""ทดสอบ OCR ภาษาไทย/อังกฤษ (ต้องมี Tesseract + tha.traineddata ในเครื่อง)"""
import sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fitz
from PySide6.QtWidgets import QApplication, QMessageBox
from app import pdfops
from app.main import MainWindow
from app.pdfops import PdfDocument, find_thai_font

tmp = Path(tempfile.mkdtemp())

print("Tesseract:", pdfops.tesseract_dir())
print("ภาษาที่มี:", pdfops.ocr_languages())
assert pdfops.tesseract_dir(), "ยังไม่ได้ลง Tesseract"
assert "tha" in pdfops.ocr_languages(), "ยังไม่มีชุดภาษาไทย"
pdfops.ensure_tesseract()
print("OK  ตรวจพบ Tesseract + ภาษาไทย")

# สร้าง "ไฟล์สแกน" จำลอง: เขียนข้อความแล้วแปลงทั้งหน้าเป็นรูป (ข้อความหายไป เหลือแต่ภาพ)
THAI = "ใบเสนอราคา บริษัท ออมใจ จำกัด"
ENG = "Total Amount 38,200.00"
build = fitz.open()
page = build.new_page(width=595, height=842)
page.insert_font(fontname="thai", fontfile=find_thai_font())
page.insert_text((60, 120), THAI, fontname="thai", fontsize=26)
page.insert_text((60, 200), ENG, fontsize=24)
flat = fitz.open()
scan_page = flat.new_page(width=595, height=842)
scan_page.insert_image(scan_page.rect, pixmap=page.get_pixmap(dpi=200))
src = tmp / "scan.pdf"
flat.save(str(src)); flat.close(); build.close()

d = PdfDocument(src)
assert d.needs_ocr(0), "หน้าสแกนต้องถูกตรวจว่าไม่มีข้อความ"
assert len(d.page_text(0).strip()) < 20
print("OK  ตรวจจับได้ว่าเป็นหน้าสแกน (ไม่มีข้อความ)")

# ---- อ่านข้อความ ----
text = d.ocr_text(0, language="tha+eng")
print("   อ่านได้:", " ".join(text.split())[:80])
assert "ใบเสนอราคา" in text, f"อ่านภาษาไทยไม่ออก ได้: {text[:200]!r}"
assert "38,200" in text.replace(" ", ""), f"อ่านตัวเลขไม่ออก ได้: {text[:200]!r}"
print("OK  OCR อ่านภาษาไทย + ตัวเลขออก")

# ---- สร้าง PDF ที่ค้นหาได้ ----
out = tmp / "searchable.pdf"
steps = []
d.ocr_to_searchable(out, progress=lambda a, b: steps.append((a, b)))
assert out.exists()
assert steps == [(1, 1)], steps

with fitz.open(out) as v:
    got = v.load_page(0).get_text()
    assert "ใบเสนอราคา" in got, f"ข้อความไม่ถูกฝัง ได้: {got[:200]!r}"
    assert v.load_page(0).search_for("ใบเสนอราคา"), "ต้องค้นหาคำไทยเจอ"
    assert len(v.load_page(0).get_images()) >= 1, "ภาพต้นฉบับต้องยังอยู่"
print("OK  สร้าง PDF ที่ค้นหาข้อความไทยได้ และภาพเดิมยังอยู่")

# ---- เลือกเฉพาะบางหน้า ----
two = fitz.open()
for i in range(2):
    p = two.new_page(width=595, height=842)
    p.insert_image(p.rect, pixmap=fitz.open(src)[0].get_pixmap(dpi=120))
src2 = tmp / "two.pdf"
two.save(str(src2)); two.close()

d2 = PdfDocument(src2)
out2 = tmp / "page2only.pdf"
d2.ocr_to_searchable(out2, indexes=[1])
with fitz.open(out2) as v:
    assert v.page_count == 1, "เลือก 1 หน้า ต้องได้ไฟล์ 1 หน้า"
print("OK  OCR เฉพาะหน้าที่เลือก")

# ---- หน้าที่มีข้อความอยู่แล้ว ----
normal = fitz.open()
np_ = normal.new_page(width=595, height=842)
np_.insert_text((60, 100), "This page already has selectable text in it.", fontsize=14)
src3 = tmp / "normal.pdf"
normal.save(str(src3)); normal.close()
d3 = PdfDocument(src3)
assert not d3.needs_ocr(0), "หน้าที่มีข้อความไม่ควรถูกมองว่าเป็นสแกน"
print("OK  หน้าที่มีข้อความอยู่แล้วไม่ถูกมองว่าเป็นสแกน")

# ---- ผ่าน UI: สร้าง PDF ค้นหาได้ ----
app = QApplication(sys.argv)
w = MainWindow()
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)

ui_out = tmp / "ui-ocr.pdf"
with patch("app.main.QInputDialog.getItem", side_effect=[
        ("ทุกหน้า (1 หน้า)", True), ("ไทย + อังกฤษ", True),
        ("สร้าง PDF ที่ค้นหา/คัดลอกข้อความได้", True)]), \
     patch("app.main.QFileDialog.getSaveFileName", return_value=(str(ui_out), "")), \
     patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    w.ocr_dialog()
assert ui_out.exists()
with fitz.open(ui_out) as v:
    assert "ใบเสนอราคา" in v.load_page(0).get_text()
print("OK  ทำ OCR ผ่านเมนูได้")

# ---- ผ่าน UI: ดึงเป็น .txt ----
ui_txt = tmp / "ui.txt"
with patch("app.main.QInputDialog.getItem", side_effect=[
        ("ทุกหน้า (1 หน้า)", True), ("ไทย + อังกฤษ", True),
        ("ดึงเป็นไฟล์ข้อความ (.txt)", True)]), \
     patch("app.main.QFileDialog.getSaveFileName", return_value=(str(ui_txt), "")):
    w.ocr_dialog()
body = ui_txt.read_text(encoding="utf-8")
assert "--- หน้า 1 ---" in body and "ใบเสนอราคา" in body, body[:200]
print("OK  ดึงข้อความ OCR เป็น .txt ได้")

# ---- ไม่มีไฟล์ภาษาเลย ต้องเตือนให้รู้วิธีแก้ ----
# หมายเหตุ: ตั้งแต่ 1.0.62 ไม่ต้องติดตั้ง Tesseract แยกแล้ว (ไฟล์ภาษาแถมมากับตัวติดตั้ง)
# จึงไม่แนะนำ winget อีก แต่บอกให้ติดตั้งโปรแกรมใหม่แทน
with patch("app.pdfops.tessdata_dir", return_value=None):
    try:
        pdfops.ensure_tesseract()
    except RuntimeError as exc:
        assert "ติดตั้งโปรแกรมใหม่" in str(exc), str(exc)
        print("OK  ไม่มีไฟล์ภาษาแล้วเตือนพร้อมวิธีแก้")
    else:
        raise AssertionError("ควร error")

# ---- มีไฟล์ภาษา แต่ไม่มีภาษาไทย ----
with patch("app.pdfops.ocr_languages", return_value=["eng", "osd"]):
    try:
        pdfops.ensure_tesseract()
    except RuntimeError as exc:
        assert "ภาษาไทย" in str(exc)
        print("OK  ไม่มีชุดภาษาไทยแล้วเตือนพร้อมลิงก์")
    else:
        raise AssertionError("ควร error")

print("\nผ่านทั้งหมด")
