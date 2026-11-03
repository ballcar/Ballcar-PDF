"""ทดสอบแปลงเป็น Word จากไฟล์สแกน: หน้าที่เป็นภาพต้องได้ข้อความที่แก้ไขได้ (OCR) ไม่ใช่รูปทั้งหน้า"""
import os, re, sys, tempfile, zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app import pdfops
from app.pdfops import PdfDocument, find_thai_font

tmp = Path(tempfile.mkdtemp())


def docx_text(path) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    return " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml))


def docx_media(path) -> list[str]:
    return [n for n in zipfile.ZipFile(path).namelist() if n.startswith("word/media/")]


def make_scan(name: str, lines: list[str]) -> Path:
    """สร้าง PDF ที่เป็นภาพล้วน (เหมือนสแกนจากเครื่องถ่ายเอกสาร)"""
    text = fitz.open()
    page = text.new_page(width=595, height=842)
    page.insert_font(fontname="thai", fontfile=find_thai_font())
    for n, line in enumerate(lines):
        page.insert_text((60, 90 + n * 30), line, fontname="thai", fontsize=16)
    pix = page.get_pixmap(dpi=200)
    scan = fitz.open()
    scan.new_page(width=595, height=842).insert_image(fitz.Rect(0, 0, 595, 842), pixmap=pix)
    out = tmp / name
    scan.save(str(out))
    return out


# ---- ต่อชิ้น OCR: อังกฤษเว้นวรรคทีละคำ ไทยไม่แตกเป็นตัวอักษร ----
def span(text, x0, x1, h=10):
    return {"text": text, "bbox": (x0, 0, x1, h)}

assert pdfops._join_ocr_spans([span("Dear", 0, 20), span("Sir", 22, 35)]) == "Dear Sir"
# ไทยมาเป็นชิ้นติดกัน ห้ามมีช่องว่าง และ ํ+า ต้องรวมเป็น ำ
thai = [span("บ", 0, 5), span("ร", 5.5, 10), span("ิ", 10.2, 12), span("ษั", 12.5, 18),
        span("ท", 18.5, 23)]
assert pdfops._join_ocr_spans(thai) == "บริษัท", pdfops._join_ocr_spans(thai)
assert pdfops._join_ocr_spans([span("ทํ", 0, 6), span("า", 6.5, 10)]) == "ทำ"
# ช่องว่างจริงระหว่างคำไทย (กว้าง) ต้องคงไว้
assert pdfops._join_ocr_spans([span("ไอที", 0, 20), span("อินฟินิท", 30, 60)]) == "ไอที อินฟินิท"
# ช่องห่างแคบในคำไทย (OCR ตีกรอบตัวอักษรแคบ) ห้ามกลายเป็นวรรคกลางคำ
assert pdfops._join_ocr_spans([span("ษั", 0, 9, h=11), span("ท", 17, 22, h=11)]) == "ษัท"
assert pdfops._is_ocr_noise("* ' .") and not pdfops._is_ocr_noise("ข้อ 1.")
print("OK  ต่อชิ้น OCR: อังกฤษเว้นวรรค ไทยไม่แตกตัว ำ ถูกต้อง ตัดเส้นขยะทิ้ง")

# ---- ไฟล์สแกนอังกฤษ -> Word มีข้อความจริง ไม่ใช่รูปทั้งหน้า ----
scan_en = make_scan("scan_en.pdf", ["Dear Sir / Madam,", "Re: Unlicensed Use of Software",
                                    "Please contact us before 12 September 2022."])
doc = PdfDocument(scan_en)
assert doc.scanned_pages() == [0]
calls = []
out = doc.to_word(tmp / "scan_en.docx", progress=lambda d, t: calls.append((d, t)))
text = docx_text(out)
for word in ("Dear Sir", "Unlicensed Use of Software", "September 2022"):
    assert word in text, f"ไม่พบ {word!r} ใน Word: {text[:200]!r}"
assert docx_media(out) == [], f"หน้าสแกนต้องไม่เหลือรูปทั้งหน้าใน Word: {docx_media(out)}"
assert calls == [(1, 1)], f"ต้องรายงานความคืบหน้า OCR: {calls}"
print("OK  ไฟล์สแกนภาษาอังกฤษได้ Word ที่เป็นข้อความ")

# ---- ไฟล์สแกนไทย ----
scan_th = make_scan("scan_th.pdf", ["บริษัท ทดสอบ จำกัด", "ใบสั่งซื้อสินค้า"])
text = docx_text(PdfDocument(scan_th).to_word(tmp / "scan_th.docx"))
# OCR ไทยอาจทำวรรณยุกต์หล่นบ้าง (ข้อจำกัดของตัวอ่าน) ตรวจเฉพาะคำที่ไม่มีวรรณยุกต์
assert "บริษัท" in text and "ทดสอบ" in text and "สินค" in text, text
print("OK  ไฟล์สแกนภาษาไทยได้ข้อความไทยใน Word")

