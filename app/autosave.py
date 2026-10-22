"""สำรองงานอัตโนมัติแบบกู้คืน (Pre-save / recovery)

แนวคิด: ไม่เขียนทับไฟล์ต้นฉบับ แต่แอบเก็บสำเนาไว้ใน %APPDATA% เป็นระยะ
ถ้าโปรแกรมปิดไม่ปกติ (ไฟดับ/ค้าง) ครั้งหน้าจะถามผู้ใช้ว่าจะกู้คืนไหม
พอบันทึกจริงหรือปิดปกติแล้ว ไฟล์กู้คืนจะถูกลบทิ้ง
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def autosave_dir() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    folder = base / "BallcarPDF" / "autosave"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _slug(session_id: str) -> str:
    """ชื่อไฟล์กู้คืน — ผูกกับ session เท่านั้น (ชื่อไฟล์เปลี่ยนตอน 'บันทึกเป็น' ก็ยังตรง)"""
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:40] or "sess"
    return f"recovery__{safe}"


def write_recovery(pdf_bytes: bytes, original_path: str | None, session_id: str) -> Path:
    """เขียนไฟล์กู้คืน + ข้อมูลกำกับ คืน path ของไฟล์ pdf กู้คืน"""
    folder = autosave_dir()
    slug = _slug(session_id)
    pdf_file = folder / f"{slug}.pdf"
    tmp = pdf_file.with_suffix(".pdf.tmp")
    tmp.write_bytes(pdf_bytes)          # เขียนไฟล์ชั่วคราวก่อนสลับ กันไฟล์เสียถ้าดับกลางคัน
    tmp.replace(pdf_file)
    meta = folder / f"{slug}.json"
    meta.write_text(json.dumps({
        "original": original_path,
        "saved_at": time.time(),
        "pdf": pdf_file.name,
    }, ensure_ascii=False), encoding="utf-8")
    return pdf_file


def clear_recovery(original_path: str | None, session_id: str) -> None:
    """ลบไฟล์กู้คืนของ session นี้ (เรียกตอนบันทึกจริง/ปิดปกติ)"""
    folder = autosave_dir()
    slug = _slug(session_id)
    for f in (folder / f"{slug}.pdf", folder / f"{slug}.json",
              folder / f"{slug}.pdf.tmp"):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


def pending_recoveries() -> list[dict]:
    """งานค้างที่ยังไม่ถูกกู้ — คืน list ของ {original, saved_at, pdf_path}"""
    folder = autosave_dir()
    out = []
    for meta in folder.glob("*.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            pdf_path = folder / data["pdf"]
            if pdf_path.exists():
                out.append({
                    "original": data.get("original"),
                    "saved_at": data.get("saved_at", 0),
                    "pdf_path": pdf_path,
                    "meta_path": meta,
                })
        except (OSError, ValueError, KeyError):
            continue
    out.sort(key=lambda d: d["saved_at"], reverse=True)
    return out


def discard_recovery(meta_path: Path) -> None:
    """ทิ้งงานค้าง (ผู้ใช้เลือกไม่กู้)"""
    try:
        data = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        (Path(meta_path).parent / data["pdf"]).unlink(missing_ok=True)
    except (OSError, ValueError, KeyError):
        pass
    try:
        Path(meta_path).unlink(missing_ok=True)
    except OSError:
        pass
