"""เปรียบเทียบเอกสาร (2.3) — สร้าง PDF รายงาน: หน้าเดิม | หน้าใหม่ วางคู่กัน
คำที่หายไปไฮไลต์แดงฝั่งเดิม คำที่เพิ่ม/เปลี่ยนไฮไลต์เขียวฝั่งใหม่

ใช้ข้อความในไฟล์ (คำทีละคำพร้อมตำแหน่ง) เทียบด้วย difflib — ไฟล์สแกนต้อง OCR ก่อน
ภาษาไทยไม่มีเว้นวรรค "คำ" จึงเป็นช่วงข้อความระหว่างช่องว่าง: แก้ตัวเดียวช่วงนั้นถูกไฮไลต์ทั้งช่วง
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

import fitz

from .pdfops import find_thai_font

RED = (0.92, 0.25, 0.25)
GREEN = (0.15, 0.65, 0.30)
GAP = 24          # ช่องว่างระหว่างหน้าเดิมกับหน้าใหม่ (จุด)
HEADER = 46       # แถบหัวกระดาษบอกชื่อไฟล์/ผลต่าง


@dataclass
class PageDiff:
    removed: list          # กรอบคำที่หายไป (บนหน้าเดิม)
    added: list            # กรอบคำที่เพิ่ม/เปลี่ยน (บนหน้าใหม่)
    changes: int = 0       # จำนวนจุดที่ต่าง (คำที่ถูกแทนที่ = 1 จุด ไม่ใช่ลบ 1 + เพิ่ม 1)


def _words(page: fitz.Page) -> list[tuple[str, fitz.Rect]]:
    words = page.get_text("words", sort=True)
    out = [(w[4], fitz.Rect(w[:4])) for w in words if w[4].strip()]
    if page.rotation:
        out = [(text, rect * page.rotation_matrix) for text, rect in out]
    return out


def diff_pages(old: fitz.Page | None, new: fitz.Page | None) -> PageDiff:
    a = _words(old) if old is not None else []
    b = _words(new) if new is not None else []
    matcher = difflib.SequenceMatcher(a=[w for w, _ in a], b=[w for w, _ in b], autojunk=False)
    removed, added, changes = [], [], 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        changes += tag != "equal"
        if tag in ("delete", "replace"):
            removed += [r for _, r in a[i1:i2]]
        if tag in ("insert", "replace"):
            added += [r for _, r in b[j1:j2]]
    return PageDiff(removed, added, changes)


def compare_files(old_path: str | Path, new_path: str | Path, target: str | Path,
                  labels: dict | None = None, progress=None) -> tuple[Path, int]:
    """สร้างรายงานเปรียบเทียบ คืน (ไฟล์รายงาน, จำนวนจุดที่ต่างทั้งหมด)

    labels = ข้อความหัวกระดาษ {"old": "เดิม", "new": "ใหม่", "changes": "ต่าง {n} จุด",
    "same": "เหมือนกัน", "missing": "(ไม่มีหน้านี้)"} — ส่งมาจาก UI ตามภาษาที่ใช้
    """
    labels = labels or {}
    font = find_thai_font()
    total = 0
    with fitz.open(str(old_path)) as old_doc, fitz.open(str(new_path)) as new_doc:
        out = fitz.open()
        pages = max(old_doc.page_count, new_doc.page_count)
        for i in range(pages):
            if progress:
                progress(i + 1, pages)
            old = old_doc[i] if i < old_doc.page_count else None
            new = new_doc[i] if i < new_doc.page_count else None
            diff = diff_pages(old, new)
            total += diff.changes
            ref = (old or new).rect
            width = ref.width * 2 + GAP
            height = max((old or new).rect.height, (new or old).rect.height) + HEADER
            page = out.new_page(width=width, height=height)
            left = fitz.Rect(0, HEADER, ref.width, HEADER + (old.rect.height if old else ref.height))
            right_w = new.rect.width if new else ref.width
            right = fitz.Rect(ref.width + GAP, HEADER, ref.width + GAP + right_w,
                              HEADER + (new.rect.height if new else ref.height))
            for doc, idx, area, present in ((old_doc, i, left, old), (new_doc, i, right, new)):
                if present is not None:
                    page.show_pdf_page(area, doc, idx)
                else:
                    page.draw_rect(area, color=(0.7, 0.7, 0.7), fill=(0.95, 0.95, 0.95))
                    _text(page, fitz.Point(area.x0 + 20, area.y0 + 40),
                          labels.get("missing", "(no page)"), font, 14, (0.4, 0.4, 0.4))
            page.draw_rect(left, color=(0.6, 0.6, 0.6), width=0.6)
            page.draw_rect(right, color=(0.6, 0.6, 0.6), width=0.6)
            for rects, area, color in ((diff.removed, left, RED), (diff.added, right, GREEN)):
                for r in rects:
                    box = fitz.Rect(r.x0 + area.x0 - 1, r.y0 + area.y0 - 1,
                                    r.x1 + area.x0 + 1, r.y1 + area.y0 + 1)
                    page.draw_rect(box, color=color, fill=color, fill_opacity=0.28,
                                   stroke_opacity=0.9, width=0.8)
            status = (labels.get("changes", "{n} changes").format(n=diff.changes)
                      if diff.changes else labels.get("same", "identical"))
            _text(page, fitz.Point(8, 20), f"{labels.get('old', 'Old')}: {Path(old_path).name}",
                  font, 11, RED)
            _text(page, fitz.Point(ref.width + GAP + 8, 20),
                  f"{labels.get('new', 'New')}: {Path(new_path).name}", font, 11, GREEN)
            _text(page, fitz.Point(8, 38), f"{labels.get('page', 'Page')} {i + 1} · {status}",
                  font, 10, (0.25, 0.25, 0.25))
        out.save(str(target), garbage=3, deflate=True)
        out.close()
    return Path(target), total


def _text(page: fitz.Page, at: fitz.Point, text: str, font: str | None, size: float, color) -> None:
    if font:
        page.insert_text(at, text, fontsize=size, fontfile=font, fontname="thai", color=color)
    else:
        page.insert_text(at, text, fontsize=size, color=color)
