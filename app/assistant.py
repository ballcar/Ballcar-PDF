"""ผู้ช่วยพิมพ์คำสั่ง — ตีความคำสั่งภาษาไทย/อังกฤษในเครื่อง (ออฟไลน์ ไม่มีค่าใช้จ่าย)

2.0: กฎที่เก่งขึ้น
- ระบุหน้าได้: "ลบหน้า 3-5", "หมุนหน้า 2 ขวา", "ย้ายหน้า 5 ไปหน้าแรก", หน้าคู่/คี่/แรก/สุดท้าย
- สั่งต่อกันได้: "ลบหน้าว่าง แล้วใส่เลขหน้า"
- คำพ้อง: หน้าเปล่า = หน้าว่าง, ตะแคง = แนวนอน, ลดขนาดไฟล์ = บีบอัด ...
- เรียกเครื่องมือในเมนูได้ด้วยชื่อ: "บีบอัดไฟล์", "แปลงเป็น Word", "ตั้งรหัสผ่าน" ...
- ไม่เข้าใจ -> suggest() เดาคำสั่งที่ใกล้เคียงให้เลือก

ตัวเลขหน้า/ข้อความ/คำค้น อ่านด้วยกฎเสมอ (ตรงตามที่พิมพ์ ไม่เดา)
ส่วน "เข้าใจว่าอยากทำอะไร" ต่อ AI จับความหมายได้ทีหลังผ่าน set_matcher()
คำสั่งที่ต้องใช้ AI ออนไลน์ (แปล/สรุป) คืน intent พิเศษเพื่อบอกผู้ใช้ว่าไม่รวม
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field


@dataclass
class Intent:
    action: str                       # คีย์งานที่จะทำ
    params: dict = field(default_factory=dict)
    preview: str = ""                 # ข้อความอธิบายว่าจะทำอะไร (ให้ผู้ใช้ยืนยัน)
    needs_online_ai: bool = False     # True = ต้องใช้บริการ AI ออนไลน์ (มีค่าใช้จ่าย)


def _has(text: str, *words: str) -> bool:
    return any(w in text for w in words)


# ---------- ปรับข้อความก่อนตีความ ----------

_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")

# คำพ้อง -> คำมาตรฐานที่กฎรู้จัก (ใช้กับข้อความสำหรับจับคำ ไม่แตะข้อความในเครื่องหมายคำพูด)
_SYNONYMS = [
    (r"หน้าเปล่า|หน้าขาว|หน้าไม่มีอะไร", "หน้าว่าง"),
    (r"ตะแคง", "แนวนอน"),
    (r"ทวนเข็ม(?:นาฬิกา)?", "ซ้าย"),
    (r"ตามเข็ม(?:นาฬิกา)?", "ขวา"),
    (r"กลับหัว", "180"),
    (r"ลดขนาดไฟล์|ย่อขนาดไฟล์|ย่อไฟล์|ทำให้ไฟล์เล็ก(?:ลง)?|ไฟล์ใหญ่ไป", "บีบอัด"),
    (r"เวิร์ด|เวิด|เวิร์ค", "word"),
    (r"เอ็กเซลล์|เอ็กเซล|เอ็กซ์เซล", "excel"),
    (r"ลบทิ้ง|ทิ้ง|เอาออก|ไม่เอา|ไม่ต้องเอา|ตัดออก", "ลบ"),
    (r"ล็อ[กค](?:ไฟล์)?|ใส่รหัส|ตั้งรหัส|ใส่พาสเวิร์ด", "ตั้งรหัสผ่าน"),
    (r"ปริ๊?้?น(?:ท์|ต์)?", "พิมพ์"),
    (r"ปลดล็อก|เอารหัสออก|ปลดรหัส|ถอดรหัส", "ลบรหัสผ่าน"),
    (r"รวมไฟล์|รวม pdf|รวมหลายไฟล์|merge", "รวมไฟล์"),
    (r"สแกนเป็นข้อความ|อ่านตัวหนังสือ", "ocr"),
]


def normalize(command: str) -> str:
    """ตัวพิมพ์เล็ก เลขไทยเป็นเลขอารบิก และแทนคำพ้องเป็นคำมาตรฐาน"""
    c = command.strip().lower().translate(_THAI_DIGITS)
    for pattern, standard in _SYNONYMS:
        c = re.sub(pattern, standard, c)
    return re.sub(r"\s+", " ", c)


# ---------- ระบุหน้า ----------

_NUM_LIST = r"\d+(?:\s*(?:-|–|ถึง|to)\s*\d+)?(?:\s*(?:,|และ|กับ|and)\s*\d+(?:\s*(?:-|–|ถึง|to)\s*\d+)?)*"


def page_spec(c: str) -> str | None:
    """หาว่าคำสั่งระบุหน้าไหน คืน "3-5,7" / "first" / "last" / "odd" / "even" หรือ None

    c ต้องผ่าน normalize() แล้ว
    """
    if re.search(r"หน้าแรก|first page", c):
        return "first"
    if re.search(r"หน้าสุดท้าย|หน้าท้ายสุด|last page", c):
        return "last"
    if re.search(r"หน้าคี่|odd pages?", c):
        return "odd"
    if re.search(r"หน้าคู่|even pages?", c):
        return "even"
    m = re.search(r"(?:หน้า(?:ที่)?|pages?|p\.?)\s*(" + _NUM_LIST + ")", c)
    if not m:
        return None
    spec = m.group(1)
    spec = re.sub(r"\s*(?:–|ถึง|to)\s*", "-", spec)
    spec = re.sub(r"\s*(?:และ|กับ|and)\s*", ",", spec)
    return re.sub(r"\s+", "", spec)


def resolve_pages(spec: str | None, total: int) -> list[int]:
    """แปลงผลจาก page_spec เป็น index (เริ่ม 0) — None = ทุกหน้า"""
    if total <= 0:
        return []
    if spec is None:
        return list(range(total))
    if spec == "first":
        return [0]
    if spec == "last":
        return [total - 1]
    if spec == "odd":
        return list(range(0, total, 2))
    if spec == "even":
        return list(range(1, total, 2))
    pages: list[int] = []
    for chunk in spec.split(","):
        if not chunk:
            continue
        lo_s, _, hi_s = chunk.partition("-")
        lo, hi = int(lo_s), int(hi_s or lo_s)
        if lo > hi:
            lo, hi = hi, lo
        if lo < 1 or hi > total:
            raise ValueError(f"ไม่มีหน้า {chunk} — เอกสารนี้มี {total} หน้า")
        pages.extend(range(lo - 1, hi))
    return sorted(set(pages))


def describe_pages(spec: str | None) -> str:
    """ข้อความบอกหน้าสำหรับแสดงในตัวอย่างคำสั่ง"""
    return {None: "ทุกหน้า", "first": "หน้าแรก", "last": "หน้าสุดท้าย",
            "odd": "หน้าคี่", "even": "หน้าคู่"}.get(spec) or f"หน้า {spec.replace(',', ', ')}"


# ---------- ตีความ ----------

def parse(command: str) -> Intent | None:
    """ตีความคำสั่งเดียว คืน Intent หรือ None ถ้าไม่เข้าใจ"""
    intent = _parse_rules(command)
    if intent is None and _matcher is not None and command.strip():
        intent = _parse_with_matcher(command)
    return intent


def parse_all(command: str) -> list[Intent] | None:
    """ตีความคำสั่งที่อาจสั่งต่อกันหลายอย่าง ("ลบหน้าว่าง แล้วใส่เลขหน้า")

    คืนรายการ intent ตามลำดับ หรือ None ถ้ามีส่วนไหนไม่เข้าใจ (ไม่ทำครึ่งๆ กลางๆ)
    """
    parts = split_commands(command)
    if len(parts) <= 1:
        whole = parse(command)
        return [whole] if whole else None
    # ทุกส่วนต้องเข้าใจ — ไม่งั้นไม่ทำเลย (ทำแค่ส่วนที่เข้าใจ ผู้ใช้จะคิดว่าทำครบแล้ว)
    intents = [parse(p) for p in parts]
    return intents if all(intents) else None


def split_commands(command: str) -> list[str]:
    """แยกคำสั่งที่สั่งต่อกันด้วย "แล้ว", "จากนั้น", "then", ";" (เครื่องหมายคำพูดไม่ถูกแยก)"""
    parts, quoted = [], re.split(r'(["“][^"”]*["”])', command)
    current = ""
    for piece in quoted:
        if piece.startswith(('"', "“")):
            current += piece
            continue
        chunks = re.split(r"\s*(?:แล้ว(?:ก็)?(?=\s*\S)|จากนั้น(?:ก็)?|ต่อด้วย|;|\bthen\b)\s*", piece)
        current += chunks[0]
        for chunk in chunks[1:]:
            parts.append(current)
            current = chunk
    parts.append(current)
    return [p.strip(" ,") for p in parts if p.strip(" ,")]


def _quoted(command: str) -> str | None:
    m = re.search(r'["“]([^"”]+)["”]', command)
    return m.group(1).strip() if m else None


# เครื่องมือในเมนูที่เรียกด้วยชื่อได้ (เปิดหน้าต่างของเครื่องมือนั้น — ให้ผู้ใช้เลือกที่บันทึก/ตัวเลือกเอง)
# (คำที่ต้องมี, ชื่อเมธอดของหน้าต่างหลัก, ข้อความตัวอย่าง)
_TOOLS = [
    (("ลบรหัสผ่าน",), "password_dialog", "เปิดหน้าต่างรหัสผ่าน (ลบรหัสผ่าน)"),
    (("ตั้งรหัสผ่าน", "รหัสผ่าน", "password"), "password_dialog", "เปิดหน้าต่างตั้งรหัสผ่าน PDF"),
    (("บีบอัด", "compress"), "compress_dialog", "เปิดหน้าต่างบีบอัดลดขนาดไฟล์"),
    (("word", "docx"), "export_word", "แปลงเป็นไฟล์ Word"),
    (("excel", "xlsx", "ตาราง"), "export_excel", "ดึงตารางเป็นไฟล์ Excel"),
    (("ดึงรูป", "รูปในไฟล์", "รูปภาพในไฟล์"), "export_embedded_images", "ดึงรูปภาพที่อยู่ในไฟล์ออกมา"),
    (("เป็นรูป", "jpg", "png", "บันทึกหน้าเป็นภาพ"), "export_images_dialog", "บันทึกหน้าเป็นไฟล์รูป"),
    (("ดึงข้อความ", "คัดลอกข้อความทั้งไฟล์", "extract text"), "extract_all_text",
     "ดึงข้อความทั้งไฟล์"),
    (("รวมไฟล์",), "merge_dialog", "เปิดหน้าต่างรวมไฟล์ PDF"),
    (("แยกไฟล์", "split"), "split_dialog", "เปิดหน้าต่างแยกไฟล์ตามช่วงหน้า"),
    (("กรอกฟอร์ม", "แบบฟอร์ม", "form"), "fill_form_dialog", "เปิดหน้าต่างกรอกแบบฟอร์ม"),
    # 2.2-2.3: เครื่องมือใหม่ (คำเฉพาะเจาะจงต้องมาก่อนคำกว้างอย่าง "ลายเซ็น")
    (("วาดลายเซ็น", "เซ็นด้วยเมาส์", "draw signature"), "draw_signature", "เปิดหน้าต่างวาดลายเซ็น"),
    (("ครอปลายเซ็น", "ตัดลายเซ็น", "เก็บลายเซ็นจากเอกสาร"), "capture_signature_mode",
     "ครอปลายเซ็นจากเอกสารเก็บเข้าคลัง"),
    (("ตรายาง", "ประทับตรา", "stamp"), "stamp_dialog", "เปิดหน้าต่างตรายาง (อนุมัติ / ได้รับแล้ว)"),
    (("เปรียบเทียบ", "เทียบไฟล์", "compare"), "compare_dialog", "เปรียบเทียบเอกสารสองฉบับ"),
    (("ปิดทับคำ", "ซ่อนเลข", "ซ่อนคำ", "redact"), "cover_text_dialog", "ปิดทับคำที่ค้นหาทุกหน้า"),
    (("คำแก้ ocr", "แก้คำ ocr"), "ocr_fixes_dialog", "เปิดตารางคำแก้ OCR ภาษาไทย"),
    (("โน้ต", "note", "แปะข้อความ"), "add_note_mode", "เพิ่มโน้ต (คลิกจุดบนหน้า)"),
    (("ตั้งค่า", "settings"), "settings_dialog", "เปิดหน้าตั้งค่า"),
    (("ล้างสคริปต์", "สคริปต์", "javascript", "ไวรัส"), "remove_risks",
     "ล้าง JavaScript / ไฟล์แนบออกจากไฟล์"),
    (("ลายเซ็น", "เซ็นชื่อ", "เซ็น", "ตราประทับ", "signature"), "signature_dialog",
     "ใส่ลายเซ็น / ตราประทับ"),
    (("ลายน้ำ", "watermark"), "watermark_dialog", "เปิดหน้าต่างใส่ลายน้ำ"),
    (("ครอบตัด", "crop"), "crop_dialog", "เปิดหน้าต่างครอบตัดหน้า"),
    (("batch", "หลายไฟล์"), "batch_dialog", "เปิดหน้าต่างประมวลผลหลายไฟล์"),
]


def _parse_rules(command: str) -> Intent | None:
    raw = command.strip()
    c = normalize(raw)
    if not c:
        return None
    quoted = _quoted(raw)
    pages = page_spec(c)

    # ---- ต้องใช้ AI ออนไลน์ (มีค่าใช้จ่าย) — บอกตรงๆ ว่าไม่รวม ----
    if _has(c, "แปล", "translate") and not _has(c, "แปลงเป็น", "แปลง"):
        return Intent("needs_ai", preview="การแปลเอกสารต้องใช้บริการ AI ออนไลน์",
                      needs_online_ai=True)
    if _has(c, "สรุป", "summariz", "summary"):
        return Intent("needs_ai", preview="การสรุปเอกสารต้องใช้บริการ AI ออนไลน์",
                      needs_online_ai=True)

    # ---- ลบหน้าว่าง ----
    if _has(c, "ลบ", "เอา", "ออก", "remove", "delete", "clear") and        _has(c, "หน้าว่าง", "ว่าง", "blank", "empty"):
        return Intent("delete_blank", preview="ลบหน้าว่างทั้งหมด")

    # ---- ลบข้อมูลส่วนบุคคล ----
    if _has(c, "ลบ", "ปิด", "ซ่อน", "remove", "redact") and \
       _has(c, "ส่วนบุคคล", "ส่วนตัว", "personal", "pii", "ข้อมูลลับ"):
        return Intent("redact_pii",
                      preview="ปิดทับข้อมูลส่วนบุคคล (เบอร์โทร/อีเมล/เลขบัตรประชาชน/เลขบัตรเครดิต)")

    # ---- ใส่ลายน้ำ "X" ----
    if _has(c, "ลายน้ำ", "watermark") and quoted:
        return Intent("watermark", {"text": quoted}, preview=f'ใส่ลายน้ำข้อความ "{quoted}"')

    # ---- แทรกหน้าว่าง (ก่อน/หลังหน้า N) ----
    if _has(c, "แทรก", "เพิ่ม", "insert", "add") and _has(c, "หน้าว่าง", "blank page"):
        m = re.search(r"(ก่อน|หลัง|before|after)\s*หน้า(?:ที่)?\s*(\d+)", c)
        if m:
            n = int(m.group(2))
            at = n - 1 if m.group(1) in ("ก่อน", "before") else n
            where = f"{m.group(1)}หน้า {n}"
        elif pages == "first":
            at, where = 0, "เป็นหน้าแรก"
        else:
            at, where = None, "ต่อท้ายเอกสาร"
        return Intent("insert_blank", {"at": at}, preview=f"แทรกหน้าว่าง {where}")

    # ---- ย้ายหน้า X ไปหน้า Y / หน้าแรก / ท้ายสุด ----
    m = re.search(r"(?:ย้าย|move)\s*หน้า(?:ที่)?\s*(\d+)\s*(?:ไป(?:ไว้|อยู่|เป็น)?|to)\s*(.*)", c)
    if m:
        source = int(m.group(1))
        dest_text = m.group(2)
        if re.search(r"แรก|first|บนสุด", dest_text):
            dest, where = 1, "หน้าแรก"
        elif re.search(r"ท้าย|สุดท้าย|last|ล่างสุด", dest_text):
            dest, where = -1, "หน้าสุดท้าย"
        else:
            d = re.search(r"(\d+)", dest_text)
            if not d:
                return None
            dest, where = int(d.group(1)), f"ตำแหน่งหน้า {d.group(1)}"
        return Intent("move_page", {"source": source, "dest": dest},
                      preview=f"ย้ายหน้า {source} ไป{where}")

    # ---- หมุน (ทุกหน้า หรือเฉพาะหน้าที่ระบุ) ----
    if _has(c, "หมุน", "rotate"):
        scope = describe_pages(pages)
        if _has(c, "แนวนอน", "นอน", "landscape"):
            return Intent("orientation", {"orientation": "landscape", "pages": pages},
                          preview=f"หมุน{scope} ให้เป็นแนวนอน")
        if _has(c, "แนวตั้ง", "ตั้ง", "portrait"):
            return Intent("orientation", {"orientation": "portrait", "pages": pages},
                          preview=f"หมุน{scope} ให้เป็นแนวตั้ง")
        if _has(c, "ซ้าย", "left"):
            return Intent("rotate", {"degrees": -90, "pages": pages},
                          preview=f"หมุน{scope} ไปทางซ้าย 90°")
        if "180" in c:
            return Intent("rotate", {"degrees": 180, "pages": pages}, preview=f"หมุน{scope} 180°")
        if _has(c, "ขวา", "right") or pages:
            return Intent("rotate", {"degrees": 90, "pages": pages},
                          preview=f"หมุน{scope} ไปทางขวา 90°")

    # ---- แยกทีละหน้า (หน้าละไฟล์) ----
    if _has(c, "แยก", "split") and _has(c, "ทีละหน้า", "หน้าละไฟล์", "ละหน้า", "each page"):
        return Intent("split_each", preview="แยกเป็นไฟล์ละ 1 หน้า (เลือกโฟลเดอร์ที่จะเก็บ)")

    # ---- ดึง/แยกหน้าที่ระบุออกเป็นไฟล์ใหม่ (ต้องมาก่อน "ดึงเฉพาะหน้าที่มีคำว่า") ----
    if pages and _has(c, "แยก", "ดึง", "บันทึก", "save", "extract") and \
       not _has(c, "คำว่า", "ที่มี") and not quoted:
        return Intent("extract_pages", {"pages": pages},
                      preview=f"บันทึก{describe_pages(pages)} เป็นไฟล์ใหม่ (ไฟล์เดิมไม่เปลี่ยน)")

    # ---- ลบหน้าที่ระบุ ----
    if pages and _has(c, "ลบ", "remove", "delete"):
        return Intent("delete_pages", {"pages": pages}, preview=f"ลบ{describe_pages(pages)}")

    # ---- เลขหน้า ----
    if _has(c, "เลขหน้า", "page number", "หมายเลขหน้า", "ใส่เลข"):
        params: dict = {"numeral": "arabic"}
        what = "ใส่เลขหน้า"
        if _has(c, "โรมัน", "roman"):
            params["numeral"] = "roman-lower" if _has(c, "เล็ก", "lower") else "roman"
            what = "ใส่เลขหน้าแบบเลขโรมัน"
        m = re.search(r"เริ่ม(?:ที่|ตั้งแต่)?\s*หน้า(?:ที่)?\s*(\d+)", c)
        if m:
            params["first_page"] = int(m.group(1))
            what += f" เริ่มที่หน้า {m.group(1)}"
        m = re.search(r"(?:เริ่ม(?:ที่|จาก)?\s*เลข|เลขเริ่มต้น)\s*(\d+)", c)
        if m:
            params["start_at"] = int(m.group(1))
            what += f" (เริ่มนับจากเลข {m.group(1)})"
        return Intent("page_numbers", params, preview=what)

    # ---- OCR ----
    if "ocr" in c or (_has(c, "อ่าน", "แปลงข้อความ") and _has(c, "สแกน", "รูป", "ภาพ")):
        return Intent("ocr", preview="ทำ OCR อ่านข้อความทุกหน้า (ไฟล์สแกน)")

    # ---- ดึง/เก็บเฉพาะหน้าที่มีคำว่า X ----
    m = re.search(r'(?:ดึง|เก็บ|เอาเฉพาะ|extract|keep)[^"“]*["“]([^"”]+)["”]', raw)
    if not m:
        m = re.search(r'(?:ดึง|เก็บ|เอา)(?:ไว้)?\s*(?:เฉพาะ)?\s*(?:หน้า(?:ที่มี)?)?\s*(?:คำว่า)?\s*'
                      r'([^\s].{0,40})$', raw)
    # ไม่มีเครื่องหมายคำพูด ต้องมี "หน้าที่มี/คำว่า/เฉพาะ" ด้วย
    # (ไม่งั้น "ดึงตารางเป็น Excel" จะกลายเป็น "เก็บหน้าที่มีคำว่า ตารางเป็น Excel")
    if m and _has(c, "ดึง", "เก็บ", "เฉพาะ", "extract", "keep") and        (quoted or _has(c, "หน้าที่มี", "คำว่า", "เฉพาะ")):
        keyword = m.group(1).strip().strip('"“”')
        if keyword:
            return Intent("keep_matching", {"keyword": keyword},
                          preview=f'เก็บไว้เฉพาะหน้าที่มีคำว่า "{keyword}" (ลบหน้าอื่น)')

    # ---- ใส่ข้อความ "ต่อท้ายป้าย" ที่มีในเอกสาร เช่น 'ใส่วันที่หลัง Date' ----
    # อ้างตำแหน่งจากป้ายในเอกสารเอง จึงตรงช่องทุกหน้าโดยไม่ต้องวางต้นแบบไว้ก่อน
    if re.search(r'หลัง|ต่อจาก|after|ข้าง', raw, re.I):
        rest = raw
        date_text = None
        m = re.search(r'(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})', rest)
        if m:
            date_text = m.group(1)
            rest = rest.replace(date_text, " ")
        # ข้อความในเครื่องหมายคำพูดมาก่อนวันที่ (ผู้ใช้อาจอยากใส่คำอื่น)
        q = re.search(r'["“]([^"”]+)["”]', rest)
        if q:
            date_text = q.group(1).strip()
            rest = rest.replace(q.group(0), " ")
        rest = re.sub(r'ทุกหน้า|all pages?|every page', " ", rest, flags=re.I)
        m = re.search(r'(?:หลัง(?:คำว่า)?|ต่อจาก|ข้าง|after)\s*(.+)', rest, re.I)
        if m:
            label = m.group(1).strip().strip('"“”:：').strip()
            # ตัดคำลงท้ายที่ไม่ใช่ชื่อป้าย
            label = re.sub(r'(?:\s*(?:ให้|ด้วย|หน่อย|ครับ|ค่ะ|คะ|นะ|เลย|ที))+\s*$', "",
                           label).strip()
            if label and len(label) <= 40:
                shown = date_text or "วันที่วันนี้"
                return Intent("text_after_label", {"label": label, "text": date_text},
                              preview=f'ใส่ "{shown}" ต่อท้ายคำว่า "{label}" '
                                      f'ในทุกหน้าที่พบคำนี้')

    # ---- ใส่วันที่/ข้อความเดิม ตำแหน่งเดียวกันทุกหน้า ----
    # ใช้ตำแหน่งของกล่องข้อความที่เลือกอยู่เป็นต้นแบบ (ผู้ใช้วางไว้หน้าหนึ่งก่อน)
    if _has(c, "ทุกหน้า", "all page", "every page"):
        if _has(c, "วันที่", "วันนี้", "date"):
            m = re.search(r'(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})', raw)
            params = {"text": m.group(1)} if m else {}
            shown = m.group(1) if m else "วันที่วันนี้"
            return Intent("text_all_pages", params,
                          preview=f'ใส่ "{shown}" ตำแหน่งเดียวกันทุกหน้า '
                                  f'(ใช้ตำแหน่งของข้อความที่เลือกอยู่)')
        if quoted and _has(c, "ใส่", "เพิ่ม", "add", "put"):
            return Intent("text_all_pages", {"text": quoted},
                          preview=f'ใส่ "{quoted}" ตำแหน่งเดียวกันทุกหน้า '
                                  f'(ใช้ตำแหน่งของข้อความที่เลือกอยู่)')

    # ---- พิมพ์ ----
    if re.match(r"^(?:สั่ง)?พิมพ์(?:เอกสาร|ไฟล์|ออก|ให้|หน่อย|นี้)*(?:\s|$)|^print\b", c):
        return Intent("open_tool", {"method": "print_document"}, preview="เปิดหน้าต่างพิมพ์เอกสาร")

    # ---- เรียกเครื่องมือในเมนูด้วยชื่อ ----
    for words, method, preview in _TOOLS:
        if _has(c, *words):
            return Intent("open_tool", {"method": method}, preview=preview)

    return None


# ---------- เดาคำสั่งที่ใกล้เคียง / AI จับความหมาย ----------

# คำสั่งแม่แบบ (ใช้ทั้งเป็นตัวอย่าง เดาคำสั่งใกล้เคียง และให้ AI เทียบความหมาย)
TEMPLATES = [
    "ลบหน้าว่างทั้งหมด", "ลบหน้า 3", "หมุนทุกหน้าแนวนอน", "หมุนหน้า 2 ไปทางขวา",
    "หมุนทุกหน้า 180", "ย้ายหน้า 5 ไปหน้าแรก", "แทรกหน้าว่างหลังหน้า 3",
    "แยกหน้า 1-3 เป็นไฟล์ใหม่", "แยกไฟล์ทีละหน้า", "ใส่เลขหน้า", "ใส่เลขหน้าเป็นเลขโรมัน",
    "ใส่เลขหน้าเริ่มที่หน้า 3", "OCR ทุกหน้า", "ลบข้อมูลส่วนบุคคล", 'ใส่ลายน้ำ "สำเนา"',
    'ดึงเฉพาะหน้าที่มีคำว่า "ใบเสนอราคา"', "ใส่วันที่หลัง Date", "บีบอัดไฟล์",
    "แปลงเป็น Word", "ดึงตารางเป็น Excel", "บันทึกหน้าเป็นรูป", "ดึงข้อความทั้งไฟล์",
    "ตั้งรหัสผ่าน", "ลบรหัสผ่าน", "รวมไฟล์", "พิมพ์", "ใส่ลายเซ็น", "กรอกแบบฟอร์ม",
]

# คำสั่งตัวอย่างที่โชว์ในหน้าต่างผู้ช่วย
EXAMPLES = [
    "ลบหน้าว่างทั้งหมด",
    "ลบหน้า 3-5",
    "หมุนหน้า 2 ไปทางขวา",
    "ย้ายหน้า 5 ไปหน้าแรก",
    "แยกหน้า 1-3 เป็นไฟล์ใหม่",
    "ใส่เลขหน้าเริ่มที่หน้า 3",
    'ดึงเฉพาะหน้าที่มีคำว่า "ใบเสนอราคา"',
    'ใส่ลายน้ำ "สำเนา"',
    "ลบหน้าว่าง แล้วใส่เลขหน้า",
    "บีบอัดไฟล์  ·  แปลงเป็น Word  ·  ตั้งรหัสผ่าน",
    "ใส่วันที่หลัง Date        (ทุกหน้าที่มีคำว่า Date)",
    "ใส่วันที่ทุกหน้า          (วางข้อความไว้หน้าหนึ่งก่อน แล้วคลิกเลือก)",
]

_matcher = None


def set_matcher(matcher) -> None:
    """ต่อ AI จับความหมาย: matcher(ข้อความ) -> [(แม่แบบใน TEMPLATES, คะแนน 0..1), ...]
    (ไม่ต่อ = ใช้กฎอย่างเดียว ทำงานได้ปกติ)"""
    global _matcher
    _matcher = matcher


def has_matcher() -> bool:
    return _matcher is not None


# AI ทำเองได้เฉพาะคะแนน >= เกณฑ์นี้ (วัดแล้ว: 0.80 ไม่ทำผิดงานเลย ต่ำกว่านี้เริ่มสับสน)
# ต่ำกว่าเกณฑ์ -> suggest() เสนอเป็นตัวเลือกให้ผู้ใช้กดเอง
MATCH_THRESHOLD = 0.80


def _parse_with_matcher(command: str, threshold: float = MATCH_THRESHOLD) -> Intent | None:
    """กฎไม่เข้าใจ -> ให้ AI หาแม่แบบที่ความหมายใกล้ที่สุด แล้วตีความแม่แบบนั้นด้วยกฎ
    (เลขหน้า/ข้อความจากคำสั่งจริงต่อท้ายไปด้วย ไม่ใช้เลขในแม่แบบ)"""
    try:
        best = _matcher(command)
    except Exception:
        return None
    if not best or best[0][1] < threshold:
        return None
    template = re.sub(r"\s*\d+(?:-\d+)?\s*", " ", best[0][0]).strip()
    quoted = _quoted(command)
    template = re.sub(r'["“][^"”]*["”]', f'"{quoted}"' if quoted else "", template).strip()
    spec = page_spec(normalize(command))
    if spec and spec not in ("first", "last", "odd", "even"):
        template += f" หน้า {spec}"
    return _parse_rules(template)


def suggest(command: str, limit: int = 3) -> list[str]:
    """เดาคำสั่งที่ใกล้เคียง (ใช้ตอนไม่เข้าใจ) — ใช้ AI ถ้ามี ไม่งั้นเทียบตัวอักษร"""
    c = normalize(command)
    if not c:
        return []
    if _matcher is not None:
        try:
            # เสนอเฉพาะที่ใกล้พอสมควร (คำที่ไม่เกี่ยวเลย เช่น "ขอบคุณ" ไม่ต้องเสนออะไร)
            ranked = [t for t, score in _matcher(command) if score >= 0.6]
            return ranked[:limit]          # AI บอกว่าไม่ใกล้อะไรเลย = ไม่เสนอ (ไม่เดามั่ว)
        except Exception:
            pass                           # AI พัง -> เทียบตัวอักษรแทน
    scored = sorted(TEMPLATES, reverse=True,
                    key=lambda t: difflib.SequenceMatcher(None, c, normalize(t)).ratio())
    return [t for t in scored[:limit]
            if difflib.SequenceMatcher(None, c, normalize(t)).ratio() >= 0.3]
