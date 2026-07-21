"""คลังลายเซ็น — เก็บลายเซ็นที่ใช้บ่อยไว้ในเครื่อง เรียกใช้ซ้ำได้"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def library_dir() -> Path:
    """โฟลเดอร์เก็บลายเซ็น (อยู่ใน AppData ไม่หายตอนอัปเดตโปรแกรม)"""
    base = Path(os.environ.get("APPDATA") or Path.home())
    folder = base / "BallcarPDF" / "signatures"

    # เคยใช้ชื่อ PdfTool ตอนโปรแกรมยังไม่มีชื่อ — ย้ายของเดิมมาให้ ลายเซ็นจะได้ไม่หาย
    legacy = base / "PdfTool" / "signatures"
    if legacy.exists() and not folder.exists():
        folder.parent.mkdir(parents=True, exist_ok=True)
        legacy.rename(folder)

    folder.mkdir(parents=True, exist_ok=True)
    return folder


def safe_name(name: str) -> str:
    """ตัดอักขระที่ใช้เป็นชื่อไฟล์ไม่ได้ออก"""
    cleaned = re.sub(r'[<>:"/\\|?*]', "", name).strip().rstrip(".")
    return cleaned or "ลายเซ็น"


def list_signatures() -> list[Path]:
    """ลายเซ็นทั้งหมดที่บันทึกไว้ เรียงตามชื่อ"""
    return sorted(library_dir().glob("*.png"), key=lambda p: p.stem.lower())


def save_signature(prepared_png: str | Path, name: str) -> Path:
    """เก็บรูปที่เตรียมไว้แล้ว (ลบพื้นหลังแล้ว) เข้าคลัง

    ถ้าชื่อซ้ำจะเติมเลขต่อท้ายให้ ไม่เขียนทับของเดิม
    """
    target = library_dir() / f"{safe_name(name)}.png"
    counter = 2
    while target.exists():
        target = library_dir() / f"{safe_name(name)} ({counter}).png"
        counter += 1
    shutil.copyfile(prepared_png, target)
    return target


def delete_signature(path: str | Path) -> None:
    path = Path(path)
    if path.parent.resolve() != library_dir().resolve():
        raise ValueError("ลบได้เฉพาะไฟล์ในคลังลายเซ็นเท่านั้น")
    path.unlink(missing_ok=True)


def rename_signature(path: str | Path, new_name: str) -> Path:
    path = Path(path)
    target = path.with_name(f"{safe_name(new_name)}.png")
    if target != path:
        if target.exists():
            raise ValueError(f"มีลายเซ็นชื่อ “{target.stem}” อยู่แล้ว")
        path.rename(target)
    return target
