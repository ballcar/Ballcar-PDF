"""ไอคอนชุดเดียวกันทั้งโปรแกรม (2.0) — Lucide (ISC License, ดู app/icons/LICENSE)

ไฟล์ SVG อยู่ใน app/icons/<ชื่อ>.svg ใช้สี currentColor จึงระบายสีได้:
    icons.icon("folder-open")            สีประจำไอคอน (COLORS) หรือสีตัวหนังสือถ้าเลือกแบบขาวดำ
    icons.icon("trash-2", "#d33")        สีที่กำหนดเอง
ธีมเปลี่ยนแล้วต้องสร้างไอคอนใหม่ (หน้าต่างหลักสร้างเมนู/แถบเครื่องมือใหม่ให้)
ไม่มีไฟล์ = คืน QIcon ว่าง (โปรแกรมทำงานต่อได้ แค่ไม่มีรูป)
"""
from __future__ import annotations

import sys
from pathlib import Path

_CACHE: dict[tuple[str, str], object] = {}
_color = "#1f2328"        # สีตัวหนังสือของธีม (ใช้ตอนเลือกไอคอนขาวดำ / ไอคอนที่ไม่มีสีประจำ)
_dark = False
_colored = True

# สีประจำไอคอน (ธีมสว่าง) — จัดตามความหมาย ให้กวาดตาหาเจอเร็ว
# ธีมมืดจะผสมขาวให้สว่างขึ้นอัตโนมัติ (ดู _for_theme)
COLORS = {
    # ไฟล์
    "folder-open": "#e8a317", "save": "#2f6fde", "save-all": "#2f6fde", "printer": "#5b6b7f",
    "log-out": "#e5484d",
    # ย้อน/ทำซ้ำ, นำทาง, ซูม, มุมมอง
    "undo-2": "#7c4dff", "redo-2": "#7c4dff",
    "chevron-left": "#0f9ba8", "chevron-right": "#0f9ba8",
    "zoom-in": "#0f9ba8", "zoom-out": "#0f9ba8", "move-horizontal": "#0f9ba8",
    "rectangle-vertical": "#0f9ba8", "maximize": "#0f9ba8", "minimize": "#0f9ba8", "layout-grid": "#0f9ba8", "sticky-note": "#e8a317", "message-square": "#e8a317",
    "search": "#2f6fde", "circle-x": "#e5484d",
    # แก้ไขเนื้อหา
    "type": "#2f6fde", "pencil-line": "#f08c00", "highlighter": "#d4a000", "pen-tool": "#7c4dff",
    "eraser": "#e5484d", "signature": "#1f5fbf", "image-plus": "#1f9d55",
    "clipboard-list": "#0f9ba8", "droplet": "#2f9bde", "image": "#1f9d55",
    # จัดการหน้า
    "file-plus": "#1f9d55", "file-input": "#2f6fde", "trash-2": "#e5484d",
    "arrow-up": "#5b6b7f", "arrow-down": "#5b6b7f",
    "rotate-ccw": "#f08c00", "rotate-cw": "#f08c00", "refresh-ccw": "#f08c00",
    "crop": "#7c4dff", "list-ordered": "#0f9ba8",
    # รวม / แยก / บีบอัด
    "merge": "#1f9d55", "scissors": "#e5484d", "minimize-2": "#f08c00", "layers": "#7c4dff",
    # แปลงไฟล์ (Word น้ำเงิน / Excel เขียว ตามโปรแกรมจริง)
    "file-output": "#2b579a", "sheet": "#217346", "scan-text": "#0f9ba8",
    "image-down": "#f08c00", "file-text": "#5b6b7f", "images": "#1f9d55",
    # อื่นๆ
    "lock": "#d4a000", "bot": "#7c4dff", "download": "#1f9d55", "globe": "#2f6fde",
    "info": "#2f6fde", "align-left": "#5b6b7f", "bookmark": "#e5484d",
    "panel-left": "#5b6b7f", "palette": "#f08c00",
}


def icons_dir() -> Path:
    # ตอนแพ็กเป็น .exe ไฟล์อยู่ใน sys._MEIPASS/app/icons (build-exe.ps1 --add-data)
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "app" / "icons"


def set_color(color: str, dark: bool = False, colored: bool = True) -> None:
    """ธีมเรียกตอน apply: สีตัวหนังสือ, ธีมมืดไหม, ใช้ไอคอนสีหรือขาวดำ"""
    global _color, _dark, _colored
    if (color, dark, colored) != (_color, _dark, _colored):
        _color, _dark, _colored = color, dark, colored
        _CACHE.clear()


def _for_theme(color: str) -> str:
    """ธีมมืด: ผสมขาว 35% ให้สีสว่างพอเห็นชัดบนพื้นเข้ม"""
    if not _dark:
        return color
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(c + (255 - c) * 0.35):02x}" for c in (r, g, b))


def color_of(name: str) -> str:
    """สีที่ไอคอนนี้จะถูกระบาย (ตามธีมและแบบสี/ขาวดำที่เลือก)"""
    if _colored and name in COLORS:
        return _for_theme(COLORS[name])
    return _color


def available(name: str) -> bool:
    return (icons_dir() / f"{name}.svg").is_file()


def icon(name: str, color: str | None = None, size: int = 48):
    """QIcon จาก SVG ของ Lucide ระบายด้วยสีที่ต้องการ (วาดที่ 48px คมทั้งเมนูและแถบเครื่องมือ)"""
    from PySide6.QtCore import QByteArray, Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    color = color or color_of(name)
    key = (name, color)
    if key in _CACHE:
        return _CACHE[key]
    path = icons_dir() / f"{name}.svg"
    if not path.is_file():
        return QIcon()
    svg = path.read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    result = QIcon(pixmap)
    _CACHE[key] = result
    return result