# ---- หน้าสแกนที่เครื่องสแกนเก็บแบบหมุน (/Rotate 270) ต้องได้ข้อความเรียงถูก ----
# เคยพัง: พิกัด OCR อยู่ในระบบที่ยังไม่หมุน บรรทัดแตกกระจาย Word ได้ภาษาเพี้ยนทั้งหน้า
src = fitz.open(str(scan_en))
pix = src[0].get_pixmap(dpi=200)
rotated = fitz.open()
page = rotated.new_page(width=842, height=595)      # เก็บภาพแนวนอน แล้วสั่งหมุนตอนแสดง
page.insert_image(page.rect, pixmap=pix, rotate=270)
page.set_rotation(270)
rot_path = tmp / "rotated.pdf"; rotated.save(str(rot_path))
assert fitz.open(str(rot_path))[0].rect.width < fitz.open(str(rot_path))[0].rect.height
text = docx_text(PdfDocument(rot_path).to_word(tmp / "rotated.docx"))
for word in ("Dear Sir", "Unlicensed Use of Software"):
    assert word in text, f"หน้าหมุน: ไม่พบ {word!r} ใน {text[:200]!r}"
assert text.index("Dear Sir") < text.index("Unlicensed"), "ลำดับบรรทัดต้องเรียงจากบนลงล่าง"
print("OK  หน้าสแกนที่ถูกหมุน (/Rotate 270) ได้ข้อความเรียงถูกต้อง")

# ---- ocr=False ได้แบบเดิม (รูปทั้งหน้า) ----
out = PdfDocument(scan_en).to_word(tmp / "no_ocr.docx", ocr=False)
assert docx_media(out) and "Dear" not in docx_text(out)
print("OK  ocr=False ได้ผลแบบเดิม")

# ---- PDF ที่มีข้อความอยู่แล้ว ไม่ต้อง OCR (ไม่เรียก Tesseract) ----
plain = fitz.open()
plain.new_page().insert_text((72, 72), "Hello text PDF with a real text layer", fontsize=14)
plain_path = tmp / "plain.pdf"; plain.save(str(plain_path))
doc = PdfDocument(plain_path)
assert doc.scanned_pages() == []
with patch.object(PdfDocument, "_ocr_text_page", side_effect=AssertionError("ไม่ควร OCR")):
    assert "Hello text PDF" in docx_text(doc.to_word(tmp / "plain.docx"))
print("OK  PDF ที่มีข้อความแปลงแบบเดิม ไม่เสียเวลา OCR")

# ---- ไฟล์ผสม: หน้าข้อความ + หน้าสแกน ลำดับหน้าต้องคงเดิม ----
mixed = fitz.open(str(plain_path)); mixed.insert_pdf(fitz.open(str(scan_en)))
mixed_path = tmp / "mixed.pdf"; mixed.save(str(mixed_path))
doc = PdfDocument(mixed_path)
assert doc.scanned_pages() == [1]
text = docx_text(doc.to_word(tmp / "mixed.docx"))
assert text.index("Hello text PDF") < text.index("Dear Sir"), "ลำดับหน้าต้องคงเดิม"
# เลือกแปลงเฉพาะหน้าแรก -> ไม่ต้อง OCR หน้าที่ไม่ได้เลือก
with patch.object(PdfDocument, "_ocr_text_page", side_effect=AssertionError("ไม่ควร OCR")):
    doc.to_word(tmp / "mixed_p1.docx", indexes=[0])
print("OK  ไฟล์ผสมคงลำดับหน้า และ OCR เฉพาะหน้าที่เลือก")

# ---- เมนูแปลงเป็น Word บอกผู้ใช้ว่ามีหน้าสแกนที่ทำ OCR ----
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from app import main as M

app = QApplication.instance() or QApplication(sys.argv)
w = M.MainWindow()
w.doc = PdfDocument(scan_en)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)
shown = {}
with patch.object(w, "_ask_scope", return_value=[0]), \
     patch.object(QFileDialog, "getSaveFileName", return_value=(str(tmp / "ui.docx"), "")), \
     patch.object(QMessageBox, "information",
                  side_effect=lambda parent, title, msg: shown.update(msg=msg)), \
     patch.object(QMessageBox, "critical", side_effect=AssertionError("ไม่ควรล้ม")):
    w.export_word()
assert (tmp / "ui.docx").exists()
assert "OCR" in shown.get("msg", "") and "1" in shown["msg"], shown
print("OK  เมนูแปลงเป็น Word แจ้งว่าหน้าไหนอ่านด้วย OCR และให้ตรวจทาน")

print("")
print("ผ่านทั้งหมด")
