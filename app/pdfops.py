"""ฟังก์ชันจัดการ PDF ทั้งหมด — แยกจาก UI เพื่อให้เทสต์/เรียกใช้ซ้ำได้"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

UNDO_LIMIT = 20  # จำนวนขั้นที่ย้อนกลับได้ (เก็บทั้งเอกสารต่อขั้น จึงไม่เก็บเยอะ)

# ฟอนต์ที่รองรับภาษาไทย — ไล่หาตามลำดับ (ฟอนต์ built-in ของ PDF ไม่มีสระ/วรรณยุกต์ไทย)
THAI_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\LeelawUI.ttf",
    r"C:\Windows\Fonts\leelawad.ttf",
    r"C:\Windows\Fonts\tahoma.ttf",
    r"C:\Windows\Fonts\angsana.ttc",
]


# OCR ใช้เอนจินที่ฝังมาใน PyMuPDF อยู่แล้ว — ต้องการแค่ "ไฟล์ภาษา" (.traineddata)
# ไม่ต้องติดตั้ง Tesseract แยก ไม่ต้องมี tesseract.exe หรือ DLL
# จึงแถมไฟล์ภาษาไทย/อังกฤษไปกับตัวติดตั้งเลย เครื่องที่ออกเน็ตไม่ได้ก็ใช้ OCR ได้ทันที
TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR",
    r"C:\Program Files (x86)\Tesseract-OCR",
]


def bundled_tessdata() -> Path | None:
    """โฟลเดอร์ไฟล์ภาษาที่แถมมากับโปรแกรม (ติดตั้งพร้อมกัน ใช้ได้แม้ไม่มีอินเทอร์เน็ต)"""
    bases: list[Path] = []
    if getattr(sys, "frozen", False):
        bases.append(Path(sys.executable).parent)        # โฟลเดอร์โปรแกรมที่ติดตั้ง (onedir)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bases.append(Path(meipass))                  # เผื่อกลับไป build แบบ onefile
    bases.append(Path(__file__).resolve().parent.parent)  # ตอนรันจากซอร์ส (โหมดพัฒนา)
    for base in bases:
        for sub in ("tessdata", Path("_internal") / "tessdata"):
            folder = base / sub
            if folder.is_dir() and any(folder.glob("*.traineddata")):
                return folder
    return None


def tessdata_dir() -> str | None:
    """โฟลเดอร์ไฟล์ภาษาที่จะใช้ทำ OCR

    ลำดับ: ที่แถมมากับโปรแกรม -> ที่ผู้ใช้กำหนดเอง -> Tesseract ที่ลงไว้ในเครื่อง
    """
    found = bundled_tessdata()
    if found:
        return str(found)
    env = os.environ.get("TESSDATA_DIR") or os.environ.get("TESSERACT_DIR")
    candidates = ([env] if env else []) + TESSERACT_CANDIDATES
    for candidate in candidates:
        if not candidate:
            continue
        base = Path(candidate)
        # รับทั้งกรณีชี้มาที่ tessdata ตรงๆ และชี้มาที่โฟลเดอร์ที่ติดตั้ง Tesseract
        for folder in (base, base / "tessdata"):
            if folder.is_dir() and any(folder.glob("*.traineddata")):
                return str(folder)
    return None


def tesseract_dir() -> Path | None:
    """โฟลเดอร์ที่ใช้ทำ OCR ได้ (None ถ้าไม่มีไฟล์ภาษาเลย) — เก็บชื่อเดิมไว้เพื่อความเข้ากันได้"""
    folder = tessdata_dir()
    return Path(folder) if folder else None


def ocr_languages() -> list[str]:
    """ภาษาที่มีให้ใช้ (ดูจากไฟล์ .traineddata)"""
    folder = tessdata_dir()
    if not folder:
        return []
    return sorted(p.stem for p in Path(folder).glob("*.traineddata"))


def ensure_tesseract() -> None:
    """เช็คว่าพร้อมทำ OCR ไหม ถ้าไม่พร้อมให้ error ที่อธิบายวิธีแก้"""
    folder = tessdata_dir()
    if not folder:
        raise RuntimeError(
            "ไม่พบไฟล์ภาษาสำหรับ OCR ในเครื่องนี้\n\n"
            "ปกติไฟล์ภาษาจะถูกติดตั้งมาพร้อมโปรแกรมอยู่แล้ว\n"
            "ถ้าขึ้นข้อความนี้ ให้ติดตั้งโปรแกรมใหม่อีกครั้ง\n\n"
            "หรือถ้ามีไฟล์ภาษาอยู่ที่อื่น ให้ตั้งตัวแปรระบบ TESSDATA_DIR ชี้ไปที่โฟลเดอร์นั้น"
        )
    langs = ocr_languages()
    if "tha" not in langs:
        raise RuntimeError(
            "ยังไม่มีชุดภาษาไทยสำหรับ OCR\n\n"
            f"ภาษาที่พบตอนนี้: {', '.join(langs) or '(ไม่มี)'}\n"
            f"โฟลเดอร์ไฟล์ภาษา: {folder}\n\n"
            "นำไฟล์ tha.traineddata ไปวางในโฟลเดอร์ข้างบน แล้วเปิดโปรแกรมใหม่"
        )


def find_thai_font() -> str | None:
    """คืนพาธฟอนต์ไทยตัวแรกที่มีในเครื่อง (None ถ้าไม่เจอเลย)"""
    for candidate in THAI_FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


# คลังฟอนต์ให้ผู้ใช้เลือกตอนเพิ่ม/แก้ข้อความ
# (key, ชื่อแสดง, ไฟล์ปกติ, ไฟล์ตัวหนา, รองรับไทย)
_FONT_DEFS = [
    ("sarabun", "TH Sarabun New", ["THSarabunNew.ttf", "THSarabun.ttf"],
     ["THSarabunNew Bold.ttf", "THSarabunNewBold.ttf", "THSarabun Bold.ttf"], True),
    ("angsana", "Angsana New", ["angsa.ttf", "angsana.ttc"], ["angsab.ttf"], True),
    ("cordia", "Cordia New", ["cordia.ttf"], ["cordiab.ttf"], True),
    ("browallia", "Browallia New", ["browa.ttf"], ["browab.ttf"], True),
    ("tahoma", "Tahoma", ["tahoma.ttf"], ["tahomabd.ttf"], True),
    ("leelawadee", "Leelawadee UI", ["LeelawUI.ttf"], ["LeelawUIb.ttf"], True),
    ("arial", "Arial", ["arial.ttf"], ["arialbd.ttf"], False),
    ("times", "Times New Roman", ["times.ttf"], ["timesbd.ttf"], False),
    ("cour", "Courier New", ["cour.ttf"], ["courbd.ttf"], False),
]

_FONTS_DIR = Path(r"C:\Windows\Fonts")
_font_cache: list[dict] | None = None


def _find_font_file(names: list[str]) -> str | None:
    for name in names:
        p = _FONTS_DIR / name
        if p.exists():
            return str(p)
    return None


def available_fonts() -> list[dict]:
    """ฟอนต์ที่เลือกได้จริงในเครื่องนี้ — คืน list ของ {key, name, regular, bold, thai}"""
    global _font_cache
    if _font_cache is not None:
        return _font_cache
    result = []
    for key, name, reg, bold, thai in _FONT_DEFS:
        regular = _find_font_file(reg)
        if not regular:
            continue
        result.append({
            "key": key, "name": name, "regular": regular,
            "bold": _find_font_file(bold), "thai": thai,
        })
    # เผื่อไม่เจอฟอนต์ไทยในรายการเลย ใช้ตัวที่ find_thai_font หามาได้
    if not any(f["thai"] for f in result):
        thai_fb = find_thai_font()
        if thai_fb:
            result.insert(0, {"key": "thai", "name": "ฟอนต์ไทย (ในเครื่อง)",
                              "regular": thai_fb, "bold": None, "thai": True})
    _font_cache = result
    return result


def font_by_key(key: str) -> dict | None:
    for f in available_fonts():
        if f["key"] == key:
            return f
    return None


def default_font_key() -> str:
    """ฟอนต์เริ่มต้น — เลือกฟอนต์ไทยตัวแรกที่มี (เอกสารส่วนใหญ่เป็นไทย)"""
    for f in available_fonts():
        if f["thai"]:
            return f["key"]
    fonts = available_fonts()
    return fonts[0]["key"] if fonts else "sarabun"


def resolve_font(key: str, bold: bool, text: str) -> tuple[str, str | None]:
    """คืน (ชื่อฟอนต์สำหรับ PyMuPDF, พาธไฟล์) จาก key ที่เลือก
    ถ้าข้อความมีภาษาไทยแต่ฟอนต์ที่เลือกไม่รองรับไทย จะสลับไปฟอนต์ไทยให้ ไม่ให้ตัวหนังสือหาย
    """
    entry = font_by_key(key)
    if entry is None:
        # ไม่รู้จัก -> ใช้พฤติกรรมเดิม
        if _has_thai(text):
            return "thaifb", find_thai_font()
        return "helv", None
    if _has_thai(text) and not entry["thai"]:
        thai_fb = font_by_key(default_font_key())
        if thai_fb:
            entry = thai_fb
    fontfile = entry["bold"] if (bold and entry["bold"]) else entry["regular"]
    tag = f"{entry['key']}{'B' if (bold and entry['bold']) else ''}"
    return tag, fontfile


# เกณฑ์ตัดพื้นหลัง: สว่างกว่า WHITE_CUT = โปร่งใสสนิท, ระหว่าง SOFT_CUT..WHITE_CUT = ไล่โปร่ง
WHITE_CUT = 242
SOFT_CUT = 200


def _strip_white_background(image):
    """ทำพื้นหลังขาวของลายเซ็นให้โปร่งใส (เก็บขอบเส้นแบบไล่ระดับไว้ ไม่ให้หยัก)

    ถ้ารูปมีความโปร่งใสมาแต่เดิมอยู่แล้ว (เช่น PNG ที่ไล่ขอบมาดี) จะไม่ไปยุ่ง
    """
    from PIL import Image

    alpha = image.getchannel("A")
    if alpha.getextrema()[0] < 250:
        return image  # มี alpha อยู่แล้ว ปล่อยไว้

    pixels = image.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            brightness = min(r, g, b)
            if brightness >= WHITE_CUT:
                pixels[x, y] = (r, g, b, 0)
            elif brightness > SOFT_CUT:
                # ขอบเส้นที่จางลง -> ไล่ความโปร่งตามความสว่าง
                ratio = (WHITE_CUT - brightness) / (WHITE_CUT - SOFT_CUT)
                pixels[x, y] = (r, g, b, int(a * ratio))
    return image


def _int_to_roman(n: int) -> str:
    if n <= 0:
        return str(n)
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
             (90, "XC"), (50, "L"), (40, "XL"), (10, "X"),
             (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = []
    for value, sym in table:
        while n >= value:
            out.append(sym)
            n -= value
    return "".join(out)


def _format_numeral(n: int, numeral: str) -> str:
    """แปลงเลขหน้าเป็นรูปแบบที่ต้องการ: arabic / roman / roman-lower"""
    if numeral == "roman":
        return _int_to_roman(n)
    if numeral == "roman-lower":
        return _int_to_roman(n).lower()
    return str(n)


def _has_thai(text: str) -> bool:
    return any("฀" <= ch <= "๿" for ch in text)


@dataclass
class Stamp:
    """ลายเซ็น/ตราประทับที่ยังแก้ไขได้ — ยังไม่ฝังลงไฟล์จนกว่าจะกดบันทึก"""
    page: int
    rect: fitz.Rect
    image_path: str

    def copy(self) -> "Stamp":
        return Stamp(self.page, fitz.Rect(self.rect), self.image_path)


@dataclass
class TextBox:
    """ข้อความที่เพิ่มเข้าไป — ยังแก้ไข/ย้าย/ปรับขนาด/ลบได้จนกว่าจะบันทึก"""
    page: int
    rect: fitz.Rect
    text: str
    font_size: float = 14.0
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    font: str = ""            # key ของฟอนต์ (ว่าง = auto: ไทยใช้ฟอนต์ไทย, อังกฤษใช้ helv)
    bold: bool = False

    def copy(self) -> "TextBox":
        return TextBox(self.page, fitz.Rect(self.rect), self.text, self.font_size,
                       self.color, self.font, self.bold)


def draw_textbox(page: fitz.Page, box: "TextBox") -> None:
    """วาดข้อความลงในกล่องบนหน้า — ใช้ทั้งตอนฝังลงไฟล์, พิมพ์, ออกรูป และตัวอย่างบนจอ

    ต้องใช้ตัวเดียวกันทุกที่ ไม่งั้นตัวอย่างบนจอกับผลจริงจะตัดบรรทัดไม่ตรงกัน
    """
    if not box.text.strip():
        return
    if box.font:
        # ผู้ใช้เลือกฟอนต์เอง
        fontname, fontfile = resolve_font(box.font, box.bold, box.text)
        if fontfile:
            page.insert_font(fontname=fontname, fontfile=fontfile)
        else:
            fontname = "helv"     # base-14 (อังกฤษ)
    else:
        # auto: อังกฤษ = Helvetica, ไทย = ฟอนต์ไทยในเครื่อง
        fontname = "helv"
        fontfile = None
        if _has_thai(box.text):
            fontfile = find_thai_font()
            if not fontfile:
                raise RuntimeError("ไม่พบฟอนต์ภาษาไทยในเครื่อง — ข้อความภาษาไทยจะแสดงไม่ถูกต้อง")
            fontname = "thai"
            page.insert_font(fontname=fontname, fontfile=fontfile)

    # หน้าที่ถูกหมุนไว้ (ไฟล์สแกนเจอบ่อย) ต้องบอก insert_textbox ให้เขียนตัวอักษรตามมุมนั้นด้วย
    # ไม่งั้นกรอบที่ "กว้าง" ในมุมมองจริง จะกลายเป็นกรอบ "สูงแคบ" ในพิกัดดิบ
    # ข้อความเลยถูกหั่นเป็นท่อนเรียงลงมาแนวตั้ง เช่น 25/08/2026 -> 25 / 08 / 202 / 6
    rot = (page.rotation or 0) % 360
    if rot not in (0, 90, 180, 270):
        rot = 0
    target = box.rect * page.derotation_matrix if page.rotation else box.rect
    # insert_textbox จะไม่วาดอะไรเลย (คืนค่าลบ) ถ้าข้อความไม่พอดีกล่อง
    # จึงลองขยายกล่องตามแนวที่บรรทัดเรียงตัว (แนวนี้ต่างกันตามมุมหมุนของหน้า)
    rect = fitz.Rect(target)
    for _ in range(6):
        leftover = page.insert_textbox(
            rect, box.text,
            fontname=fontname, fontfile=fontfile, fontsize=box.font_size,
            color=box.color, align=fitz.TEXT_ALIGN_LEFT, rotate=rot,
        )
        if leftover >= 0:
            return
        grow = box.font_size * 1.5
        if rot in (90, 270):      # หน้าตะแคง บรรทัดเรียงตามแนวนอนของพิกัดดิบ
            rect = fitz.Rect(rect.x0, rect.y0, rect.x1 + grow, rect.y1)
        else:
            rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + grow)
    # ยังไม่ลง (เช่นข้อความยาวมาก) — วางเป็นบรรทัดเดียว กันข้อความหาย
    anchor = {
        0: (target.x0, target.y0 + box.font_size),
        90: (target.x0 + box.font_size, target.y1),
        180: (target.x1, target.y1 - box.font_size),
        270: (target.x1 - box.font_size, target.y0),
    }[rot]
    page.insert_text(
        anchor, box.text.replace(chr(10), " "), rotate=rot,
        fontname=fontname, fontfile=fontfile, fontsize=box.font_size, color=box.color,
    )


def compress_pdf(doc: fitz.Document, target: str | Path,
                 image_quality: int = 60, downsample_dpi: int = 120) -> int:
    """บีบอัดเอกสารลง target — คืนขนาดไฟล์ใหม่ (bytes)"""
    work = fitz.open("pdf", doc.tobytes())     # สำเนา ไม่แตะตัวจริง
    try:
        try:
            work.rewrite_images(dpi_threshold=downsample_dpi + 30, dpi_target=downsample_dpi,
                                quality=image_quality, lossy=True, lossless=True)
        except Exception:
            pass   # ไม่มีรูปหรือ rewrite ไม่ได้ ก็ข้ามไปบีบด้วยวิธีอื่น
        try:
            work.subset_fonts()
        except Exception:
            pass
        work.save(str(target), garbage=4, deflate=True, deflate_images=True,
                  deflate_fonts=True, clean=True)
    finally:
        work.close()
    return Path(target).stat().st_size


def render_textbox_bitmap(box: "TextBox", zoom: float, overflow: bool = True) -> fitz.Pixmap:
    """วาดตัวอย่างข้อความด้วยเอนจินเดียวกับตอนฝังลงไฟล์ (WYSIWYG)

    overflow=True: เผื่อความสูงไว้ให้เห็นข้อความที่ล้นออกนอกกล่อง (ใช้ตอนแสดงบนหน้า)
    overflow=False: สูงเท่ากล่องเป๊ะ (ใช้กับ overlay ตอนลากย้าย/ปรับขนาดที่ยืดรูปตามกรอบ
        — ไม่งั้นภาพที่เผื่อไว้จะถูกบีบจนตัวอักษรแบนผิดรูป)
    """
    width = max(1.0, box.rect.width)
    box_height = max(1.0, box.rect.height)
    # เผื่อความสูงเท่าที่ draw_textbox ยอมขยายกล่องลงล่าง จะได้เห็นส่วนที่ล้นด้วย
    height = box_height + (box.font_size * 1.5 * 6 if overflow else 0)
    tmp = fitz.open()
    page = tmp.new_page(width=width, height=height)
    local = TextBox(page=0, rect=fitz.Rect(0, 0, width, box_height),
                    text=box.text, font_size=box.font_size, color=box.color,
                    font=box.font, bold=box.bold)
    draw_textbox(page, local)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=True)
    tmp.close()
    return pix


@dataclass
class Eraser:
    """ยางลบ/ปิดทับ — สี่เหลี่ยมทึบทับเนื้อหาเดิม (ใช้กับไฟล์สแกนที่แก้ข้อความไม่ได้)"""
    page: int
    rect: fitz.Rect
    color: tuple[float, float, float] = (1.0, 1.0, 1.0)

    def copy(self) -> "Eraser":
        return Eraser(self.page, fitz.Rect(self.rect), self.color)


@dataclass
class Annotation:
    """รูปวาด/มาร์กอัป — ปากกา(draw)/เส้น(line)/ลูกศร(arrow)/สี่เหลี่ยม(rect)/วงกลม(circle)

    points เก็บพิกัดบนหน้า (จุดเริ่ม-จุดจบสำหรับรูปทรง, หลายจุดสำหรับปากกา)
    """
    page: int
    kind: str
    points: list                       # [(x, y), ...]
    color: tuple[float, float, float] = (0.9, 0.1, 0.1)
    width: float = 2.0

    def copy(self) -> "Annotation":
        return Annotation(self.page, self.kind, [tuple(p) for p in self.points],
                          self.color, self.width)


def sample_background_color(page: fitz.Page, rect: fitz.Rect) -> tuple[float, float, float]:
    """ดูดสีพื้นหลังรอบๆ กรอบที่จะลบ — ให้แผ่นปิดกลืนกับกระดาษสแกน (ที่มักไม่ขาวสนิท)"""
    pad = 6
    outer = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad) & page.rect
    if outer.is_empty:
        return (1.0, 1.0, 1.0)
    try:
        pix = page.get_pixmap(clip=outer, colorspace=fitz.csRGB)
    except Exception:
        return (1.0, 1.0, 1.0)
    if pix.width < 3 or pix.height < 3:
        return (1.0, 1.0, 1.0)
    # เก็บสีเฉพาะขอบนอก (ไม่เอาตรงกลางที่เป็นตัวหนังสือที่จะลบ)
    edge = []
    for x in range(pix.width):
        edge.append(pix.pixel(x, 0))
        edge.append(pix.pixel(x, pix.height - 1))
    for y in range(pix.height):
        edge.append(pix.pixel(0, y))
        edge.append(pix.pixel(pix.width - 1, y))
    if not edge:
        return (1.0, 1.0, 1.0)
    # ใช้ค่ากลาง (median) กันตัวหนังสือสีเข้มที่ติดขอบมาดึงค่าเพี้ยน
    edge.sort(key=lambda c: c[0] + c[1] + c[2])
    r, g, b = edge[len(edge) * 3 // 4]      # ค่อนไปทางสว่าง = สีกระดาษ
    return (r / 255, g / 255, b / 255)


def arrowhead_points(start, end, size: float) -> tuple:
    """คืนจุดปลายลูกศร 2 จุด (ปีกซ้าย-ขวา) จากทิศ start->end"""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    head = max(8.0, size * 3.5)
    ang = math.radians(28)
    cos_a, sin_a = math.cos(ang), math.sin(ang)
    # หมุนเวกเตอร์ทิศทางย้อนกลับ ±ang แล้วยืดตาม head
    left = (end[0] - head * (ux * cos_a - uy * sin_a),
            end[1] - head * (uy * cos_a + ux * sin_a))
    right = (end[0] - head * (ux * cos_a + uy * sin_a),
             end[1] - head * (uy * cos_a - ux * sin_a))
    return left, right


def _draw_annotation_pdf(page: fitz.Page, kind: str, pts: list,
                         color: tuple, width: float) -> None:
    """วาดรูปมาร์กอัปลงหน้า PDF จริง (พิกัดแปลงตามมุมหมุนมาแล้ว)"""
    if not pts:
        return
    if kind == "draw":
        if len(pts) >= 2:
            page.draw_polyline([fitz.Point(*p) for p in pts], color=color, width=width)
        return
    a = fitz.Point(*pts[0])
    b = fitz.Point(*pts[-1])
    if kind == "rect":
        page.draw_rect(fitz.Rect(a, b).normalize(), color=color, width=width)
    elif kind == "circle":
        page.draw_oval(fitz.Rect(a, b).normalize(), color=color, width=width)
    elif kind == "line":
        page.draw_line(a, b, color=color, width=width)
    elif kind == "arrow":
        page.draw_line(a, b, color=color, width=width)
        left, right = arrowhead_points((a.x, a.y), (b.x, b.y), width)
        page.draw_line(b, fitz.Point(*left), color=color, width=width)
        page.draw_line(b, fitz.Point(*right), color=color, width=width)


@dataclass
class Watermark:
    """ลายน้ำที่ยังแก้ไขได้ — ปรับข้อความ/ขนาด/ความจาง/องศา/สีได้จนกว่าจะบันทึก"""
    text: str
    indexes: list[int] | None = None          # None = ทุกหน้า
    opacity: float = 0.18
    angle: float = 45.0
    color: tuple[float, float, float] = (0.5, 0.5, 0.5)
    font_size: float | None = None            # None = คำนวณให้พอดีหน้าอัตโนมัติ

    def copy(self) -> "Watermark":
        return Watermark(self.text, None if self.indexes is None else list(self.indexes),
                         self.opacity, self.angle, self.color, self.font_size)

    def applies_to(self, index: int) -> bool:
        return self.indexes is None or index in self.indexes


@dataclass
class SearchHit:
    page: int          # index เริ่มที่ 0
    rect: fitz.Rect    # ตำแหน่งคำที่เจอบนหน้า


def page_words(page: fitz.Page) -> list:
    """คำทั้งหมดบนหน้า พร้อมตำแหน่ง — (x0, y0, x1, y1, คำ, บล็อก, บรรทัด, ลำดับคำ)

    พิกัดที่ได้เป็น "พิกัดที่แสดงจริง" (รวมการหมุนของหน้าแล้ว) จะได้ตรงกับที่ผู้ใช้เห็น
    """
    words = page.get_text("words")
    if page.rotation:
        m = page.rotation_matrix
        rotated = []
        for w in words:
            r = fitz.Rect(w[0], w[1], w[2], w[3]) * m
            rotated.append((r.x0, r.y0, r.x1, r.y1, *w[4:]))
        return rotated
    return words


def _reading_order(words: list) -> list[int]:
    """ลำดับการอ่านของคำ (บล็อก -> บรรทัด -> ลำดับคำ)"""
    return sorted(range(len(words)), key=lambda i: (words[i][5], words[i][6], words[i][7]))


def _nearest_word(words: list, point) -> int:
    """คำที่ใกล้จุดที่คลิกที่สุด (ถ้าคลิกโดนคำไหนก็คืนคำนั้น) — คืน -1 ถ้าไม่มีคำเลย"""
    if not words:
        return -1
    px, py = point
    on_line, others = [], []
    for i, w in enumerate(words):
        x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
        if x0 <= px <= x1 and y0 <= py <= y1:
            return i                       # ชี้โดนคำนั้นพอดี
        dx = 0.0 if x0 <= px <= x1 else min(abs(px - x0), abs(px - x1))
        dy = 0.0 if y0 <= py <= y1 else min(abs(py - y0), abs(py - y1))
        # อยู่ในแนวบรรทัดเดียวกันไหม (ชี้เลยท้ายบรรทัดก็ยังนับว่าบรรทัดนั้น)
        (on_line if y0 <= py <= y1 else others).append((dx, dy, i))
    # บรรทัดที่ชี้อยู่มาก่อนเสมอ ค่อยดูระยะแนวนอน — กันเลือกข้ามไปบรรทัดไกลๆ
    pool = on_line or others
    if not pool:
        return -1
    return min(pool, key=lambda t: (t[1], t[0]))[2]


def select_words_between(words: list, start, end) -> tuple[list, str]:
    """เลือกข้อความจากจุดหนึ่งถึงอีกจุดตามลำดับการอ่าน (แบบลากเลือกใน Adobe)

    คืน (รายการกรอบของคำที่เลือก, ข้อความที่ได้) — ลากทิศไหนก็ได้
    """
    if not words:
        return [], ""
    a, b = _nearest_word(words, start), _nearest_word(words, end)
    if a < 0 or b < 0:
        return [], ""
    order = _reading_order(words)
    pos = {w: p for p, w in enumerate(order)}
    lo, hi = sorted((pos[a], pos[b]))
    chosen = [words[i] for i in order[lo:hi + 1]]
    rects, parts, last_line = [], [], None
    for w in chosen:
        rects.append(fitz.Rect(w[0], w[1], w[2], w[3]))
        line = (w[5], w[6])
        if last_line is not None and line != last_line:
            parts.append("\n")           # ขึ้นบรรทัดใหม่ตามเอกสาร
        elif parts:
            parts.append(" ")
        parts.append(w[4])
        last_line = line
    return rects, "".join(parts)


def merge_line_rects(rects: list, tol: float = 2.0) -> list:
    """รวมกรอบคำที่อยู่บรรทัดเดียวกันเป็นแถบเดียว — ไฮไลต์จะได้ดูเรียบ ไม่เป็นบล็อกๆ"""
    merged: list = []
    for r in sorted(rects, key=lambda x: (round(x.y0, 1), x.x0)):
        if merged:
            last = merged[-1]
            same_line = abs(last.y0 - r.y0) <= tol and abs(last.y1 - r.y1) <= tol
            if same_line and r.x0 - last.x1 < 12:      # ติดกันพอ ถือว่าแถบเดียว
                merged[-1] = fitz.Rect(last.x0, min(last.y0, r.y0),
                                       max(last.x1, r.x1), max(last.y1, r.y1))
                continue
        merged.append(fitz.Rect(r))
    return merged


class PasswordRequired(Exception):
    """ไฟล์ถูกเข้ารหัส ต้องใส่รหัสผ่านก่อนเปิด"""
    def __init__(self, wrong: bool = False):
        super().__init__("ไฟล์นี้มีรหัสผ่าน")
        self.wrong = wrong   # True = ใส่รหัสมาแล้วแต่ผิด


def _swap_file(tmp: Path, target: Path) -> None:
    """เอาไฟล์ชั่วคราวไปแทนไฟล์เดิม — ทนกรณีไฟล์ถูกล็อกชั่วคราว

    บน Windows การ rename ทับมักโดน "Access is denied" เพราะโปรแกรมอื่นเปิดค้างอยู่
    (แอนตี้ไวรัสสแกน, OneDrive/ตัวซิงก์, ตัวอย่างไฟล์ของ Explorer) ซึ่งมักหลุดเองใน 1-2 วินาที
    จึงลองซ้ำสั้นๆ ก่อน แล้วค่อยถอยไปเขียนทับ "เนื้อไฟล์" เดิมแทนการ rename
    (วิธีหลังใช้ได้แม้ rename ไม่ได้ และยังคงสิทธิ์/ตำแหน่งไฟล์เดิมไว้ด้วย)
    """
    last: OSError | None = None
    for delay in (0, 0.3, 0.6, 1.0):
        if delay:
            time.sleep(delay)
        try:
            tmp.replace(target)
            return
        except OSError as exc:
            last = exc
    # rename ไม่ผ่าน — ลองเขียนทับเนื้อไฟล์เดิมตรงๆ
    try:
        data = tmp.read_bytes()
        with open(target, "wb") as f:
            f.write(data)
        tmp.unlink(missing_ok=True)
        return
    except OSError:
        raise last if last else OSError("สลับไฟล์ไม่สำเร็จ")


def repair_pdf(path: str | Path) -> "fitz.Document | None":
    """ซ่อมไฟล์ PDF ที่ตาราง xref เสีย (เปิดได้ 0 หน้า) คืนเอกสารที่ซ่อมแล้ว หรือ None

    ใช้ qpdf (ผ่าน pikepdf) สร้างตาราง xref ใหม่จาก object ที่ยังอยู่ในไฟล์
    ซึ่งกู้ได้แม้ MuPDF เองซ่อมไม่ได้ — เนื้อหาหน้ายังอยู่ในไฟล์ แค่ชี้ไม่ถูก
    """
    try:
        import pikepdf
    except ImportError:
        return None
    try:
        with pikepdf.open(str(path)) as pdf:
            if len(pdf.pages) == 0:
                return None
            out = Path(tempfile.gettempdir()) / f"ballcar-repaired-{abs(hash(str(path)))}.pdf"
            pdf.save(str(out))
        fixed = fitz.open(str(out))
        if fixed.page_count == 0:
            fixed.close()
            return None
        return fixed
    except Exception:
        return None


class PdfDocument:
    """ห่อ fitz.Document ให้ใช้ง่ายขึ้น + จำสถานะว่ามีการแก้ไขค้างอยู่ไหม"""

    def __init__(self, path: str | Path | None = None, password: str | None = None):
        self.path: Path | None = Path(path) if path else None
        self.doc = fitz.open(str(path)) if path else fitz.open()
        # ไฟล์เสียหาย (เปิดได้ 0 หน้า แต่ไฟล์มีข้อมูลอยู่) — ลองซ่อมให้อัตโนมัติ
        # เจอบ่อยกับไฟล์ที่ถูกบันทึกด้วยเวอร์ชัน <= 1.0.62 ซึ่งเขียนทับแบบต่อท้ายจน xref เสีย
        self.repaired_on_open = False
        if path and self.doc.page_count == 0 and Path(path).stat().st_size > 2048:
            recovered = repair_pdf(path)
            if recovered is not None:
                self.doc.close()
                self.doc = recovered
                self.repaired_on_open = True
        # ไฟล์เข้ารหัส — ต้องปลดล็อกด้วยรหัสผ่านก่อนใช้งาน
        self._was_encrypted = bool(self.doc.needs_pass)
        if self.doc.needs_pass:
            if not password or not self.doc.authenticate(password):
                self.doc.close()
                raise PasswordRequired(wrong=bool(password))
        self.dirty = False
        # ประวัติสำหรับ undo/redo — เก็บทั้งเอกสารเป็น bytes ต่อ 1 ขั้น
        self._in_memory = path is None
        self._undo: list[tuple] = []
        self._redo: list[tuple] = []
        # ลายเซ็นที่ยังลอยอยู่ (ย้าย/ย่อขยาย/ลบได้) — ฝังลงไฟล์ตอน save
        self.stamps: list[Stamp] = []
        # ข้อความที่เพิ่ม/แก้ไข ยังลอยอยู่เช่นกัน — ฝังลงไฟล์ตอน save
        self.textboxes: list[TextBox] = []
        # ลายน้ำที่ยังลอยอยู่ (ปรับข้อความ/ขนาด/องศา/สีได้) — ฝังลงไฟล์ตอน save
        self.watermark: Watermark | None = None
        # ยางลบ/แผ่นปิดทับ (ใช้กับไฟล์สแกน) — ฝังลงไฟล์ตอน save
        self.erasers: list[Eraser] = []
        # รูปวาด/มาร์กอัป (ปากกา/เส้น/ลูกศร/สี่เหลี่ยม/วงกลม) — ฝังลงไฟล์ตอน save
        self.annotations: list[Annotation] = []
        # จำนวนหน้าที่ปรับขนาดไม่สำเร็จตอนแทรกครั้งล่าสุด (ใช้แจ้งเตือนผู้ใช้)
        self.fit_failed_pages = 0

    # ---------- ย้ายเลขหน้าของ "ของลอย" ตามการแทรก/ลบ/สลับหน้า ----------

    def _remap_floating(self, mapper) -> None:
        """อัปเดต .page ของของลอยทุกชิ้นด้วย mapper(old_page) -> new_page (None = ถูกลบ)

        ต้องเรียกทุกครั้งที่ลำดับหน้าเปลี่ยน (แทรก/ลบ/ย้าย/เรียงใหม่) ไม่งั้นลายเซ็น
        ข้อความ ยางลบ มาร์กอัป จะไปโผล่ผิดหน้าตอนบันทึก
        """
        for name in ("stamps", "textboxes", "erasers", "annotations"):
            kept = []
            for obj in getattr(self, name):
                new = mapper(obj.page)
                if new is not None:
                    obj.page = new
                    kept.append(obj)
            setattr(self, name, kept)

    def _shift_floating(self, at: int, count: int) -> None:
        """แทรก count หน้าที่ตำแหน่ง at — ของลอยที่อยู่ตั้งแต่ at ลงไปเลื่อนตาม"""
        self._remap_floating(lambda p: p + count if p >= at else p)

    # ---------- undo / redo ----------

    def _snapshot(self) -> tuple:
        return (self.doc.tobytes(), self.dirty,
                [s.copy() for s in self.stamps], [b.copy() for b in self.textboxes],
                self.watermark.copy() if self.watermark else None,
                [e.copy() for e in self.erasers],
                [a.copy() for a in self.annotations])

    def _restore(self, state: tuple) -> None:
        data, dirty, stamps, textboxes, watermark, erasers, annotations = state
        old = self.doc
        self.doc = fitz.open("pdf", data)
        old.close()
        self.dirty = dirty
        self.stamps = [s.copy() for s in stamps]
        self.textboxes = [b.copy() for b in textboxes]
        self.watermark = watermark.copy() if watermark else None
        self.erasers = [e.copy() for e in erasers]
        self.annotations = [a.copy() for a in annotations]
        # เอกสารมาจากหน่วยความจำแล้ว บันทึกทับไฟล์เดิมแบบ incremental ไม่ได้
        self._in_memory = True

    def push_undo(self) -> None:
        """เรียกก่อนแก้ไขทุกครั้ง — เก็บสภาพปัจจุบันไว้ย้อนกลับ"""
        self._undo.append(self._snapshot())
        if len(self._undo) > UNDO_LIMIT:
            self._undo.pop(0)
        self._redo.clear()  # แก้ไขใหม่แล้ว redo เดิมใช้ไม่ได้

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        return True

    # ---------- เปิด/บันทึก ----------

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def close(self) -> None:
        self.doc.close()

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("ยังไม่ได้ระบุที่อยู่ไฟล์สำหรับบันทึก")

        same_file = self.path is not None and target.exists() and target.resolve() == self.path.resolve()

        # ลายเซ็น/ข้อความ/ลายน้ำที่ยังลอยอยู่ ต้องฝังลงเอกสารก่อนบันทึก (ฝังแล้วแก้ไม่ได้อีก)
        if (self.stamps or self.textboxes or self.watermark or self.erasers
                or self.annotations):
            self._flatten_erasers(self.doc)   # ลบก่อน แล้วค่อยวางของทับ
            self._flatten_stamps(self.doc)
            self._flatten_textboxes(self.doc)
            self._flatten_annotations(self.doc)
            self._flatten_watermark(self.doc)
            self.stamps = []
            self.textboxes = []
            self.watermark = None
            self.erasers = []
            self.annotations = []
            # เพิ่งแก้เนื้อหา จึงเขียนทับแบบ incremental ไม่ได้
            if same_file:
                self._in_memory = True

        if same_file:
            # เขียนทับไฟล์เดิม = เขียนไฟล์ชั่วคราวแล้วสลับทับ (เขียนใหม่ทั้งไฟล์)
            #
            # ⚠️ ห้ามใช้ incremental save เด็ดขาด — มันเขียน "ต่อท้าย" ไฟล์เดิม
            # ซึ่งพังเมื่อโครงสร้างหน้าเปลี่ยน (แทรก/ลบ/ย้าย/หมุน/รวมไฟล์)
            # ทำหลายรอบแล้ว xref เสีย เปิดไฟล์ได้ 0 หน้า หรือหน้าขาวหมด (บั๊กจริงถึง 1.0.62)
            self._save_and_swap(target)
        else:
            self.doc.save(str(target), garbage=3, deflate=True)
            self.path = target

        self.dirty = False
        return target

    def _save_and_swap(self, target: Path) -> None:
        """เขียนไฟล์ใหม่ลงไฟล์ชั่วคราว ตรวจว่าใช้ได้จริง แล้วค่อยสลับทับไฟล์เดิม

        ตรวจก่อนสลับ เพราะถ้าไฟล์ใหม่เสียแล้วเราทับไปเลย ต้นฉบับของผู้ใช้จะหายถาวร
        (เคยเกิดจริง: incremental save ทำ xref เสีย ได้ไฟล์ 0 หน้า)
        """
        want_pages = self.doc.page_count
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            self.doc.save(str(tmp), garbage=3, deflate=True,
                          encryption=fitz.PDF_ENCRYPT_KEEP)
            # ตรวจไฟล์ที่เพิ่งเขียน — ต้องเปิดได้และจำนวนหน้าตรง
            with fitz.open(str(tmp)) as check:
                got = check.page_count
            if got != want_pages:
                raise RuntimeError(
                    f"ไฟล์ที่บันทึกมี {got} หน้า แต่ควรมี {want_pages} หน้า — ยกเลิกการบันทึก "
                    "เพื่อไม่ให้ไฟล์เดิมเสียหาย"
                )
        except Exception:
            tmp.unlink(missing_ok=True)      # ไฟล์เดิมยังอยู่ครบ ไม่ถูกแตะ
            raise

        # ไฟล์ใหม่ใช้ได้แน่แล้ว ค่อยปิดตัวเก่าและสลับ
        self.doc.close()
        try:
            _swap_file(tmp, target)
        except OSError:
            # สลับไม่ได้จริงๆ — กลับไปเปิดไฟล์เดิมให้ทำงานต่อได้ (ไฟล์เดิมยังอยู่ครบ)
            tmp.unlink(missing_ok=True)
            self.doc = fitz.open(str(target))
            self._in_memory = False
            raise
        self.doc = fitz.open(str(target))
        self._in_memory = False

    @property
    def is_encrypted(self) -> bool:
        """ไฟล์ที่เปิดอยู่ตอนนี้มาจากไฟล์ที่มีรหัสไหม"""
        return bool(getattr(self, "_was_encrypted", False))

    def save_with_password(
        self,
        target: str | Path,
        user_pw: str,
        owner_pw: str | None = None,
    ) -> Path:
        """บันทึกเป็นไฟล์ใหม่พร้อมตั้งรหัสผ่าน (user_pw ว่าง = ไม่ใส่รหัส/ลบรหัส)"""
        target = Path(target)
        # ฝังลายเซ็น/ข้อความที่ลอยอยู่ก่อน เหมือนตอน save ปกติ
        if self.stamps or self.textboxes:
            self._flatten_stamps(self.doc)
            self._flatten_textboxes(self.doc)
            self.stamps = []
            self.textboxes = []

        if user_pw:
            self.doc.save(
                str(target),
                encryption=fitz.PDF_ENCRYPT_AES_256,
                user_pw=user_pw,
                owner_pw=owner_pw or user_pw,
                permissions=int(fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT
                                | fitz.PDF_PERM_COPY | fitz.PDF_PERM_ANNOTATE),
                garbage=3, deflate=True,
            )
        else:
            # ลบรหัส — เขียนใหม่แบบไม่เข้ารหัส
            self.doc.save(str(target), encryption=fitz.PDF_ENCRYPT_NONE,
                          garbage=3, deflate=True)

        self.dirty = False
        return target

    # ---------- อ่าน/ค้นหา ----------

    def render_page(self, index: int, zoom: float = 1.0) -> fitz.Pixmap:
        matrix = fitz.Matrix(zoom, zoom)
        return self.doc.load_page(index).get_pixmap(matrix=matrix, alpha=False)

    def page_text(self, index: int) -> str:
        return self.doc.load_page(index).get_text()

    def all_text(self) -> str:
        return "\n".join(self.page_text(i) for i in range(self.page_count))

    def search(self, needle: str) -> list[SearchHit]:
        if not needle.strip():
            return []
        hits: list[SearchHit] = []
        for i in range(self.page_count):
            for rect in self.doc.load_page(i).search_for(needle):
                hits.append(SearchHit(page=i, rect=rect))
        return hits

    # ---------- จัดการหน้า ----------

    def insert_blank_page(self, at: int) -> None:
        """แทรกหน้าว่างขนาดเท่าหน้าก่อนหน้า (หรือ A4 ถ้าเอกสารว่าง)"""
        if self.page_count:
            ref = self.doc.load_page(min(at, self.page_count - 1)).rect
            width, height = ref.width, ref.height
        else:
            width, height = 595, 842  # A4 ที่ 72 dpi
        self.push_undo()
        self.doc.new_page(pno=at, width=width, height=height)
        self._shift_floating(at, 1)
        self.dirty = True

    def insert_pdf(self, at: int, source: str | Path) -> int:
        """แทรกทุกหน้าจากไฟล์อื่นเข้ามาที่ตำแหน่ง at คืนจำนวนหน้าที่แทรก"""
        with fitz.open(str(source)) as src:
            added = src.page_count
            self.push_undo()
            self.doc.insert_pdf(src, start_at=at)
        self._shift_floating(at, added)
        self.dirty = True
        return added

    def delete_pages(self, indexes: list[int]) -> None:
        if len(indexes) >= self.page_count:
            raise ValueError("ลบทุกหน้าไม่ได้ — เอกสารต้องเหลืออย่างน้อย 1 หน้า")
        self.push_undo()
        gone = sorted(set(indexes), reverse=True)
        # ลบจากท้ายไปหน้า เพื่อไม่ให้ index เลื่อน
        for i in gone:
            self.doc.delete_page(i)
        removed = set(gone)
        # ของลอยบนหน้าที่ถูกลบก็หายไปด้วย ที่เหลือเลื่อนขึ้นตามจำนวนหน้าที่ถูกลบก่อนหน้ามัน
        self._remap_floating(
            lambda p: None if p in removed else p - sum(1 for g in removed if g < p))
        self.dirty = True

    def move_page(self, source: int, dest: int) -> None:
        self.push_undo()
        before = list(range(self.page_count))
        self.doc.move_page(source, dest)
        # เทียบลำดับเดิม -> ใหม่ เพื่อย้ายของลอยตามหน้าไปด้วย
        moved = before.pop(source)
        before.insert(dest if dest <= source else dest - 1, moved)
        new_of = {old: new for new, old in enumerate(before)}
        self._remap_floating(lambda p: new_of.get(p, p))
        self.dirty = True

    def rotate_pages(self, indexes: list[int], degrees: int) -> None:
        """หมุนแบบสะสมจากมุมเดิมของหน้านั้น"""
        self.push_undo()
        for i in indexes:
            page = self.doc.load_page(i)
            page.set_rotation((page.rotation + degrees) % 360)
        self.dirty = True

    def crop_pages(self, indexes: list[int], margins: tuple[float, float, float, float]) -> None:
        """ครอบตัดหน้า — margins = (ซ้าย, บน, ขวา, ล่าง) เป็นสัดส่วน 0..1 ของขนาดหน้า"""
        left, top, right, bottom = margins
        self.push_undo()
        for i in indexes:
            if not (0 <= i < self.page_count):
                continue
            page = self.doc.load_page(i)
            r = page.rect
            new = fitz.Rect(r.x0 + left * r.width, r.y0 + top * r.height,
                            r.x1 - right * r.width, r.y1 - bottom * r.height)
            # กันครอบจนเหลือศูนย์
            if new.width > 5 and new.height > 5:
                page.set_cropbox(new)
        self.dirty = True

    def crop_pages_rect(self, indexes: list[int], rect: fitz.Rect) -> None:
        """ครอบตัดหน้าตามกรอบที่ลาก (พิกัดบนหน้า อ้างอิงหน้าแรกใน indexes)"""
        self.push_undo()
        for i in indexes:
            if not (0 <= i < self.page_count):
                continue
            page = self.doc.load_page(i)
            clipped = rect & page.rect     # ตัดให้อยู่ในขอบหน้า
            if clipped.width > 5 and clipped.height > 5:
                page.set_cropbox(clipped)
        self.dirty = True

    def compress(self, target: str | Path, image_quality: int = 60,
                 downsample_dpi: int = 120) -> tuple[int, int]:
        """บีบอัดลดขนาดไฟล์ — บีบรูป + subset ฟอนต์ + เก็บขยะ
        คืน (ขนาดเดิม, ขนาดใหม่) เป็น bytes. บีบจากสำเนาที่ฝังวัตถุลอยแล้ว
        """
        target = Path(target)
        old_size = (self.path.stat().st_size if self.path and self.path.exists()
                    else len(self.doc.tobytes()))
        with self.flattened() as flat:
            new_size = compress_pdf(flat, target, image_quality, downsample_dpi)
        return old_size, new_size

    def reorder_pages(self, order: list[int]) -> None:
        """เรียงหน้าใหม่ทั้งเอกสาร — order คือ index เดิมเรียงตามลำดับใหม่ที่ต้องการ"""
        if sorted(order) != list(range(self.page_count)):
            raise ValueError("ลำดับหน้าใหม่ไม่ครบหรือซ้ำ")
        if order != list(range(self.page_count)):
            self.push_undo()
            self.doc.select(order)
            new_of = {old: new for new, old in enumerate(order)}
            self._remap_floating(lambda p: new_of.get(p))
            self.dirty = True

    # ---------- รวม/แยก ----------

    def append_pdf(self, source: str | Path) -> int:
        return self.insert_pdf(self.page_count, source)

    def extract_to(self, indexes: list[int], target: str | Path) -> Path:
        """เขียนเฉพาะหน้าที่เลือกออกเป็นไฟล์ใหม่ (ไม่แตะเอกสารปัจจุบัน)"""
        out = fitz.open()
        for i in sorted(set(indexes)):
            out.insert_pdf(self.doc, from_page=i, to_page=i)
        out.save(str(target), garbage=3, deflate=True)
        out.close()
        return Path(target)

    def split_to_files(self, folder: str | Path, stem: str | None = None,
                       per_file: int = 1, indexes: list[int] | None = None,
                       progress=None) -> list[Path]:
        """แยกออกเป็นหลายไฟล์ — per_file=1 คือหน้าละไฟล์ (100 หน้า = 100 ไฟล์)

        คืนรายการไฟล์ที่เขียน · progress(done, total) ถูกเรียกระหว่างทำ
        """
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        stem = stem or (self.path.stem if self.path else "หน้า")
        pages = sorted(set(indexes)) if indexes else list(range(self.page_count))
        pages = [i for i in pages if 0 <= i < self.page_count]
        if not pages:
            return []
        per_file = max(1, per_file)
        groups = [pages[i:i + per_file] for i in range(0, len(pages), per_file)]
        width = max(3, len(str(len(groups))))    # เลขลำดับให้เรียงไฟล์ถูกต้อง (001, 002, ...)
        written: list[Path] = []
        # ฝังวัตถุลอย (ข้อความ/ลายเซ็น/ลายน้ำ) ก่อน ไม่งั้นของที่เพิ่มไว้จะหายจากไฟล์ที่แยก
        with self.flattened() as flat:
            for n, group in enumerate(groups, start=1):
                if progress:
                    progress(n - 1, len(groups))
                out = fitz.open()
                for i in group:
                    out.insert_pdf(flat, from_page=i, to_page=i)
                if per_file == 1:
                    name = f"{stem}-{group[0] + 1:0{width}d}.pdf"
                else:
                    name = f"{stem}-{group[0] + 1:0{width}d}-{group[-1] + 1:0{width}d}.pdf"
                target = folder / name
                out.save(str(target), garbage=3, deflate=True)
                out.close()
                written.append(target)
        if progress:
            progress(len(groups), len(groups))
        return written

    def page_size_of(self, index: int) -> tuple[float, float]:
        """ขนาดหน้าที่แสดงจริง (กว้าง, สูง) — page.rect สลับด้านตามมุมหมุนให้แล้ว"""
        r = self.doc.load_page(index).rect
        return (r.width, r.height)

    @staticmethod
    def paper_name(width: float, height: float, tol: float = 6.0) -> str:
        """ชื่อกระดาษมาตรฐานจากขนาดเป็นจุด (A4/Letter/...) — ไม่รู้จักก็คืนขนาดมิลลิเมตร"""
        known = {"A4": (595.28, 841.89), "A3": (841.89, 1190.55), "A5": (419.53, 595.28),
                 "Letter": (612.0, 792.0), "Legal": (612.0, 1008.0),
                 "Tabloid": (792.0, 1224.0)}
        for name, (w, h) in known.items():
            for a, b in ((w, h), (h, w)):        # แนวตั้ง/แนวนอนถือว่าชื่อเดียวกัน
                if abs(width - a) <= tol and abs(height - b) <= tol:
                    return name
        return f"{width * 25.4 / 72:.0f}×{height * 25.4 / 72:.0f} มม."

    def describe_size(self, index: int) -> str:
        w, h = self.page_size_of(index)
        return f"{self.paper_name(w, h)} ({w:.0f}×{h:.0f} pt)"

    def describe_source_sizes(self, sources: list[str | Path], limit: int = 3) -> str:
        """สรุปขนาดหน้าของไฟล์ที่จะแทรก (ไว้โชว์ให้ผู้ใช้เห็นว่าต่างกันตรงไหน)"""
        seen: list[str] = []
        for source in sources:
            try:
                with fitz.open(str(source)) as src:
                    for i in range(src.page_count):
                        r = src.load_page(i).rect
                        label = f"{self.paper_name(r.width, r.height)} ({r.width:.0f}×{r.height:.0f} pt)"
                        if label not in seen:
                            seen.append(label)
            except Exception:
                continue
        return " · ".join(seen[:limit]) + (" …" if len(seen) > limit else "")

    def sizes_differ_from(self, sources: list[str | Path], at: int = 0,
                          tol: float = 2.0) -> bool:
        """ไฟล์ที่จะแทรกมีหน้าขนาดต่างจากเอกสารนี้ไหม (ไว้ถามผู้ใช้ว่าจะปรับให้เท่ากันไหม)"""
        if not self.page_count:
            return False
        # เทียบแบบไม่สนแนวตั้ง/นอน — การแทรกจะสลับแนวให้เองอยู่แล้ว
        # (A4 ตั้ง กับ A4 นอน ถือว่ากระดาษขนาดเดียวกัน ไม่ต้องถามผู้ใช้)
        target = sorted(self.page_size_of(min(at, self.page_count - 1)))
        for source in sources:
            try:
                with fitz.open(str(source)) as src:
                    for i in range(src.page_count):
                        r = src.load_page(i).rect
                        got = sorted((r.width, r.height))
                        if any(abs(a - b) > tol for a, b in zip(got, target)):
                            return True
            except Exception:
                continue
        return False

    def insert_pdfs(self, at: int, sources: list[str | Path],
                    fit_to_page: bool = False) -> int:
        """แทรกหลายไฟล์ต่อกันที่ตำแหน่ง at (เรียงตามลำดับที่ส่งมา) คืนจำนวนหน้าที่แทรก

        fit_to_page=True จะย่อ/ขยายหน้าที่แทรกให้พอดีขนาดหน้าของเอกสารนี้ (คงสัดส่วน
        วางกึ่งกลาง) — ใช้ show_pdf_page จึงยังเป็น vector คมชัดเหมือนเดิม ไม่ใช่รูปภาพ
        """
        if not sources:
            return 0
        self.push_undo()
        target = self.page_size_of(min(at, self.page_count - 1)) if self.page_count else None
        total = 0
        cursor = at
        self.fit_failed_pages = 0      # หน้าที่ปรับขนาดไม่ได้ ต้องคงขนาดเดิมแทน
        for source in sources:
            with fitz.open(str(source)) as src:
                if fit_to_page and target:
                    cursor += self._insert_all_fitted(cursor, src, target)
                else:
                    self.doc.insert_pdf(src, start_at=cursor)
                    cursor += src.page_count
                total += src.page_count
        self._shift_floating(at, total)
        self.dirty = True
        return total

    def _insert_all_fitted(self, at: int, src: "fitz.Document",
                           target: tuple[float, float]) -> int:
        """แทรกทุกหน้าของ src แบบปรับขนาด คืนจำนวนหน้าที่แทรก

        บาง PDF มีโครงสร้างหน้าไม่เป็นไปตามมาตรฐาน (MuPDF ฟ้อง "object is not a stream")
        จึงลองซ่อมไฟล์ในหน่วยความจำแล้วทำใหม่ · ถ้ายังไม่ได้ก็ใส่หน้านั้นแบบขนาดเดิม
        ดีกว่าปล่อยให้ล้มทั้งงาน
        """
        # ลายเซ็น/ตราประทับในไฟล์สแกนมักเป็น annotation ไม่ใช่เนื้อหาหน้า
        # ส่วนคำสั่งย่อ/ขยายหน้า (show_pdf_page) คัดลอกแค่ "เนื้อหา" -> annotation หายหมด
        # จึงฝัง annotation ลงเนื้อหาก่อน (bake) แล้วค่อยย่อ/ขยาย ลายเซ็นจะติดไปด้วย
        src = self._baked_copy(src) or src
        repaired = None
        added = 0
        for i in range(src.page_count):
            if self._insert_fitted(at + added, src, i, target):
                added += 1
                continue
            if repaired is None:            # ลองซ่อมโครงสร้างไฟล์แล้วทำใหม่ (ครั้งเดียวพอ)
                try:
                    repaired = fitz.open("pdf", src.tobytes(garbage=3, clean=True))
                except Exception:
                    repaired = False
            if repaired and self._insert_fitted(at + added, repaired, i, target):
                added += 1
                continue
            # ยังไม่ได้จริงๆ — ใส่หน้านั้นตามขนาดเดิม (ยังได้เนื้อหาครบ)
            self.doc.insert_pdf(src, from_page=i, to_page=i, start_at=at + added)
            self.fit_failed_pages += 1
            added += 1
        if repaired:
            repaired.close()
        if getattr(src, "_ballcar_baked", False):
            src.close()
        return added

    @staticmethod
    def _baked_copy(src: "fitz.Document") -> "fitz.Document | None":
        """สำเนาที่ฝัง annotation/ฟอร์มลงเนื้อหาหน้าแล้ว — None ถ้าไม่มีอะไรต้องฝัง

        ใช้ก่อนย่อ/ขยายหน้า เพื่อไม่ให้ลายเซ็น ตราประทับ หรือค่าที่กรอกในฟอร์มหายไป
        """
        try:
            has_extra = any(src.load_page(i).first_annot is not None
                            for i in range(src.page_count))
        except Exception:
            return None
        if not has_extra:
            return None
        try:
            copy = fitz.open("pdf", src.tobytes())
            copy.bake(annots=True, widgets=True)
            copy._ballcar_baked = True
            return copy
        except Exception:
            return None      # ฝังไม่ได้ก็ใช้ต้นฉบับต่อ ดีกว่าล้มทั้งงาน

    def _insert_fitted(self, at: int, src: "fitz.Document", index: int,
                       target: tuple[float, float]) -> bool:
        """แทรกหน้า index ของ src ลงหน้าใหม่ขนาด target (คงสัดส่วน วางกึ่งกลาง)

        เรื่องการหมุน: show_pdf_page ของ PyMuPDF "ไม่สนใจ /Rotate ของหน้าต้นทางตอนวาด"
        (วาดเนื้อหาดิบ) แต่ยังใช้ขนาดหลังหมุนมาคำนวณการย่อ — ผลคือหน้าที่ถูกหมุนไว้
        (ไฟล์สแกน/ใบแจ้งหนี้) จะออกมาตะแคงและขนาดเพี้ยน
        จึงล้างมุมหมุนของหน้าต้นทางชั่วคราวให้ทำงานในพิกัดดิบตรงๆ แล้วใส่มุมหมุนคืน
        ที่หน้าใหม่ (ตรวจแล้วได้ผลตรงกับต้นฉบับเป๊ะทุกมุม 0/90/180/270)

        คืน False ถ้าทำไม่ได้ — ผู้เรียกจะได้ลองทางอื่นต่อ (หน้าที่สร้างค้างไว้ถูกลบทิ้ง)
        """
        tw, th = target
        try:
            src_page = src.load_page(index)
            rot = src_page.rotation
            shown = src_page.rect                  # ขนาดที่ "แสดงจริง" (รวมการหมุนแล้ว)
            if shown.width <= 0 or shown.height <= 0:
                return False
            # คงขนาดกระดาษเดิมไว้ แต่สลับแนวตั้ง/นอนให้ตรงกับหน้าต้นทาง
            # (ยัดหน้าแนวนอนลงกระดาษแนวตั้งจะเหลือขอบว่างเยอะและเนื้อหาเล็กจนอ่านไม่ออก)
            if (shown.width > shown.height) != (tw > th):
                tw, th = th, tw
            # mediabox ของหน้าใหม่ (ก่อนหมุน) ที่ทำให้ "แสดงผล" ออกมาเป็น tw x th
            bw, bh = (th, tw) if rot in (90, 270) else (tw, th)

            src_page.set_rotation(0)               # ทำงานในพิกัดดิบ ไม่กำกวม
            try:
                mw, mh = src_page.rect.width, src_page.rect.height
                if mw <= 0 or mh <= 0:
                    return False
                scale = min(bw / mw, bh / mh)
                w, h = mw * scale, mh * scale
                x, y = (bw - w) / 2, (bh - h) / 2
                page = self.doc.new_page(pno=at, width=bw, height=bh)
                try:
                    page.show_pdf_page(fitz.Rect(x, y, x + w, y + h), src, index)
                except Exception:
                    self.doc.delete_page(at)       # เก็บกวาดหน้าเปล่าที่เพิ่งสร้าง
                    return False
                page.set_rotation(rot)             # ให้แสดงผลเหมือนต้นฉบับ
            finally:
                src_page.set_rotation(rot)         # คืนค่าเดิม (กันกระทบไฟล์ต้นทาง)
            return True
        except Exception:
            return False

    # ---------- เลขหน้า ----------

    def add_page_numbers(
        self,
        fmt: str = "{page}/{total}",
        position: str = "bottom-center",
        font_size: int = 10,
        start_at: int = 1,
        margin: float = 28,
        numeral: str = "arabic",
        first_page: int = 0,
    ) -> None:
        """ใส่เลขหน้าตั้งแต่หน้า first_page (index) เป็นต้นไป โดยหน้านั้นได้เลข start_at

        เช่น first_page=7, start_at=1 -> หน้าที่ 8 ของไฟล์ได้เลข 1 (หน้าปก/สารบัญไม่มีเลข)
        {total} = เลขของหน้าสุดท้าย ไม่ใช่จำนวนหน้าทั้งไฟล์
        """
        if not 0 <= first_page < self.page_count:
            raise ValueError(f"หน้าเริ่มต้นต้องอยู่ระหว่าง 1–{self.page_count}")
        fmt.format(page=1, total=1)   # รูปแบบผิดให้ล้มตรงนี้ ก่อนแตะหน้าใดๆ
        last_no = start_at + (self.page_count - first_page) - 1
        self.push_undo()
        for i in range(first_page, self.page_count):
            page = self.doc.load_page(i)
            page_no = _format_numeral(i - first_page + start_at, numeral)
            total_no = _format_numeral(last_no, numeral)
            text = fmt.format(page=page_no, total=total_no)
            rect = page.rect
            # รูปแบบที่มีคำไทย เช่น "หน้า {page}" ต้องใช้ฟอนต์ไทย (helv ไม่มีอักษรไทย)
            fontname, font = self._register_font(page, text)
            width = font.text_length(text, fontsize=font_size)

            top = position.startswith("top")
            y = rect.y0 + margin if top else rect.y1 - margin
            if position.endswith("left"):
                x = rect.x0 + margin
            elif position.endswith("right"):
                x = rect.x1 - margin - width
            else:
                x = (rect.width - width) / 2

            page.insert_text((x, y), text, fontname=fontname, fontsize=font_size)
        self.dirty = True

    # ---------- ลายน้ำ / ลายเซ็น ----------

    def _register_font(self, page: fitz.Page, text: str) -> tuple[str, fitz.Font]:
        """ลงทะเบียนฟอนต์ให้หน้านั้น คืน (ชื่อที่ใช้ตอน insert, ออบเจกต์ฟอนต์ไว้วัดความกว้าง)"""
        if not _has_thai(text):
            return "helv", fitz.Font("helv")  # อังกฤษล้วนใช้ฟอนต์มาตรฐาน ไฟล์เล็กกว่า
        font_path = find_thai_font()
        if not font_path:
            raise RuntimeError(
                "ไม่พบฟอนต์ภาษาไทยในเครื่อง — ลายน้ำภาษาไทยจะแสดงไม่ถูกต้อง "
                "(ลองใช้ข้อความภาษาอังกฤษแทน)"
            )
        page.insert_font(fontname="thai", fontfile=font_path)
        return "thai", fitz.Font(fontfile=font_path)

    def add_text_watermark(
        self,
        text: str,
        indexes: list[int] | None = None,
        opacity: float = 0.18,
        angle: float = 45,
        color: tuple[float, float, float] = (0.5, 0.5, 0.5),
        font_size: int | None = None,
    ) -> None:
        """ใส่ลายน้ำข้อความกลางหน้า เอียงตามองศาที่กำหนด"""
        if not text.strip():
            raise ValueError("ยังไม่ได้ใส่ข้อความลายน้ำ")
        indexes = list(range(self.page_count)) if indexes is None else sorted(set(indexes))

        self.push_undo()
        for i in indexes:
            page = self.doc.load_page(i)
            fontname, font = self._register_font(page, text)
            rect = page.rect

            # ขนาดอัตโนมัติ: วัดความกว้างจริงของฟอนต์ ให้ข้อความพอดี ~80% ของหน้า
            # (เอียง 45° ทำให้มีที่มากขึ้นตามแนวทแยง จึงเผื่อตามองศาด้วย)
            if font_size:
                size = font_size
            else:
                # ข้อความกว้าง u*size สูงราว 1.2*size เมื่อหมุน angle องศาแล้ว
                # กรอบที่กินพื้นที่จริงคือ (u*cos + 1.2*sin) x (u*sin + 1.2*cos)
                # หา size ที่ใหญ่สุดที่ยังอยู่ใน 85% ของหน้าทั้งสองแกน
                unit = font.text_length(text, fontsize=1) or 1
                cos_a = abs(math.cos(math.radians(angle)))
                sin_a = abs(math.sin(math.radians(angle)))
                size = min(
                    rect.width * 0.85 / (unit * cos_a + 1.2 * sin_a),
                    rect.height * 0.85 / (unit * sin_a + 1.2 * cos_a),
                )
                size = max(8, size)

            # วางเป็นบรรทัดเดียวกลางหน้า แล้วหมุนรอบจุดกึ่งกลางด้วย morph
            # (ไม่ใช้ insert_textbox เพราะมันตัดข้อความทิ้งเมื่อกล่องไม่พอดี)
            center = fitz.Point(rect.width / 2, rect.height / 2)
            width = font.text_length(text, fontsize=size)
            start = fitz.Point(center.x - width / 2, center.y + size * 0.35)

            page.insert_text(
                start, text,
                fontname=fontname, fontsize=size, color=color,
                fill_opacity=opacity,
                morph=(center, fitz.Matrix(angle)),
            )
        self.dirty = True

    @contextmanager
    def flattened(self):
        """สำเนาเอกสารที่ฝังวัตถุลอย (ข้อความ/ลายเซ็น/ลายน้ำ) ลงไปแล้ว

        ใช้ตอนพิมพ์และบันทึกเป็นรูป — ไม่งั้นจะได้แต่หน้าดิบ ข้อความที่เพิ่มไว้หายหมด
        """
        if not (self.stamps or self.textboxes or self.watermark or self.erasers
                or self.annotations):
            yield self.doc          # ไม่มีวัตถุลอย ใช้ตัวจริงได้เลย ไม่ต้องสำเนา
            return
        copy = fitz.open("pdf", self.doc.tobytes())
        try:
            self._flatten_erasers(copy)     # ลบก่อน แล้วค่อยวางของทับ
            self._flatten_stamps(copy)
            self._flatten_textboxes(copy)
            self._flatten_annotations(copy)
            self._flatten_watermark(copy)
            yield copy
        finally:
            copy.close()

    # ---------- ลายน้ำแบบแก้ไขได้ (ยังไม่ฝังจนกว่าจะบันทึก) ----------

    def set_watermark(self, text: str, indexes: list[int] | None = None, **kwargs) -> Watermark:
        """ตั้งลายน้ำ (แทนที่ของเดิมถ้ามี) — ยังแก้ไขได้จนกว่าจะบันทึก"""
        if not text.strip():
            raise ValueError("ยังไม่ได้ใส่ข้อความลายน้ำ")
        self.push_undo()
        self.watermark = Watermark(text=text, indexes=indexes, **kwargs)
        self.dirty = True
        return self.watermark

    def update_watermark(self, **kwargs) -> None:
        """ปรับค่าลายน้ำที่มีอยู่ (text/opacity/angle/color/font_size/indexes)"""
        if self.watermark is None:
            return
        self.push_undo()
        # ตั้งทุกคีย์ที่ส่งมา (รวม None) — font_size=None คือกลับไปใช้ขนาดอัตโนมัติ
        for key, value in kwargs.items():
            setattr(self.watermark, key, value)
        self.dirty = True

    def remove_watermark(self) -> bool:
        if self.watermark is None:
            return False
        self.push_undo()
        self.watermark = None
        self.dirty = True
        return True

    def watermark_geometry(self, index: int) -> tuple[float, float, float, float] | None:
        """คำนวณตำแหน่ง/ขนาดลายน้ำบนหน้า (x_กลาง, y_กลาง, ขนาดฟอนต์, ความกว้างข้อความ)
        ใช้ร่วมกันทั้งตอนวาดบนจอและตอนฝังลงไฟล์ ให้ตรงกันเป๊ะ"""
        wm = self.watermark
        if wm is None or not wm.applies_to(index):
            return None
        page = self.doc.load_page(index)
        rect = page.rect
        _, font = self._register_font(page, wm.text)
        if wm.font_size:
            size = wm.font_size
        else:
            unit = font.text_length(wm.text, fontsize=1) or 1
            cos_a = abs(math.cos(math.radians(wm.angle)))
            sin_a = abs(math.sin(math.radians(wm.angle)))
            size = min(rect.width * 0.85 / (unit * cos_a + 1.2 * sin_a),
                       rect.height * 0.85 / (unit * sin_a + 1.2 * cos_a))
            size = max(8, size)
        width = font.text_length(wm.text, fontsize=size)
        return rect.width / 2, rect.height / 2, size, width

    def _flatten_watermark(self, doc) -> None:
        """ฝังลายน้ำลงเอกสารจริง (เรียกตอนบันทึก)"""
        wm = self.watermark
        if wm is None:
            return
        indexes = range(doc.page_count) if wm.indexes is None else sorted(set(wm.indexes))
        for i in indexes:
            if not (0 <= i < doc.page_count):
                continue
            geo = self.watermark_geometry(i)
            if geo is None:
                continue
            cx, cy, size, width = geo
            page = doc.load_page(i)
            fontname, _ = self._register_font(page, wm.text)
            center = fitz.Point(cx, cy)
            start = fitz.Point(cx - width / 2, cy + size * 0.35)
            page.insert_text(
                start, wm.text,
                fontname=fontname, fontsize=size, color=wm.color,
                fill_opacity=wm.opacity,
                morph=(center, fitz.Matrix(wm.angle)),
            )

    # ---------- ลายเซ็นแบบแก้ไขได้ ----------

    @staticmethod
    def prepare_image(path: str | Path, remove_background: bool = True) -> str:
        """เตรียมรูปลายเซ็นให้พร้อมวางลง PDF

        - แปลงทุกนามสกุลเป็น PNG (GIF ใช้ index transparency, อาจมีหลายเฟรม)
        - ลบพื้นหลังขาวออกให้เป็นโปร่งใส เพื่อไม่ให้บังเนื้อหาใต้ลายเซ็น
        """
        from PIL import Image

        path = Path(path)
        suffix = "-nobg" if remove_background else ""
        out = Path(tempfile.gettempdir()) / f"pdftool-sig-{abs(hash(str(path)))}{suffix}.png"

        with Image.open(path) as im:
            im.seek(0)  # ภาพเคลื่อนไหว -> เอาเฟรมแรก
            rgba = im.convert("RGBA")

        if remove_background:
            rgba = _strip_white_background(rgba)
        elif path.suffix.lower() in (".png", ".jpg", ".jpeg"):
            return str(path)  # ใช้ไฟล์เดิมได้เลย ไม่ต้องแปลง

        rgba.save(out, format="PNG")
        return str(out)

    def add_stamp(self, page: int, image_path: str | Path, rect: fitz.Rect) -> Stamp:
        """เพิ่มลายเซ็นเป็นชั้นลอย (ยังย้าย/ย่อขยาย/ลบได้)"""
        self.push_undo()
        stamp = Stamp(page, fitz.Rect(rect), str(image_path))
        self.stamps.append(stamp)
        self.dirty = True
        return stamp

    # ---------- ยางลบ / ปิดทับ (สำหรับไฟล์สแกน) ----------

    def add_eraser(self, page: int, rect: fitz.Rect,
                   color: tuple[float, float, float] | None = None) -> Eraser:
        """ปิดทับพื้นที่บนหน้า — color=None คือดูดสีพื้นหลังรอบๆ ให้กลืนกับกระดาษ"""
        if color is None:
            color = sample_background_color(self.doc.load_page(page), fitz.Rect(rect))
        self.push_undo()
        eraser = Eraser(page, fitz.Rect(rect), color)
        self.erasers.append(eraser)
        self.dirty = True
        return eraser

    def remove_eraser(self, eraser: Eraser) -> None:
        self.push_undo()
        if eraser in self.erasers:
            self.erasers.remove(eraser)
        self.dirty = True

    def erasers_on(self, page: int) -> list[Eraser]:
        return [e for e in self.erasers if e.page == page]

    def eraser_at(self, page: int, point: fitz.Point) -> Eraser | None:
        for eraser in reversed(self.erasers_on(page)):
            if eraser.rect.contains(point):
                return eraser
        return None

    def _flatten_erasers(self, doc: fitz.Document) -> None:
        """ลบเนื้อหาใต้แผ่นปิดออกจริง แล้วถมด้วยสีที่เลือก

        ต้องใช้ redaction ไม่ใช่แค่วาดสี่เหลี่ยมทับ — ไม่งั้นข้อความเดิมยังอยู่ในไฟล์
        (ลากคลุมคัดลอกออกไปได้ ทั้งที่ตาเห็นว่าถูกลบแล้ว)
        """
        by_page: dict[int, list[Eraser]] = {}
        for eraser in self.erasers:
            if 0 <= eraser.page < doc.page_count:
                by_page.setdefault(eraser.page, []).append(eraser)
        for page_index, items in by_page.items():
            page = doc.load_page(page_index)
            for eraser in items:
                rect = eraser.rect * page.derotation_matrix if page.rotation else eraser.rect
                page.add_redact_annot(rect, fill=eraser.color)
            page.apply_redactions()

    # ---------- รูปวาด / มาร์กอัป ----------

    def add_annotation(self, page: int, kind: str, points: list,
                       color: tuple[float, float, float] = (0.9, 0.1, 0.1),
                       width: float = 2.0) -> Annotation:
        """เพิ่มรูปวาด (draw/line/arrow/rect/circle) เป็นชั้นลอย"""
        self.push_undo()
        annot = Annotation(page, kind, [tuple(p) for p in points], color, width)
        self.annotations.append(annot)
        self.dirty = True
        return annot

    def remove_annotation(self, annot: Annotation) -> None:
        self.push_undo()
        if annot in self.annotations:
            self.annotations.remove(annot)
        self.dirty = True

    def annotations_on(self, page: int) -> list[Annotation]:
        return [a for a in self.annotations if a.page == page]

    def clear_annotations(self, page: int) -> int:
        on = self.annotations_on(page)
        if not on:
            return 0
        self.push_undo()
        for a in on:
            self.annotations.remove(a)
        self.dirty = True
        return len(on)

    def _flatten_annotations(self, doc: fitz.Document) -> None:
        for a in self.annotations:
            if 0 <= a.page < doc.page_count:
                page = doc.load_page(a.page)
                pts = a.points
                if page.rotation:      # แปลงพิกัดกลับตามมุมหมุนของหน้า
                    m = page.derotation_matrix
                    pts = [tuple(fitz.Point(*p) * m) for p in pts]
                _draw_annotation_pdf(page, a.kind, pts, a.color, a.width)

    def add_stamp_all_pages(self, image_path: str | Path, rect: fitz.Rect,
                            indexes: list[int] | None = None) -> int:
        """วางลายเซ็นตำแหน่งเดิมทุกหน้า (หรือเฉพาะหน้าที่ระบุ) คืนจำนวนหน้าที่วาง"""
        indexes = list(range(self.page_count)) if indexes is None else sorted(set(indexes))
        indexes = [i for i in indexes if 0 <= i < self.page_count]
        if not indexes:
            return 0
        self.push_undo()
        for i in indexes:
            self.stamps.append(Stamp(i, fitz.Rect(rect), str(image_path)))
        self.dirty = True
        return len(indexes)

    def update_stamp(self, stamp: Stamp, rect: fitz.Rect) -> None:
        self.push_undo()
        stamp.rect = fitz.Rect(rect)
        self.dirty = True

    def remove_stamp(self, stamp: Stamp) -> None:
        self.push_undo()
        if stamp in self.stamps:
            self.stamps.remove(stamp)
        self.dirty = True

    def stamps_on(self, page: int) -> list[Stamp]:
        return [s for s in self.stamps if s.page == page]

    def stamp_at(self, page: int, point: fitz.Point) -> Stamp | None:
        """หาลายเซ็นที่จุดนั้น — ตัวบนสุด (เพิ่มทีหลัง) ได้ก่อน"""
        for stamp in reversed(self.stamps_on(page)):
            if stamp.rect.contains(point):
                return stamp
        return None

    def _flatten_stamps(self, doc: fitz.Document) -> None:
        """ฝังลายเซ็นทั้งหมดลงในเอกสารที่กำลังจะบันทึก"""
        for stamp in self.stamps:
            if not 0 <= stamp.page < doc.page_count:
                continue
            page = doc.load_page(stamp.page)
            target = stamp.rect * page.derotation_matrix if page.rotation else stamp.rect
            page.insert_image(target, filename=stamp.image_path, overlay=True, alpha=-1)

    # ---------- ข้อความแบบแก้ไขได้ (เพิ่ม/แก้) ----------

    def add_textbox(
        self,
        page: int,
        rect: fitz.Rect,
        text: str = "",
        font_size: float = 14.0,
        color: tuple[float, float, float] = (0.0, 0.0, 0.0),
        font: str = "",
        bold: bool = False,
    ) -> TextBox:
        """เพิ่มกล่องข้อความเป็นชั้นลอย (ยังแก้ไข/ย้าย/ปรับขนาด/ลบได้)"""
        self.push_undo()
        box = TextBox(page, fitz.Rect(rect), text, font_size, color, font, bold)
        self.textboxes.append(box)
        self.dirty = True
        return box

    def label_anchor(self, page_index: int, label: str) -> fitz.Rect | None:
        """หาป้ายข้อความในหน้า (เช่น "Date") คืนกรอบใน "พิกัดที่แสดงจริง"

        ใช้พิกัดที่แสดงจริงเหมือน TextBox ทุกที่ เพื่อให้ "ต่อท้ายป้าย" หมายถึง
        ทางขวาของป้ายอย่างที่ผู้ใช้เห็นจริง แม้หน้าจะถูกหมุนไว้

        ถ้ามีเครื่องหมาย : ต่อท้ายป้ายในบรรทัดเดียวกัน จะรวมโคลอนไว้ในกรอบด้วย
        เพื่อให้ข้อความที่วางต่อท้ายไม่ไปทับโคลอน
        """
        if not label.strip():
            return None
        page = self.doc.load_page(page_index)
        found = page.search_for(label)
        if not found:
            return None
        rect = fitz.Rect(found[0])
        mid_top, mid_bottom = rect.y0 - 2, rect.y1 + 2
        for colon in page.search_for(":"):
            center_y = (colon.y0 + colon.y1) / 2
            # โคลอนต้องอยู่บรรทัดเดียวกัน ถัดจากป้ายไปทางขวา และอยู่ใกล้ๆ (ไม่ใช่คนละคอลัมน์)
            if (mid_top <= center_y <= mid_bottom and colon.x0 >= rect.x1 - 1
                    and colon.x0 - rect.x1 < 60 and colon.x1 > rect.x1):
                rect = fitz.Rect(rect.x0, min(rect.y0, colon.y0),
                                 colon.x1, max(rect.y1, colon.y1))
        # search_for คืนพิกัดก่อนหมุน -> แปลงเป็นพิกัดที่แสดงจริง
        return rect * page.rotation_matrix if page.rotation else rect

    def add_textbox_after_label(self, label: str, text: str,
                                indexes: list[int] | None = None,
                                font_size: float | None = None,
                                gap: float = 6.0,
                                width: float = 150.0) -> tuple[int, list[int]]:
        """วางข้อความต่อท้ายป้ายที่ระบุ ในทุกหน้าที่พบป้ายนั้น

        อ้างตำแหน่งจากป้ายในเอกสาร (เช่น "หลัง Date") จึงตรงช่องเสมอแม้แต่ละหน้า
        วางป้ายไม่ตรงกันเป๊ะ · คืน (จำนวนหน้าที่วางได้, รายการหน้าที่ไม่พบป้าย)
        """
        indexes = list(range(self.page_count)) if indexes is None else sorted(set(indexes))
        indexes = [i for i in indexes if 0 <= i < self.page_count]
        anchors: dict[int, fitz.Rect] = {}
        missing: list[int] = []
        for i in indexes:
            found = self.label_anchor(i, label)
            if found is None:
                missing.append(i)
            else:
                anchors[i] = found
        if not anchors:
            return 0, missing
        self.push_undo()
        for i, anchor in anchors.items():
            page = self.doc.load_page(i)
            # ขนาดตัวอักษรตามความสูงของป้าย เพื่อให้กลืนกับเอกสาร
            size = font_size or max(6.0, min(20.0, anchor.height * 0.8))
            # ทำงานในพิกัดที่แสดงจริงทั้งหมด — "ต่อท้ายป้าย" = ทางขวาอย่างที่ผู้ใช้เห็น
            page_right = page.rect.x1
            x0 = anchor.x1 + gap
            x1 = min(x0 + width, page_right - 2)
            if x1 - x0 < 20:                      # ชิดขอบขวาเกินไป ถอยกล่องมาทางซ้าย
                x0 = max(anchor.x0, page_right - 2 - width)
                x1 = page_right - 2
            rect = fitz.Rect(x0, anchor.y0 - size * 0.2, x1, anchor.y1 + size * 0.6)
            self.textboxes.append(TextBox(i, rect, text, size, (0.0, 0.0, 0.0), "", False))
        self.dirty = True
        return len(anchors), missing

    def add_textbox_all_pages(self, template: TextBox,
                              indexes: list[int] | None = None) -> int:
        """วางข้อความเดิม ตำแหน่งเดิม ลงทุกหน้า (หรือเฉพาะหน้าที่ระบุ) คืนจำนวนหน้าที่วาง

        ใช้กับงานที่ต้องลงวันที่/เลขที่เอกสารตรงช่องเดียวกันทุกหน้า
        ข้ามหน้าที่มีข้อความเดียวกันตำแหน่งเดียวกันอยู่แล้ว (กันวางซ้ำทับกัน)
        """
        indexes = list(range(self.page_count)) if indexes is None else sorted(set(indexes))
        indexes = [i for i in indexes if 0 <= i < self.page_count]
        targets = [i for i in indexes
                   if not any(b.text == template.text and b.rect == template.rect
                              for b in self.textboxes_on(i))]
        if not targets:
            return 0
        self.push_undo()
        for i in targets:
            copy = template.copy()
            copy.page = i
            self.textboxes.append(copy)
        self.dirty = True
        return len(targets)

    def update_textbox_rect(self, box: TextBox, rect: fitz.Rect,
                            font_size: float | None = None) -> None:
        self.push_undo()
        box.rect = fitz.Rect(rect)
        if font_size is not None:
            box.font_size = font_size
        self.dirty = True

    def update_textbox_content(
        self,
        box: TextBox,
        text: str | None = None,
        font_size: float | None = None,
        color: tuple[float, float, float] | None = None,
        font: str | None = None,
        bold: bool | None = None,
    ) -> None:
        self.push_undo()
        if text is not None:
            box.text = text
        if font_size is not None:
            box.font_size = font_size
        if color is not None:
            box.color = color
        if font is not None:
            box.font = font
        if bold is not None:
            box.bold = bold
        self.dirty = True

    def remove_textbox(self, box: TextBox) -> None:
        self.push_undo()
        if box in self.textboxes:
            self.textboxes.remove(box)
        self.dirty = True

    def textboxes_on(self, page: int) -> list[TextBox]:
        return [b for b in self.textboxes if b.page == page]

    def textbox_at(self, page: int, point: fitz.Point) -> TextBox | None:
        """หากล่องข้อความที่จุดนั้น — ตัวบนสุด (เพิ่มทีหลัง) ได้ก่อน"""
        for box in reversed(self.textboxes_on(page)):
            if box.rect.contains(point):
                return box
        return None

    def _draw_textbox(self, page: fitz.Page, box: TextBox) -> None:
        draw_textbox(page, box)

    def _flatten_textboxes(self, doc: fitz.Document) -> None:
        for box in self.textboxes:
            if 0 <= box.page < doc.page_count:
                draw_textbox(doc.load_page(box.page), box)

    # ---------- แก้ไขข้อความเดิมในไฟล์ (ลบของเดิม + วางใหม่ทับ) ----------

    def text_span_at(self, page_index: int, point: fitz.Point) -> dict | None:
        """หาข้อความเดิมที่จุดนั้น คืนข้อมูลบรรทัด (bbox, text, size, สี, ฟอนต์) หรือ None"""
        page = self.doc.load_page(page_index)
        data = page.get_text("dict")
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                # รวมทั้งบรรทัดเป็นก้อนเดียว เพื่อให้แก้ได้ทั้งบรรทัด
                line_rect = fitz.Rect(line["bbox"])
                if not line_rect.contains(point):
                    continue
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                if not text.strip():
                    continue
                first = spans[0]
                srgb = first.get("color", 0)
                color = (((srgb >> 16) & 255) / 255, ((srgb >> 8) & 255) / 255, (srgb & 255) / 255)
                return {
                    "rect": line_rect,
                    "text": text,
                    "size": first.get("size", 12),
                    "color": color,
                }
        return None

    def _sample_background(self, page: fitz.Page, rect: fitz.Rect) -> tuple[float, float, float]:
        """เดาสีพื้นหลังใต้ข้อความ (ดูจากขอบรอบๆ) — คืน (1,1,1) ถ้าไม่แน่ใจ"""
        try:
            pad = 3
            clip = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
            clip = clip & page.rect
            pix = page.get_pixmap(clip=clip, alpha=False)
            if pix.width < 2 or pix.height < 2:
                return (1, 1, 1)
            n = pix.n
            s = pix.samples
            # เก็บสีของแถวบนสุดและล่างสุด (นอกตัวอักษรส่วนใหญ่)
            edge = []
            for x in range(pix.width):
                for y in (0, pix.height - 1):
                    k = (y * pix.width + x) * n
                    edge.append((s[k], s[k + 1], s[k + 2]))
            # ใช้สีที่พบบ่อยสุด
            from collections import Counter
            (r, g, b), _ = Counter(edge).most_common(1)[0]
            return (r / 255, g / 255, b / 255)
        except Exception:
            return (1, 1, 1)

    def start_edit_existing_text(self, page_index: int, point: fitz.Point) -> TextBox | None:
        """ลบข้อความเดิมที่จุดนั้น แล้วคืนกล่องข้อความใหม่ (เติมคำเดิมไว้) ให้แก้ต่อ

        คืน None ถ้าตรงนั้นไม่มีข้อความให้แก้ (เช่นเป็นไฟล์สแกน)
        """
        span = self.text_span_at(page_index, point)
        if span is None:
            return None

        self.push_undo()
        page = self.doc.load_page(page_index)
        rect = span["rect"]
        bg = self._sample_background(page, rect)

        # ลบข้อความเดิมด้วย redaction (ถมด้วยสีพื้นหลังที่เดาได้)
        page.add_redact_annot(rect, fill=bg)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        # วางกล่องใหม่ทับ เติมคำเดิม สี/ขนาดตามของเดิม (ผู้ใช้แก้ต่อได้)
        box = TextBox(
            page_index,
            fitz.Rect(rect.x0, rect.y0 - 1, rect.x1 + 4, rect.y1 + 2),
            span["text"], font_size=span["size"], color=span["color"],
        )
        self.textboxes.append(box)
        self.dirty = True
        return box

    def add_image(
        self,
        index: int,
        image_path: str | Path,
        rect: fitz.Rect,
    ) -> None:
        """วางรูป (ลายเซ็น/ตราประทับ/ลายน้ำรูป) ลงบนหน้าตามกรอบที่กำหนด

        rect เป็นพิกัดบนหน้าที่ผู้ใช้เห็น — แปลงกลับตามมุมหมุนของหน้าให้เอง
        """
        self.push_undo()
        page = self.doc.load_page(index)
        target = rect * page.derotation_matrix if page.rotation else rect
        # alpha=-1 = ใช้ความโปร่งใสที่มากับไฟล์รูป (PNG ลายเซ็นพื้นหลังใสจะไม่มีกรอบขาว)
        page.insert_image(target, filename=str(image_path), overlay=True, alpha=-1)
        self.dirty = True

    def add_image_watermark(
        self,
        image_path: str | Path,
        indexes: list[int] | None = None,
        scale: float = 0.5,
    ) -> None:
        """วางรูปเป็นลายน้ำกลางหน้า (ขนาดตามสัดส่วนความกว้างหน้า)"""
        indexes = list(range(self.page_count)) if indexes is None else sorted(set(indexes))
        self.push_undo()
        for i in indexes:
            page = self.doc.load_page(i)
            rect = page.rect
            width = rect.width * scale
            with fitz.open(str(image_path)) as img:
                ratio = img[0].rect.height / img[0].rect.width if img[0].rect.width else 1
            height = width * ratio
            cx, cy = rect.width / 2, rect.height / 2
            box = fitz.Rect(cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)
            page.insert_image(
                box * page.derotation_matrix if page.rotation else box,
                filename=str(image_path), overlay=True, alpha=-1,
            )
        self.dirty = True

    # ---------- คำสั่งอัตโนมัติ (ใช้โดยผู้ช่วยพิมพ์คำสั่ง) ----------

    def find_blank_pages(self) -> list[int]:
        """หาหน้าว่าง (ไม่มีข้อความและไม่มีรูป)"""
        blank = []
        for i in range(self.page_count):
            page = self.doc.load_page(i)
            if not page.get_text().strip() and not page.get_images():
                blank.append(i)
        return blank

    def delete_blank_pages(self) -> int:
        """ลบหน้าว่างทั้งหมด คืนจำนวนที่ลบ (ไม่ลบถ้าจะเหลือ 0 หน้า)"""
        blank = self.find_blank_pages()
        if not blank or len(blank) >= self.page_count:
            return 0
        self.delete_pages(blank)   # push_undo อยู่ข้างใน
        return len(blank)

    def set_orientation(self, indexes: list[int], orientation: str) -> int:
        """หมุนหน้าให้เป็นแนวนอน/แนวตั้ง คืนจำนวนหน้าที่เปลี่ยน"""
        changed = []
        for i in indexes:
            page = self.doc.load_page(i)
            r = page.rect
            # ขนาดที่แสดงจริง (เผื่อหน้าถูกหมุนไว้แล้ว)
            landscape_now = r.width > r.height
            want_landscape = orientation == "landscape"
            if landscape_now != want_landscape:
                changed.append(i)
        if changed:
            self.rotate_pages(changed, 90)   # push_undo อยู่ข้างใน
        return len(changed)

    def keep_only_pages(self, indexes: list[int]) -> int:
        """เก็บไว้เฉพาะหน้าที่ระบุ ลบที่เหลือ คืนจำนวนหน้าที่เหลือ"""
        keep = sorted(set(i for i in indexes if 0 <= i < self.page_count))
        if not keep or len(keep) == self.page_count:
            return len(keep)
        self.push_undo()
        self.doc.select(keep)
        new_of = {old: new for new, old in enumerate(keep)}
        self._remap_floating(lambda p: new_of.get(p))   # ของลอยบนหน้าที่ถูกตัดทิ้งก็หายไปด้วย
        self.dirty = True
        return len(keep)

    def pages_matching(self, keyword: str) -> list[int]:
        """หน้าที่มีคำนี้อยู่"""
        kw = keyword.strip().lower()
        if not kw:
            return []
        return [i for i in range(self.page_count) if kw in self.page_text(i).lower()]

    def redact_personal_info(self, indexes: list[int] | None = None) -> int:
        """ลบข้อมูลส่วนบุคคล (เบอร์โทร/อีเมล/เลขบัตรประชาชน/เลขบัตรเครดิต) ด้วยการถมทับ"""
        import re

        patterns = [
            re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),            # อีเมล
            re.compile(r"\b\d(?:[ -]?\d){12}\b"),                # เลขบัตรประชาชน 13 หลัก
            re.compile(r"\b0\d(?:[ -]?\d){8}\b"),                # เบอร์โทร 10 หลักขึ้นต้น 0
            re.compile(r"\b\d{4}(?:[ -]?\d{4}){3}\b"),           # เลขบัตรเครดิต 16 หลัก
        ]
        indexes = list(range(self.page_count)) if indexes is None else sorted(set(indexes))
        total = 0
        pushed = False
        for i in indexes:
            page = self.doc.load_page(i)
            text = page.get_text()
            targets = set()
            for pat in patterns:
                for m in pat.findall(text):
                    frag = m if isinstance(m, str) else "".join(m)
                    if len(frag.strip()) >= 6:
                        targets.add(frag.strip())
            hits = []
            for frag in targets:
                hits.extend(page.search_for(frag))
            if not hits:
                continue
            if not pushed:
                self.push_undo()
                pushed = True
            for rect in hits:
                page.add_redact_annot(rect, fill=(0, 0, 0))
            page.apply_redactions()
            total += len(hits)
        if total:
            self.dirty = True
        return total

    # ---------- Bookmarks (สารบัญ / TOC) ----------

    def get_bookmarks(self) -> list[dict]:
        """คืนรายการ bookmark — แต่ละอันมี level (เริ่ม 1), title, page (index เริ่ม 0)"""
        result = []
        for entry in self.doc.get_toc(simple=True):
            level, title, page = entry[0], entry[1], entry[2]
            result.append({
                "level": max(1, level),
                "title": title,
                "page": max(0, page - 1),   # get_toc ใช้หน้าเริ่มที่ 1
            })
        return result

    def set_bookmarks(self, items: list[dict]) -> None:
        """ตั้ง bookmark ทั้งหมดใหม่ (items = list ของ {level, title, page(0-based)})"""
        self.push_undo()
        # ปรับระดับให้ถูกกติกา PDF: อันแรกต้องเป็น 1 และห้ามกระโดดลึกเกิน +1
        toc = []
        prev_level = 0
        for it in items:
            level = max(1, int(it["level"]))
            if level > prev_level + 1:
                level = prev_level + 1
            prev_level = level
            page = min(self.page_count, max(1, int(it["page"]) + 1))
            toc.append([level, str(it["title"]), page])
        self.doc.set_toc(toc)
        self.dirty = True

    def add_bookmark(self, title: str, page: int, level: int = 1,
                     after: int | None = None) -> None:
        """เพิ่ม bookmark 1 อัน (after = index ในรายการที่จะแทรกต่อท้าย, None = ต่อท้ายสุด)"""
        items = self.get_bookmarks()
        entry = {"level": max(1, level), "title": title, "page": page}
        if after is None or after >= len(items):
            items.append(entry)
        else:
            items.insert(after + 1, entry)
        self.set_bookmarks(items)

    def remove_bookmark(self, index: int) -> None:
        items = self.get_bookmarks()
        if 0 <= index < len(items):
            del items[index]
            self.set_bookmarks(items)

    def rename_bookmark(self, index: int, title: str) -> None:
        items = self.get_bookmarks()
        if 0 <= index < len(items):
            items[index]["title"] = title
            self.set_bookmarks(items)

    def move_bookmark_level(self, index: int, delta: int) -> None:
        """เลื่อนระดับ bookmark เข้า/ออก (delta +1 = ย่อยลง, -1 = ขึ้นระดับ)"""
        items = self.get_bookmarks()
        if 0 <= index < len(items):
            new_level = items[index]["level"] + delta
            # ระดับต้องไม่ลึกกว่าตัวก่อนหน้า +1 (กติกาของ PDF TOC)
            max_level = (items[index - 1]["level"] + 1) if index > 0 else 1
            items[index]["level"] = max(1, min(new_level, max_level))
            self.set_bookmarks(items)

    # ---------- ไฮไลต์ข้อความ ----------

    def highlight_rect(
        self,
        page_index: int,
        rect: fitz.Rect,
        color: tuple[float, float, float] = (1.0, 0.92, 0.23),
    ) -> int:
        """ไฮไลต์ข้อความที่อยู่ในกรอบที่ลากคลุม คืนจำนวนคำที่ไฮไลต์"""
        page = self.doc.load_page(page_index)
        area = rect * page.derotation_matrix if page.rotation else rect

        # เก็บ quad ของคำที่กรอบคลุมเกินครึ่ง (กันไฮไลต์คำที่โดนขอบนิดเดียว)
        quads = []
        for w in page.get_text("words"):
            wr = fitz.Rect(w[:4])
            inter = wr & area
            if inter.is_empty or wr.get_area() == 0:
                continue
            if inter.get_area() / wr.get_area() >= 0.4:
                quads.append(wr.quad)

        if not quads:
            return 0

        self.push_undo()
        annot = page.add_highlight_annot(quads=quads)
        annot.set_colors(stroke=color)
        annot.update()
        self.dirty = True
        return len(quads)

    def highlight_search(
        self,
        needle: str,
        color: tuple[float, float, float] = (1.0, 0.92, 0.23),
    ) -> int:
        """ไฮไลต์ทุกคำที่ตรงกับคำค้นทั้งเอกสาร คืนจำนวนจุดที่ไฮไลต์"""
        if not needle.strip():
            return 0
        total = 0
        pushed = False
        for i in range(self.page_count):
            page = self.doc.load_page(i)
            hits = page.search_for(needle)
            if not hits:
                continue
            if not pushed:
                self.push_undo()
                pushed = True
            annot = page.add_highlight_annot(hits)
            annot.set_colors(stroke=color)
            annot.update()
            total += len(hits)
        if total:
            self.dirty = True
        return total

    def remove_highlight_at(self, page_index: int, point: fitz.Point) -> bool:
        """ลบไฮไลต์ที่จุดนั้น (คลิกโดนไฮไลต์แล้วเอาออก)"""
        page = self.doc.load_page(page_index)
        target = point * page.derotation_matrix if page.rotation else point
        for annot in page.annots(types=[fitz.PDF_ANNOT_HIGHLIGHT]):
            if fitz.Rect(annot.rect).contains(target):
                self.push_undo()
                page.delete_annot(annot)
                self.dirty = True
                return True
        return False

    def clear_highlights(self, page_index: int) -> int:
        """ลบไฮไลต์ทั้งหมดในหน้านั้น"""
        page = self.doc.load_page(page_index)
        annots = [a for a in page.annots(types=[fitz.PDF_ANNOT_HIGHLIGHT])]
        if not annots:
            return 0
        self.push_undo()
        for annot in annots:
            page.delete_annot(annot)
        self.dirty = True
        return len(annots)

    # ---------- แบบฟอร์ม PDF (AcroForm) ----------

    def is_form(self) -> bool:
        """ไฟล์นี้มีช่องกรอกแบบฟอร์มไหม"""
        return bool(self.doc.is_form_pdf)

    def form_fields(self) -> list[dict]:
        """รายการช่องกรอกทั้งหมด — แต่ละช่องคืน page/name/xref/ประเภท/ค่า/ตัวเลือก"""
        fields: list[dict] = []
        for i in range(self.page_count):
            for w in self.doc.load_page(i).widgets():
                fields.append({
                    "page": i,
                    "name": w.field_name or "",
                    "label": w.field_label or w.field_name or "",
                    "xref": w.xref,
                    "type": w.field_type,
                    "type_str": w.field_type_string,
                    "value": w.field_value,
                    "rect": fitz.Rect(w.rect),
                    "choices": list(w.choice_values) if w.choice_values else [],
                })
        return fields

    def set_form_field(self, page_index: int, xref: int, value) -> bool:
        """ตั้งค่าช่องกรอกตาม xref คืน True ถ้าตั้งได้"""
        self.push_undo()
        for w in self.doc.load_page(page_index).widgets():
            if w.xref == xref:
                if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                    w.field_value = bool(value)
                else:
                    w.field_value = value
                w.update()
                self.dirty = True
                return True
        # ไม่เจอ widget — ยกเลิก snapshot ที่เพิ่งเก็บ
        self._undo.pop()
        return False

    def set_form_fields(self, updates: list[tuple[int, int, object]]) -> int:
        """ตั้งหลายช่องพร้อมกัน (undo ครั้งเดียว) — updates = [(page, xref, value), ...]"""
        if not updates:
            return 0
        self.push_undo()
        count = 0
        by_page: dict[int, dict[int, object]] = {}
        for page, xref, value in updates:
            by_page.setdefault(page, {})[xref] = value
        for page_index, xref_map in by_page.items():
            for w in self.doc.load_page(page_index).widgets():
                if w.xref in xref_map:
                    value = xref_map[w.xref]
                    if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                        w.field_value = bool(value)
                    else:
                        w.field_value = value
                    w.update()
                    count += 1
        if count:
            self.dirty = True
        else:
            self._undo.pop()
        return count

    def flatten_form(self) -> None:
        """ตรึงค่าฟอร์มให้เป็นเนื้อหาถาวร (แก้ต่อไม่ได้ แต่เปิดที่ไหนก็เห็นเหมือนกัน)"""
        self.push_undo()
        self.doc.bake()  # PyMuPDF: แปลง widget เป็นเนื้อหาหน้า แล้วเอา field ออก
        self.dirty = True

    def fill_form_flatten(self, updates: list[tuple[int, int, object]]) -> int:
        """กรอกฟอร์มโดยวาดค่าเป็นเนื้อหาถาวร (รองรับภาษาไทยแน่นอน แต่แก้ต่อไม่ได้)

        เหมาะกับภาษาไทย เพราะช่องฟอร์มมาตรฐานใช้ฟอนต์ Helvetica ที่ไม่มีสระ/วรรณยุกต์ไทย
        """
        if not updates:
            return 0
        self.push_undo()
        count = 0
        by_page: dict[int, dict[int, object]] = {}
        for page, xref, value in updates:
            by_page.setdefault(page, {})[xref] = value

        for page_index, xref_map in by_page.items():
            page = self.doc.load_page(page_index)
            for w in page.widgets():
                if w.xref not in xref_map:
                    continue
                value = xref_map[w.xref]
                rect = fitz.Rect(w.rect)
                if w.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                    if value:  # ติ๊กถูกกลางช่อง
                        size = min(rect.width, rect.height) * 1.1
                        box = TextBox(page_index, rect, "X",
                                      font_size=size, color=(0, 0, 0))
                        self._draw_textbox(page, box)
                        count += 1
                else:
                    text = str(value)
                    if text.strip():
                        # จัดข้อความให้อยู่กลางแนวตั้งของช่อง
                        size = min(max(rect.height * 0.7, 8), 14)
                        pad = fitz.Rect(rect.x0 + 2, rect.y0, rect.x1, rect.y1)
                        self._draw_textbox(page, TextBox(page_index, pad, text, font_size=size))
                        count += 1

        self.doc.bake()  # เอา widget เปล่าออก เหลือแต่ข้อความที่เราวาด
        if count:
            self.dirty = True
        else:
            self._undo.pop()
        return count

    # ---------- OCR (อ่านข้อความจากไฟล์สแกน) ----------

    def needs_ocr(self, index: int) -> bool:
        """หน้านี้เป็นภาพสแกนหรือเปล่า (แทบไม่มีข้อความให้เลือกได้)"""
        return len(self.page_text(index).strip()) < 20

    def ocr_text(self, index: int, language: str = "tha+eng", dpi: int = 300) -> str:
        """อ่านข้อความจากหน้าที่เป็นรูป คืนเป็นข้อความ"""
        ensure_tesseract()
        page = self.doc.load_page(index)
        textpage = page.get_textpage_ocr(
            flags=0, language=language, dpi=dpi, full=True, tessdata=tessdata_dir()
        )
        return page.get_text(textpage=textpage)

    def ocr_to_searchable(
        self,
        target: str | Path,
        indexes: list[int] | None = None,
        language: str = "tha+eng",
        dpi: int = 300,
        progress=None,
    ) -> Path:
        """สร้าง PDF ใหม่ที่ค้นหา/คัดลอกข้อความได้ (ภาพเดิมคงอยู่ ข้อความซ้อนอยู่ข้างหลัง)"""
        ensure_tesseract()
        indexes = list(range(self.page_count)) if indexes is None else sorted(set(indexes))
        out = fitz.open()
        tess = tessdata_dir()

        for order, i in enumerate(indexes, start=1):
            if progress:
                progress(order, len(indexes))
            page = self.doc.load_page(i)
            pix = page.get_pixmap(dpi=dpi)
            # pdfocr_tobytes คืนหน้า PDF ที่มีข้อความ OCR ซ้อนใต้ภาพ
            ocr_pdf = pix.pdfocr_tobytes(language=language, tessdata=tess)
            with fitz.open("pdf", ocr_pdf) as piece:
                out.insert_pdf(piece)

        out.save(str(target), garbage=3, deflate=True)
        out.close()
        return Path(target)

    # ---------- ตาราง / รูปภาพในไฟล์ ----------

    def find_tables(self, index: int) -> list[list[list[str]]]:
        """หาตารางในหน้านั้น คืนเป็นลิสต์ของตาราง (แต่ละตารางเป็นลิสต์ของแถว)"""
        page = self.doc.load_page(index)
        found = []
        for table in page.find_tables().tables:
            rows = [[(cell if cell is not None else "") for cell in row]
                    for row in table.extract()]
            if rows:
                found.append(rows)
        return found

    def extract_images(self, indexes: list[int], folder: str | Path) -> list[Path]:
        """ดึงรูปที่ฝังอยู่ในไฟล์ออกมาเป็นไฟล์รูป (ไม่ใช่การแปลงหน้าเป็นรูป)"""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        seen: set[int] = set()

        for i in sorted(set(indexes)):
            for order, info in enumerate(self.doc.load_page(i).get_images(full=True), start=1):
                xref = info[0]
                if xref in seen:
                    continue  # รูปเดียวกันใช้ซ้ำหลายหน้า เก็บครั้งเดียวพอ
                seen.add(xref)
                pix = fitz.Pixmap(self.doc, xref)
                if pix.n - pix.alpha >= 4:      # CMYK แปลงเป็น RGB ก่อนบันทึก
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                out = folder / f"หน้า{i + 1}-รูป{order}.png"
                pix.save(str(out))
                written.append(out)
        return written

    # ---------- แปลงเป็น Word / Excel ----------

    def to_word(self, target: str | Path, indexes: list[int] | None = None) -> Path:
        """แปลงเป็น .docx (คงหน้าตา/ตาราง/รูปไว้เท่าที่ทำได้)"""
        import logging

        from pdf2docx import Converter

        # pdf2docx ตั้ง log ไว้ที่ root logger และพ่นทุกหน้า — ปิดชั่วคราวระหว่างแปลง
        root = logging.getLogger()
        previous_level = root.level

        # pdf2docx อ่านจากไฟล์ จึงต้องเขียนสภาพปัจจุบัน (รวมลายเซ็น) ลงไฟล์ชั่วคราวก่อน
        with tempfile.TemporaryDirectory() as work:
            source = Path(work) / "source.pdf"
            snapshot = fitz.open("pdf", self.doc.tobytes())
            self._flatten_stamps(snapshot)
            self._flatten_textboxes(snapshot)
            snapshot.save(str(source))
            snapshot.close()

            root.setLevel(logging.ERROR)
            converter = Converter(str(source))
            try:
                if indexes:
                    converter.convert(str(target), pages=sorted(set(indexes)))
                else:
                    converter.convert(str(target))
            finally:
                converter.close()
                root.setLevel(previous_level)
        return Path(target)

    def to_excel(self, target: str | Path, indexes: list[int] | None = None) -> int:
        """ดึงตารางทุกหน้าออกเป็น .xlsx (1 ตาราง = 1 ชีต) คืนจำนวนตารางที่เจอ"""
        from openpyxl import Workbook

        indexes = list(range(self.page_count)) if indexes is None else sorted(set(indexes))
        book = Workbook()
        book.remove(book.active)
        count = 0

        for i in indexes:
            for order, rows in enumerate(self.find_tables(i), start=1):
                count += 1
                sheet = book.create_sheet(f"หน้า{i + 1}-ตาราง{order}"[:31])
                for row in rows:
                    sheet.append([str(cell).replace("\n", " ") if cell else "" for cell in row])

        if not count:
            raise ValueError(
                "ไม่พบตารางในหน้าที่เลือก\n"
                "(โปรแกรมหาตารางจากเส้นตาราง — ถ้าเป็นไฟล์สแกนหรือตารางไม่มีเส้น จะหาไม่เจอ)"
            )

        book.save(str(target))
        return count

    # ---------- export รูปภาพ ----------

    def export_images(
        self,
        indexes: list[int],
        folder: str | Path,
        dpi: int = 150,
        fmt: str = "jpg",
        stem: str | None = None,
    ) -> list[Path]:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        stem = stem or (self.path.stem if self.path else "page")
        zoom = dpi / 72
        written: list[Path] = []

        # ออกรูปจากสำเนาที่ฝังวัตถุลอยแล้ว ไม่งั้นข้อความ/ลายเซ็นที่เพิ่มไว้จะหายจากรูป
        with self.flattened() as flat:
            for i in sorted(set(indexes)):
                pix = flat.load_page(i).get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                out = folder / f"{stem}-{i + 1:03d}.{fmt}"
                if fmt.lower() in ("jpg", "jpeg"):
                    pix.pil_save(str(out), format="JPEG", quality=90)
                else:
                    pix.save(str(out))
                written.append(out)

        return written


def merge_files(sources: list[str | Path], target: str | Path) -> Path:
    """รวมหลายไฟล์เป็นไฟล์เดียวตามลำดับที่ส่งมา"""
    out = fitz.open()
    for src in sources:
        with fitz.open(str(src)) as doc:
            out.insert_pdf(doc)
    out.save(str(target), garbage=3, deflate=True)
    out.close()
    return Path(target)


def parse_page_ranges(spec: str, total: int) -> list[int]:
    """แปลงข้อความแบบ "1-3,5,8-10" เป็น list ของ index (เริ่มที่ 0)"""
    result: list[int] = []
    for chunk in spec.replace(" ", "").split(","):
        if not chunk:
            continue
        if "-" in chunk:
            lo_s, _, hi_s = chunk.partition("-")
            lo, hi = int(lo_s), int(hi_s)
        else:
            lo = hi = int(chunk)
        if lo < 1 or hi > total or lo > hi:
            raise ValueError(f"ช่วงหน้าไม่ถูกต้อง: {chunk} (เอกสารมี {total} หน้า)")
        result.extend(range(lo - 1, hi))
    if not result:
        raise ValueError("ยังไม่ได้ระบุช่วงหน้า")
    return sorted(set(result))
