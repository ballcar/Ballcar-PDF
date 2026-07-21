"""ฟังก์ชันจัดการ PDF ทั้งหมด — แยกจาก UI เพื่อให้เทสต์/เรียกใช้ซ้ำได้"""
from __future__ import annotations

import math
import os
import tempfile
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


TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR",
    r"C:\Program Files (x86)\Tesseract-OCR",
]


def tesseract_dir() -> Path | None:
    """โฟลเดอร์ที่ติดตั้ง Tesseract (None ถ้ายังไม่ได้ลง)"""
    env = os.environ.get("TESSERACT_DIR")
    candidates = ([env] if env else []) + TESSERACT_CANDIDATES
    for candidate in candidates:
        if candidate and (Path(candidate) / "tesseract.exe").exists():
            return Path(candidate)
    return None


def tessdata_dir() -> str | None:
    folder = tesseract_dir()
    return str(folder / "tessdata") if folder else None


def ocr_languages() -> list[str]:
    """ภาษาที่ติดตั้งไว้ (ดูจากไฟล์ .traineddata)"""
    folder = tesseract_dir()
    if not folder:
        return []
    return sorted(p.stem for p in (folder / "tessdata").glob("*.traineddata"))


def ensure_tesseract() -> None:
    """เช็คว่าพร้อมทำ OCR ไหม ถ้าไม่พร้อมให้ error ที่อธิบายวิธีแก้"""
    if not tesseract_dir():
        raise RuntimeError(
            "ยังไม่ได้ติดตั้งโปรแกรม OCR (Tesseract) ในเครื่องนี้\n\n"
            "ติดตั้งด้วยคำสั่ง:\n"
            "    winget install -e --id UB-Mannheim.TesseractOCR\n\n"
            "แล้วดาวน์โหลดไฟล์ภาษาไทย tha.traineddata ไปไว้ที่\n"
            r"    C:\Program Files\Tesseract-OCR\tessdata\ "
        )
    if "tha" not in ocr_languages():
        raise RuntimeError(
            "ติดตั้ง Tesseract แล้ว แต่ยังไม่มีชุดภาษาไทย\n\n"
            "ดาวน์โหลด tha.traineddata จาก\n"
            "    https://github.com/tesseract-ocr/tessdata\n"
            "ไปวางที่ " + (tessdata_dir() or "")
        )


def find_thai_font() -> str | None:
    """คืนพาธฟอนต์ไทยตัวแรกที่มีในเครื่อง (None ถ้าไม่เจอเลย)"""
    for candidate in THAI_FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


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

    def copy(self) -> "TextBox":
        return TextBox(self.page, fitz.Rect(self.rect), self.text, self.font_size, self.color)


@dataclass
class SearchHit:
    page: int          # index เริ่มที่ 0
    rect: fitz.Rect    # ตำแหน่งคำที่เจอบนหน้า


class PasswordRequired(Exception):
    """ไฟล์ถูกเข้ารหัส ต้องใส่รหัสผ่านก่อนเปิด"""
    def __init__(self, wrong: bool = False):
        super().__init__("ไฟล์นี้มีรหัสผ่าน")
        self.wrong = wrong   # True = ใส่รหัสมาแล้วแต่ผิด


