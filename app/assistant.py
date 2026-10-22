"""ผู้ช่วยพิมพ์คำสั่ง — ตีความคำสั่งภาษาไทย/อังกฤษในเครื่อง (ออฟไลน์ ไม่มีค่าใช้จ่าย)

ไม่ใช้ AI ออนไลน์ — ใช้การจับคู่คำ/รูปแบบ แล้ว map ไปยังฟังก์ชันของ PdfDocument
คำสั่งที่ต้องใช้ AI จริง (แปล/สรุป) จะคืน intent พิเศษเพื่อบอกผู้ใช้ว่าไม่รวมในเวอร์ชันนี้
"""
from __future__ import annotations

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


def parse(command: str) -> Intent | None:
    """ตีความคำสั่ง คืน Intent หรือ None ถ้าไม่เข้าใจ"""
    c = command.strip().lower()
    if not c:
        return None

    # ---- ต้องใช้ AI ออนไลน์ (มีค่าใช้จ่าย) — บอกตรงๆ ว่าไม่รวม ----
    if _has(c, "แปล", "translate"):
        return Intent("needs_ai", preview="การแปลเอกสารต้องใช้บริการ AI ออนไลน์",
                      needs_online_ai=True)
    if _has(c, "สรุป", "summariz", "summary"):
        return Intent("needs_ai", preview="การสรุปเอกสารต้องใช้บริการ AI ออนไลน์",
                      needs_online_ai=True)

    # ---- ลบหน้าว่าง ----
    if _has(c, "ลบ", "เอา", "ออก", "remove", "delete", "clear") and \
       _has(c, "หน้าว่าง", "ว่าง", "blank", "empty"):
        return Intent("delete_blank", preview="ลบหน้าว่างทั้งหมด")

    # ---- ลบข้อมูลส่วนบุคคล ----
    if _has(c, "ลบ", "ปิด", "ซ่อน", "remove", "redact") and \
       _has(c, "ส่วนบุคคล", "ส่วนตัว", "personal", "pii", "ข้อมูลลับ"):
        return Intent("redact_pii",
                      preview="ปิดทับข้อมูลส่วนบุคคล (เบอร์โทร/อีเมล/เลขบัตรประชาชน/เลขบัตรเครดิต)")

    # ---- หมุนหน้า ----
    if _has(c, "หมุน", "rotate"):
        if _has(c, "แนวนอน", "นอน", "landscape"):
            return Intent("orientation", {"orientation": "landscape"},
                          preview="หมุนทุกหน้าให้เป็นแนวนอน")
        if _has(c, "แนวตั้ง", "ตั้ง", "portrait"):
            return Intent("orientation", {"orientation": "portrait"},
                          preview="หมุนทุกหน้าให้เป็นแนวตั้ง")
        if _has(c, "ซ้าย", "left"):
            return Intent("rotate", {"degrees": -90}, preview="หมุนทุกหน้าไปทางซ้าย 90°")
        if _has(c, "ขวา", "right"):
            return Intent("rotate", {"degrees": 90}, preview="หมุนทุกหน้าไปทางขวา 90°")
        if "180" in c or _has(c, "กลับหัว"):
            return Intent("rotate", {"degrees": 180}, preview="หมุนทุกหน้า 180°")

    # ---- เลขหน้า ----
    if _has(c, "เลขหน้า", "page number", "หมายเลขหน้า", "ใส่เลข"):
        if _has(c, "โรมัน", "roman"):
            lower = _has(c, "เล็ก", "lower")
            return Intent("page_numbers", {"numeral": "roman-lower" if lower else "roman"},
                          preview="ใส่เลขหน้าแบบเลขโรมัน")
        return Intent("page_numbers", {"numeral": "arabic"}, preview="ใส่เลขหน้า")

    # ---- OCR ----
    if "ocr" in c or (_has(c, "อ่าน", "แปลงข้อความ") and _has(c, "สแกน", "รูป", "ภาพ")):
        return Intent("ocr", preview="ทำ OCR อ่านข้อความทุกหน้า (ไฟล์สแกน)")

    # ---- ดึง/เก็บเฉพาะหน้าที่มีคำว่า X ----
    m = re.search(r'(?:ดึง|เก็บ|เอาเฉพาะ|extract|keep)[^"“]*["“]([^"”]+)["”]', command)
    if not m:
        m = re.search(r'(?:ดึง|เก็บ|เอาเฉพาะ)\s*(?:หน้าที่มี(?:คำว่า)?|เฉพาะ)?\s*([^\s].{0,40})$', command)
    if m and _has(c, "ดึง", "เก็บ", "เฉพาะ", "extract", "keep"):
        keyword = m.group(1).strip().strip('"“”')
        if keyword:
            return Intent("keep_matching", {"keyword": keyword},
                          preview=f'เก็บไว้เฉพาะหน้าที่มีคำว่า "{keyword}" (ลบหน้าอื่น)')

    # ---- ใส่ข้อความ "ต่อท้ายป้าย" ที่มีในเอกสาร เช่น 'ใส่วันที่หลัง Date' ----
    # อ้างตำแหน่งจากป้ายในเอกสารเอง จึงตรงช่องทุกหน้าโดยไม่ต้องวางต้นแบบไว้ก่อน
    if re.search(r'หลัง|ต่อจาก|after|ข้าง', command, re.I):
        rest = command
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
            # มีวันที่ระบุมาด้วยไหม เช่น "ใส่วันที่ 03/08/2026 ทุกหน้า"
            m = re.search(r'(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})', command)
            params = {"text": m.group(1)} if m else {}
            shown = m.group(1) if m else "วันที่วันนี้"
            return Intent("text_all_pages", params,
                          preview=f'ใส่ "{shown}" ตำแหน่งเดียวกันทุกหน้า '
                                  f'(ใช้ตำแหน่งของข้อความที่เลือกอยู่)')
        m = re.search(r'["“]([^"”]+)["”]', command)
        if m and _has(c, "ใส่", "เพิ่ม", "add", "put"):
            return Intent("text_all_pages", {"text": m.group(1).strip()},
                          preview=f'ใส่ "{m.group(1).strip()}" ตำแหน่งเดียวกันทุกหน้า '
                                  f'(ใช้ตำแหน่งของข้อความที่เลือกอยู่)')

    # ---- ใส่ลายน้ำ "X" ----
    m = re.search(r'(?:ลายน้ำ|watermark)[^"“]*["“]([^"”]+)["”]', command)
    if m:
        return Intent("watermark", {"text": m.group(1).strip()},
                      preview=f'ใส่ลายน้ำข้อความ "{m.group(1).strip()}"')

    return None


# คำสั่งตัวอย่างที่รองรับ (โชว์เมื่อผู้ใช้พิมพ์คำสั่งที่ไม่เข้าใจ)
EXAMPLES = [
    "ลบหน้าว่างทั้งหมด",
    "หมุนทุกหน้าแนวนอน",
    "ใส่เลขหน้าเป็นเลขโรมัน",
    'ดึงเฉพาะหน้าที่มีคำว่า "ใบเสนอราคา"',
    "ลบข้อมูลส่วนบุคคล",
    "OCR ทุกหน้า",
    'ใส่ลายน้ำ "สำเนา"',
    "ใส่วันที่หลัง Date        (ทุกหน้าที่มีคำว่า Date)",
    'ใส่ 03/08/2026 หลัง "วันที่"',
    "ใส่วันที่ทุกหน้า          (วางข้อความไว้หน้าหนึ่งก่อน แล้วคลิกเลือก)",
]
