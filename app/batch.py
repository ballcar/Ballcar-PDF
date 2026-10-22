"""ประมวลผลไฟล์ PDF หลายไฟล์พร้อมกัน (Batch Processing)

แต่ละงาน (operation) เป็นฟังก์ชันที่รับ (ไฟล์เข้า, โฟลเดอร์ออก, พารามิเตอร์)
ต่อยอดจากตรรกะใน PdfDocument ที่มีอยู่แล้ว
"""
from __future__ import annotations

from pathlib import Path

from .pdfops import PasswordRequired, PdfDocument, merge_files


def _out_path(out_dir: Path, src: Path, suffix: str = "", ext: str = ".pdf") -> Path:
    return Path(out_dir) / f"{src.stem}{suffix}{ext}"


# ---------- งานแบบไฟล์ต่อไฟล์ (1 เข้า -> 1 ออก) ----------

def op_watermark_text(src: Path, out_dir: Path, params: dict) -> Path:
    doc = PdfDocument(src, password=params.get("password"))
    doc.add_text_watermark(params["text"], opacity=params.get("opacity", 0.18),
                           angle=params.get("angle", 45))
    out = _out_path(out_dir, src, "-watermark")
    doc.save(out)
    doc.close()
    return out


def op_ocr(src: Path, out_dir: Path, params: dict) -> Path:
    doc = PdfDocument(src, password=params.get("password"))
    out = _out_path(out_dir, src, "-ocr")
    doc.ocr_to_searchable(out, language=params.get("language", "tha+eng"))
    doc.close()
    return out


def op_to_word(src: Path, out_dir: Path, params: dict) -> Path:
    doc = PdfDocument(src, password=params.get("password"))
    out = _out_path(out_dir, src, "", ".docx")
    doc.to_word(out)
    doc.close()
    return out


def op_to_excel(src: Path, out_dir: Path, params: dict) -> Path:
    doc = PdfDocument(src, password=params.get("password"))
    out = _out_path(out_dir, src, "", ".xlsx")
    doc.to_excel(out)   # ValueError ถ้าไม่เจอตาราง
    doc.close()
    return out


def op_to_images(src: Path, out_dir: Path, params: dict) -> Path:
    doc = PdfDocument(src, password=params.get("password"))
    folder = Path(out_dir) / src.stem
    doc.export_images(list(range(doc.page_count)), folder,
                      dpi=params.get("dpi", 150), fmt=params.get("fmt", "jpg"))
    doc.close()
    return folder


def op_page_numbers(src: Path, out_dir: Path, params: dict) -> Path:
    doc = PdfDocument(src, password=params.get("password"))
    doc.add_page_numbers(position=params.get("position", "bottom-center"))
    out = _out_path(out_dir, src, "-numbered")
    doc.save(out)
    doc.close()
    return out


def op_set_password(src: Path, out_dir: Path, params: dict) -> Path:
    doc = PdfDocument(src, password=params.get("open_password"))
    out = _out_path(out_dir, src, "-locked")
    doc.save_with_password(out, params["password"])
    doc.close()
    return out


def op_remove_password(src: Path, out_dir: Path, params: dict) -> Path:
    doc = PdfDocument(src, password=params.get("open_password"))
    out = _out_path(out_dir, src, "-unlocked")
    doc.save_with_password(out, "")
    doc.close()
    return out


# key -> ฟังก์ชัน (งานที่ทำทีละไฟล์)
OPERATIONS = {
    "watermark_text": op_watermark_text,
    "ocr": op_ocr,
    "to_word": op_to_word,
    "to_excel": op_to_excel,
    "to_images": op_to_images,
    "page_numbers": op_page_numbers,
    "set_password": op_set_password,
    "remove_password": op_remove_password,
}


def run_batch(files, out_dir, operation: str, params: dict, progress=None) -> list[dict]:
    """รันงานเดียวกันกับทุกไฟล์ คืนผลลัพธ์รายไฟล์ (ok/ข้อผิดพลาด)

    progress(done, total, ชื่อไฟล์) ถูกเรียกก่อนประมวลผลแต่ละไฟล์
    """
    op = OPERATIONS.get(operation)
    if op is None:
        raise ValueError(f"ไม่รู้จักงาน: {operation}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    files = [Path(f) for f in files]
    for i, src in enumerate(files):
        if progress:
            progress(i, len(files), src.name)
        try:
            out = op(src, out_dir, params)
            results.append({"file": src, "ok": True, "out": out})
        except PasswordRequired:
            results.append({"file": src, "ok": False, "error": "ไฟล์มีรหัสผ่าน (ข้าม)"})
        except Exception as exc:
            results.append({"file": src, "ok": False, "error": str(exc)})
    if progress:
        progress(len(files), len(files), "")
    return results


# ---------- งานพิเศษ: รวมทุกไฟล์เป็นไฟล์เดียว ----------

def run_merge(files, target, progress=None) -> Path:
    if progress:
        progress(0, 1, "merge")
    result = merge_files([Path(f) for f in files], target)
    if progress:
        progress(1, 1, "")
    return result