class PdfDocument:
    """ห่อ fitz.Document ให้ใช้ง่ายขึ้น + จำสถานะว่ามีการแก้ไขค้างอยู่ไหม"""

    def __init__(self, path: str | Path | None = None, password: str | None = None):
        self.path: Path | None = Path(path) if path else None
        self.doc = fitz.open(str(path)) if path else fitz.open()
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

    # ---------- undo / redo ----------

    def _snapshot(self) -> tuple:
        return (self.doc.tobytes(), self.dirty,
                [s.copy() for s in self.stamps], [b.copy() for b in self.textboxes])

    def _restore(self, state: tuple) -> None:
        data, dirty, stamps, textboxes = state
        old = self.doc
        self.doc = fitz.open("pdf", data)
        old.close()
        self.dirty = dirty
        self.stamps = [s.copy() for s in stamps]
        self.textboxes = [b.copy() for b in textboxes]
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

        # ลายเซ็น/ข้อความที่ยังลอยอยู่ ต้องฝังลงเอกสารก่อนบันทึก (ฝังแล้วแก้ไม่ได้อีก)
        if self.stamps or self.textboxes:
            self._flatten_stamps(self.doc)
            self._flatten_textboxes(self.doc)
            self.stamps = []
            self.textboxes = []
            # เพิ่งแก้เนื้อหา จึงเขียนทับแบบ incremental ไม่ได้
            if same_file:
                self._in_memory = True

        if same_file and not self._in_memory:
            # เขียนทับไฟล์เดิมต้องใช้ incremental ไม่งั้น PyMuPDF จะปฏิเสธ
            self.doc.save(str(target), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        elif same_file:
            # เอกสารอยู่ในหน่วยความจำ (ผ่าน undo มา) — เขียนไฟล์ชั่วคราวแล้วสลับทับ
            tmp = target.with_suffix(target.suffix + ".tmp")
            self.doc.save(str(tmp), garbage=3, deflate=True)
            self.doc.close()
            tmp.replace(target)
            self.doc = fitz.open(str(target))
            self._in_memory = False
        else:
            self.doc.save(str(target), garbage=3, deflate=True)
            self.path = target

        self.dirty = False
        return target

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
        self.dirty = True

    def insert_pdf(self, at: int, source: str | Path) -> int:
        """แทรกทุกหน้าจากไฟล์อื่นเข้ามาที่ตำแหน่ง at คืนจำนวนหน้าที่แทรก"""
        with fitz.open(str(source)) as src:
            added = src.page_count
            self.push_undo()
            self.doc.insert_pdf(src, start_at=at)
        self.dirty = True
        return added

    def delete_pages(self, indexes: list[int]) -> None:
        if len(indexes) >= self.page_count:
            raise ValueError("ลบทุกหน้าไม่ได้ — เอกสารต้องเหลืออย่างน้อย 1 หน้า")
        self.push_undo()
        # ลบจากท้ายไปหน้า เพื่อไม่ให้ index เลื่อน
        for i in sorted(set(indexes), reverse=True):
            self.doc.delete_page(i)
        self.dirty = True

    def move_page(self, source: int, dest: int) -> None:
        self.push_undo()
        self.doc.move_page(source, dest)
        self.dirty = True

    def rotate_pages(self, indexes: list[int], degrees: int) -> None:
        """หมุนแบบสะสมจากมุมเดิมของหน้านั้น"""
        self.push_undo()
        for i in indexes:
            page = self.doc.load_page(i)
            page.set_rotation((page.rotation + degrees) % 360)
        self.dirty = True

    def reorder_pages(self, order: list[int]) -> None:
        """เรียงหน้าใหม่ทั้งเอกสาร — order คือ index เดิมเรียงตามลำดับใหม่ที่ต้องการ"""
        if sorted(order) != list(range(self.page_count)):
            raise ValueError("ลำดับหน้าใหม่ไม่ครบหรือซ้ำ")
        if order != list(range(self.page_count)):
            self.push_undo()
            self.doc.select(order)
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

    # ---------- เลขหน้า ----------

    def add_page_numbers(
        self,
        fmt: str = "{page}/{total}",
        position: str = "bottom-center",
        font_size: int = 10,
        start_at: int = 1,
        margin: float = 28,
    ) -> None:
        total = self.page_count
        self.push_undo()
        for i in range(total):
            page = self.doc.load_page(i)
            text = fmt.format(page=i + start_at, total=total + start_at - 1)
            rect = page.rect
            width = fitz.get_text_length(text, fontname="helv", fontsize=font_size)

            top = position.startswith("top")
            y = rect.y0 + margin if top else rect.y1 - margin
            if position.endswith("left"):
                x = rect.x0 + margin
            elif position.endswith("right"):
                x = rect.x1 - margin - width
            else:
                x = (rect.width - width) / 2

            page.insert_text((x, y), text, fontname="helv", fontsize=font_size)
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
    ) -> TextBox:
        """เพิ่มกล่องข้อความเป็นชั้นลอย (ยังแก้ไข/ย้าย/ปรับขนาด/ลบได้)"""
        self.push_undo()
        box = TextBox(page, fitz.Rect(rect), text, font_size, color)
        self.textboxes.append(box)
        self.dirty = True
        return box

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
    ) -> None:
        self.push_undo()
        if text is not None:
            box.text = text
        if font_size is not None:
            box.font_size = font_size
        if color is not None:
            box.color = color
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
        """วาดข้อความลงในกล่องบนหน้าจริง (ใช้ทั้งตอน flatten และ export)"""
        if not box.text.strip():
            return
        fontname = "helv"
        fontfile = None
        if _has_thai(box.text):
            fontfile = find_thai_font()
            if not fontfile:
                raise RuntimeError("ไม่พบฟอนต์ภาษาไทยในเครื่อง — ข้อความภาษาไทยจะแสดงไม่ถูกต้อง")
            fontname = "thai"
            page.insert_font(fontname=fontname, fontfile=fontfile)

        target = box.rect * page.derotation_matrix if page.rotation else box.rect
        # insert_textbox จะไม่วาดอะไรเลย (คืนค่าลบ) ถ้าข้อความสูงเกินกล่อง
        # จึงลองขยายกล่องลงล่างจนใส่ได้ (กล่องแคบไปเป็นเรื่องปกติตอนแก้ข้อความเดิม)
        rect = fitz.Rect(target)
        for _ in range(6):
            leftover = page.insert_textbox(
                rect, box.text,
                fontname=fontname, fontfile=fontfile, fontsize=box.font_size,
                color=box.color, align=fitz.TEXT_ALIGN_LEFT,
            )
            if leftover >= 0:
                return
            rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + box.font_size * 1.5)
        # ยังไม่ลง (เช่นข้อความยาวมาก) — วางเป็นบรรทัดเดียวที่เส้นฐาน กันข้อความหาย
        page.insert_text(
            (target.x0, target.y0 + box.font_size),
            box.text.replace("\n", " "),
            fontname=fontname, fontfile=fontfile, fontsize=box.font_size, color=box.color,
        )

    def _flatten_textboxes(self, doc: fitz.Document) -> None:
        for box in self.textboxes:
            if 0 <= box.page < doc.page_count:
                self._draw_textbox(doc.load_page(box.page), box)

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

        for i in sorted(set(indexes)):
            pix = self.render_page(i, zoom)
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
