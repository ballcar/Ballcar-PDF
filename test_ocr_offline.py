"""ทดสอบ OCR แบบไม่ต้องต่อเน็ต — ใช้ไฟล์ภาษาที่แถมมากับโปรแกรม

เครื่องลูกที่ออกอินเทอร์เน็ตไม่ได้ ต้องใช้ OCR ได้ทันทีหลังติดตั้ง
โดยไม่ต้องลง Tesseract แยก (OCR ใช้เอนจินที่ฝังมาใน PyMuPDF อยู่แล้ว)
"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from app import pdfops

ROOT = Path(__file__).resolve().parent

# ---- ไฟล์ภาษาต้องอยู่ในโปรเจกต์ พร้อมแพ็กไปกับตัวติดตั้ง ----
shipped = ROOT / "tessdata"
assert shipped.is_dir(), "ต้องมีโฟลเดอร์ tessdata ในโปรเจกต์ (แถมไปกับตัวติดตั้ง)"
names = sorted(p.name for p in shipped.glob("*.traineddata"))
assert "tha.traineddata" in names, f"ต้องมีภาษาไทย ได้ {names}"
assert "eng.traineddata" in names, f"ต้องมีภาษาอังกฤษ ได้ {names}"
size = sum(p.stat().st_size for p in shipped.glob("*.traineddata")) / 1024 / 1024
print(f"OK  มีไฟล์ภาษาในโปรเจกต์: {', '.join(names)} ({size:.1f} MB)")

# ---- หาไฟล์ภาษาเจอตอนรันจากซอร์ส ----
found = pdfops.bundled_tessdata()
assert found is not None and found.resolve() == shipped.resolve(), f"ควรเจอ {shipped} ได้ {found}"
print("OK  หาโฟลเดอร์ภาษาที่แถมมาเจอ")

# ---- ต้องเลือกของที่แถมมาก่อน Tesseract ที่ลงในเครื่อง ----
with patch.dict(os.environ, {"TESSDATA_DIR": r"C:\ที่ไม่มีอยู่จริง"}, clear=False):
    assert Path(pdfops.tessdata_dir()).resolve() == shipped.resolve(), \
        "ของที่แถมมาต้องมาก่อนค่าที่ตั้งเอง/ที่ลงในเครื่อง"
print("OK  ใช้ไฟล์ภาษาที่แถมมาก่อนเสมอ")

langs = pdfops.ocr_languages()
assert "tha" in langs and "eng" in langs, langs
print(f"OK  รายการภาษาที่ใช้ได้: {langs}")

pdfops.ensure_tesseract()          # ต้องไม่ error
print("OK  ระบบพร้อมทำ OCR (ไม่ต้องลง Tesseract แยก)")


# ================= OCR ได้จริงทั้งไทยและอังกฤษ =================

def scanned_pdf(text: str, fontfile: str | None = None) -> Path:
    """สร้าง PDF ที่เป็น 'รูปภาพ' ล้วน (เลียนแบบไฟล์สแกน — ไม่มีข้อความให้ค้นหา)"""
    d = fitz.open()
    page = d.new_page(width=420, height=140)
    if fontfile:
        page.insert_font(fontname="th", fontfile=fontfile)
        page.insert_text((25, 85), text, fontsize=30, fontname="th")
    else:
        page.insert_text((25, 85), text, fontsize=30)
    pix = page.get_pixmap(dpi=300)
    d.close()

    out = fitz.open()
    p2 = out.new_page(width=420, height=140)
    p2.insert_image(p2.rect, pixmap=pix)
    path = Path(tempfile.mkdtemp()) / "scan.pdf"
    out.save(str(path)); out.close()
    return path


eng_pdf = scanned_pdf("Invoice 2026 Total 155,373")
with fitz.open(str(eng_pdf)) as v:
    assert v.load_page(0).get_text().strip() == "", "ไฟล์ทดสอบต้องเป็นรูปล้วน (ยังไม่มีข้อความ)"
print("OK  สร้างไฟล์สแกนจำลอง (ยังค้นหาข้อความไม่ได้)")

# เรียกผ่านเส้นทางเดียวกับที่โปรแกรมใช้จริง
with fitz.open(str(eng_pdf)) as v:
    pix = v.load_page(0).get_pixmap(dpi=300)
    ocr = fitz.open("pdf", pix.pdfocr_tobytes(language="eng", tessdata=pdfops.tessdata_dir()))
    got = ocr.load_page(0).get_text()
    ocr.close()
assert "Invoice" in got, f"OCR อังกฤษไม่ได้ผล: {got!r}"
print(f"OK  OCR ภาษาอังกฤษได้: {got.split()[0:3]}")

thai_font = pdfops.find_thai_font()
if thai_font:
    tha_pdf = scanned_pdf("ใบวางบิล", fontfile=thai_font)
    with fitz.open(str(tha_pdf)) as v:
        pix = v.load_page(0).get_pixmap(dpi=300)
        ocr = fitz.open("pdf", pix.pdfocr_tobytes(language="tha", tessdata=pdfops.tessdata_dir()))
        got_th = ocr.load_page(0).get_text()
        ocr.close()
    assert got_th.strip(), "OCR ภาษาไทยต้องได้ข้อความออกมา"
    print(f"OK  OCR ภาษาไทยได้ข้อความออกมา ({got_th.strip()[:20]!r})")
else:
    print("ข้าม  ไม่พบฟอนต์ไทยในเครื่องนี้")

# ---- ไม่มีไฟล์ภาษาเลย -> ต้องบอกวิธีแก้ ไม่ใช่พังเงียบ ----
with patch.object(pdfops, "bundled_tessdata", return_value=None), \
     patch.dict(os.environ, {"TESSDATA_DIR": "", "TESSERACT_DIR": ""}, clear=False), \
     patch.object(pdfops, "TESSERACT_CANDIDATES", []):
    assert pdfops.tessdata_dir() is None
    assert pdfops.ocr_languages() == []
    try:
        pdfops.ensure_tesseract()
        raise AssertionError("ต้องแจ้งเตือนเมื่อไม่มีไฟล์ภาษา")
    except RuntimeError as exc:
        assert "ติดตั้งโปรแกรมใหม่" in str(exc), str(exc)
print("OK  ไม่มีไฟล์ภาษา -> แจ้งวิธีแก้ชัดเจน")

# ---- มีแต่อังกฤษ ไม่มีไทย -> บอกให้ชัดว่าขาดอะไร ----
only_eng = Path(tempfile.mkdtemp()) / "tessdata"
only_eng.mkdir()
(only_eng / "eng.traineddata").write_bytes((shipped / "eng.traineddata").read_bytes())
with patch.object(pdfops, "bundled_tessdata", return_value=only_eng):
    try:
        pdfops.ensure_tesseract()
        raise AssertionError("ต้องแจ้งว่าไม่มีภาษาไทย")
    except RuntimeError as exc:
        assert "ภาษาไทย" in str(exc) and "eng" in str(exc), str(exc)
print("OK  ขาดภาษาไทย -> บอกว่าพบภาษาอะไรและต้องวางไฟล์ที่ไหน")

# ---- ตัวติดตั้งต้องไม่พึ่งอินเทอร์เน็ตแล้ว ----
iss = (ROOT / "installer" / "BallcarPDF.iss").read_text(encoding="utf-8-sig")
assert "install-ocr.ps1" not in iss, "ตัวติดตั้งต้องไม่เรียกสคริปต์โหลด OCR จากเน็ตแล้ว"
assert "installocr" not in iss, "ต้องไม่มีตัวเลือกติดตั้ง OCR ที่ต้องต่อเน็ต"
build = (ROOT / "build-exe.ps1").read_text(encoding="utf-8")
assert "tessdata;tessdata" in build, "build ต้องแพ็กโฟลเดอร์ tessdata ไปด้วย"
print("OK  ตัวติดตั้งไม่พึ่งอินเทอร์เน็ต และ build แพ็กไฟล์ภาษาไปด้วย")

print("\nผ่านทั้งหมด")
