"""ไฟล์ที่เปิดล่าสุด (2.0) — เก็บใน settings.json คีย์ recent_files (ใหม่สุดอยู่หน้า)"""
from __future__ import annotations

import os
from pathlib import Path

from . import i18n

MAX_ITEMS = 12
_KEY = "recent_files"


def _norm(path: str | os.PathLike) -> str:
    return str(Path(path).resolve())


def add(path: str | os.PathLike) -> None:
    """เปิดไฟล์สำเร็จแล้วเรียก — ไฟล์เดิมย้ายขึ้นบนสุด ไม่ซ้ำ"""
    key = _norm(path)
    items = [p for p in i18n.get_setting(_KEY, []) or [] if os.path.normcase(p) != os.path.normcase(key)]
    i18n.set_setting(_KEY, [key, *items][:MAX_ITEMS])


def remove(path: str | os.PathLike) -> None:
    key = os.path.normcase(_norm(path))
    i18n.set_setting(_KEY, [p for p in i18n.get_setting(_KEY, []) or []
                            if os.path.normcase(p) != key])


def clear() -> None:
    i18n.set_setting(_KEY, [])


def items() -> list[Path]:
    """รายการที่ยังมีไฟล์อยู่จริง (ไฟล์ที่ถูกลบ/ย้ายไปแล้วไม่แสดง แต่ไม่ลบออกจากรายการ
    เผื่อเป็นไดรฟ์เครือข่าย/USB ที่ยังไม่ได้เสียบ)"""
    found = []
    for p in i18n.get_setting(_KEY, []) or []:
        try:
            if Path(p).is_file():
                found.append(Path(p))
        except OSError:
            pass
    return found


# ---------- ปักหมุด (2.3) — ไฟล์ที่ใช้ประจำ อยู่บนสุดของหน้าแรกเสมอ ไม่หลุดตามเวลา ----------

_PIN_KEY = "pinned_files"


def pinned() -> list[Path]:
    """ไฟล์ที่ปักหมุดไว้และยังมีอยู่จริง (เรียงตามลำดับที่ปัก)"""
    found = []
    for p in i18n.get_setting(_PIN_KEY, []) or []:
        try:
            if Path(p).is_file():
                found.append(Path(p))
        except OSError:
            pass
    return found


def is_pinned(path: str | os.PathLike) -> bool:
    key = os.path.normcase(_norm(path))
    return any(os.path.normcase(p) == key for p in i18n.get_setting(_PIN_KEY, []) or [])


def pin(path: str | os.PathLike) -> None:
    if not is_pinned(path):
        i18n.set_setting(_PIN_KEY, [*(i18n.get_setting(_PIN_KEY, []) or []), _norm(path)])


def unpin(path: str | os.PathLike) -> None:
    key = os.path.normcase(_norm(path))
    i18n.set_setting(_PIN_KEY, [p for p in i18n.get_setting(_PIN_KEY, []) or []
                                if os.path.normcase(p) != key])
