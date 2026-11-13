"""ทดสอบ 2.3.3: แถบบอกว่าไฟล์คลุม/คัดลอกข้อความไม่ได้ (สแกน / Print to PDF) + ปุ่มทำ OCR"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication
from app import i18n
from app.main import MainWindow
from app.pdfops import PdfDocument

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())
FONT = r"C:\Windows\Fonts\tahoma.ttf"

# ไฟล์ปกติ (มีตัวหนังสือจริง)
normal = tmp / "normal.pdf"
d = fitz.open()
page = d.new_page()
page.insert_text((72, 100), "ใบเสนอราคา เลขที่ 2026-118 รายการสินค้าและบริการ", fontname="th", fontfile=FONT, fontsize=14)
d.save(str(normal)); d.close()

# ไฟล์สแกน: หน้าเป็นรูปทั้งหน้า
scan = tmp / "scan.pdf"
pix = fitz.open(str(normal))[0].get_pixmap(dpi=200)
d = fitz.open()
d.new_page().insert_image(fitz.Rect(0, 0, 595, 842), pixmap=pix)
d.save(str(scan)); d.close()

# Print to PDF: ตัวอักษรถูกแปลงเป็นเส้นวาดเยอะๆ ไม่มีฟอนต์
vector = tmp / "printed.pdf"
d = fitz.open()
p = d.new_page()
for row in range(30):
    for col in range(10):
        x, y = 60 + col * 45, 80 + row * 22
        p.draw_bezier((x, y), (x + 10, y - 12), (x + 20, y + 4), (x + 30, y - 6), width=0.8)
d.save(str(vector)); d.close()

# ไฟล์หน้าว่าง / ข้อความสั้นๆ — ไม่ใช่ไฟล์สแกน ไม่ต้องเตือน
blank = tmp / "blank.pdf"
d = fitz.open(); d.new_page(); d.new_page().insert_text((72, 72), "A-1"); d.save(str(blank)); d.close()

# ไฟล์ผสม: หน้า 1 ข้อความจริง หน้า 2 สแกน
mixed = tmp / "mixed.pdf"
d = fitz.open(str(normal)); d.insert_pdf(fitz.open(str(scan))); d.save(str(mixed)); d.close()

assert [PdfDocument(f).looks_textless(0) for f in (normal, scan, vector, blank)] == [False, True, True, False]
print("OK  ตรวจได้: สแกน / ตัวอักษรเป็นเส้นวาด = คลุมไม่ได้ · ไฟล์ปกติ/หน้าว่าง = ไม่เตือน")

w = MainWindow(); w.resize(1200, 800); w.show(); app.processEvents()


def open_file(path):
    w._open_path(str(path))
    for _ in range(3):
        app.processEvents()


open_file(scan)
assert w._ocr_bar.isVisible() and w._ocr_label.text().startswith("🔍 " + i18n.t("ocrbar.all")[:20])
assert "OCR" in w._ocr_go.text()
open_file(normal)
assert not w._ocr_bar.isVisible(), "ไฟล์ปกติไม่มีแถบ"
open_file(vector)
assert w._ocr_bar.isVisible(), "ไฟล์ Print to PDF ก็ต้องบอก"
open_file(blank)
assert not w._ocr_bar.isVisible(), "หน้าว่างไม่ใช่ไฟล์สแกน"
open_file(mixed)
assert w._ocr_bar.isVisible() and "(หน้า 2)" in w._ocr_label.text(), w._ocr_label.text()
print("OK  เปิดไฟล์สแกน/Print to PDF = มีแถบ · ไฟล์ปกติ/หน้าว่างไม่มี · ไฟล์ผสมบอกเลขหน้า")

with patch.object(MainWindow, "ocr_dialog") as ocr:
    w2 = MainWindow()          # ปุ่มต่อสัญญาณตอนสร้างหน้าต่าง จึงสร้างใหม่หลัง patch
    w2._open_path(str(scan)); app.processEvents()
    w2._ocr_go.click()
    assert ocr.called, "ปุ่มบนแถบ = เปิดหน้าต่างทำ OCR"
for tab in w2._tabs:
    tab["doc"].dirty = False

w.tab_bar.setCurrentIndex(0); app.processEvents(); app.processEvents()   # กลับไปไฟล์สแกน
assert w._ocr_bar.isVisible()
w._ocr_close.click()
assert not w._ocr_bar.isVisible()
w.tab_bar.setCurrentIndex(1); app.processEvents(); app.processEvents()
w.tab_bar.setCurrentIndex(0); app.processEvents(); app.processEvents()
assert not w._ocr_bar.isVisible(), "กด × แล้วไม่ขึ้นอีกสำหรับไฟล์นั้น"
w.tab_bar.setCurrentIndex(2); app.processEvents(); app.processEvents()
assert w._ocr_bar.isVisible(), "ไฟล์อื่นยังเตือนตามปกติ"
print("OK  ปุ่มทำ OCR · ซ่อนได้ต่อไฟล์ · ตามแท็บที่ดูอยู่")

# ทำ OCR แล้ว ไฟล์ผลลัพธ์คลุมข้อความได้ -> ไม่มีแถบ
out = PdfDocument(scan).ocr_to_searchable(tmp / "scan-ocr.pdf")
open_file(out)
assert not w._ocr_bar.isVisible(), "ไฟล์ที่ทำ OCR แล้วไม่ต้องเตือน"
print("OK  ไฟล์ที่ทำ OCR แล้ว คลุมได้ ไม่มีแถบ")

for tab in w._tabs:
    tab["doc"].dirty = False
print("\nผ่านทั้งหมด")
