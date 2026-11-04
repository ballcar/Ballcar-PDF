"""หน้าต่าง "มีอะไรใหม่" (2.3) — ขึ้นครั้งเดียวหลังอัปเดตเป็นเวอร์ชันใหม่ บอกของใหม่พร้อมวิธีใช้

คนในออฟฟิศอัปเดตแล้วมักไม่รู้ว่ามีอะไรเพิ่ม (เช่นคลิกขวาเพิ่มโน้ต) — ทางนี้บอกตรงจุดที่สุด
เนื้อหาเก็บแยกตามเวอร์ชัน (major.minor) และภาษา; ช่วยเหลือ → มีอะไรใหม่ เปิดดูซ้ำได้
"""
from __future__ import annotations

from . import i18n

# เวอร์ชัน -> รายการ (หัวข้อ, วิธีใช้สั้นๆ) — ใหม่สุดอยู่บน
NOTES = {
    "th": {
        "2.3": [
            ("ครอปลายเซ็นจากเอกสาร", "ปุ่มลายเซ็น → ครอปลายเซ็นจากเอกสาร: ลากกรอบคลุมลายเซ็นบนหน้า "
                                      "แล้วเก็บเข้าคลังไว้ใช้ซ้ำ"),
            ("วาดลายเซ็น", "ปุ่มลายเซ็น → วาดลายเซ็น: เซ็นด้วยเมาส์/ปากกา ไม่ต้องสแกนรูป"),
            ("ตรายาง", "เครื่องมือ → ตรายาง: อนุมัติ / ได้รับแล้ว / สำเนาถูกต้อง พร้อมวันที่ พ.ศ."),
            ("เปรียบเทียบเอกสาร", "เครื่องมือ → เปรียบเทียบเอกสาร: เทียบฉบับเดิมกับฉบับใหม่ "
                                  "แดง = หายไป เขียว = เพิ่ม/แก้"),
            ("ตั้งค่ารวม", "ไฟล์ → ตั้งค่า (Ctrl+,): ธีม ภาษา ชื่อผู้เขียนโน้ต เซิร์ฟเวอร์อัปเดต"),
            ("ปักหมุดไฟล์ที่ใช้บ่อย", "หน้าแรก: คลิกขวาที่ไฟล์ → ปักหมุดไว้บนสุด"),
        ],
        "2.2": [
            ("โน้ตบนหน้า", "คลิกขวาตรงจุดที่ต้องการ → เพิ่มโน้ตตรงนี้ · ชี้เมาส์ที่ไอคอนเพื่ออ่าน · "
                          "ลากไอคอนเพื่อย้าย · คลิกขวาที่ไอคอนเพื่อแก้/ลบ"),
            ("ปิดทับคำที่ค้นหาทุกหน้า", "เครื่องมือ → ปิดทับคำที่ค้นหา: พิมพ์เลขบัตร/ชื่อ "
                                        "แล้วปิดทุกจุด ข้อความข้างใต้ถูกลบจริงตอนบันทึก"),
            ("คำแก้ OCR ภาษาไทย", "เครื่องมือ → คำแก้ OCR: ใส่คำที่ OCR อ่านผิดบ่อยของออฟฟิศ"),
        ],
        "2.1": [
            ("แท็บ", "เปิดหลายไฟล์ในหน้าต่างเดียว · Ctrl+Tab สลับ · Ctrl+W ปิด"),
            ("จัดเรียงหน้าแบบตาราง", "Ctrl+G: ลากสลับ หมุน ลบ หลายหน้าพร้อมกัน"),
            ("ลากไฟล์มาวาง", "ลาก PDF มาเลือกได้ว่าเปิดแท็บใหม่/ต่อท้าย/แทรกบนสุด · ลากรูปมาวางบนหน้าได้"),
        ],
    },
    "en": {
        "2.3": [
            ("Crop a signature from a document", "Signatures → Crop Signature from Document: drag a box "
                                                 "around it and save it to the library"),
            ("Draw a signature", "Signatures → Draw Signature: sign with a mouse or pen"),
            ("Stamps", "Tools → Stamp: Approved / Received / Certified copy with today's date"),
            ("Compare documents", "Tools → Compare Documents: old vs new side by side, "
                                  "red = removed, green = added/changed"),
            ("Settings page", "File → Settings (Ctrl+,): theme, language, note author, update server"),
            ("Pin frequent files", "Home page: right-click a file → Pin to top"),
        ],
        "2.2": [
            ("Notes on the page", "Right-click where you want it → Add Note Here · hover the icon to read · "
                                  "drag the icon to move · right-click the icon to edit/delete"),
            ("Cover searched text on every page", "Tools → Cover Searched Text: type an ID/name and "
                                                  "cover every match; the text is removed when saved"),
            ("Thai OCR corrections", "Tools → Thai OCR Corrections: add words OCR often misreads"),
        ],
        "2.1": [
            ("Tabs", "Several files in one window · Ctrl+Tab to switch · Ctrl+W to close"),
            ("Organize pages grid", "Ctrl+G: drag, rotate, delete many pages at once"),
            ("Drag and drop", "Drop a PDF to open as a tab / append / insert at top · drop images onto a page"),
        ],
    },
}

_SEEN_KEY = "whats_new_seen"


def _minor(version: str) -> str:
    parts = (version or "0.0").split(".")
    return ".".join(parts[:2])


def _key(v: str) -> tuple:
    return tuple(int(x) for x in v.split(".") if x.isdigit())


def notes_since(seen: str | None, current: str, lang: str | None = None) -> list[tuple[str, list]]:
    """[(เวอร์ชัน, รายการ)] ที่ใหม่กว่า seen จนถึง current (ใหม่สุดก่อน) — seen=None = เฉพาะเวอร์ชันปัจจุบัน"""
    table = NOTES.get(lang or i18n.current(), NOTES["th"])
    cur = _key(_minor(current))
    low = _key(_minor(seen)) if seen else None
    out = []
    for version in sorted(table, key=_key, reverse=True):
        k = _key(version)
        if k > cur:
            continue
        if low is None and k != cur:
            continue
        if low is not None and k <= low:
            continue
        out.append((version, table[version]))
    return out


def pending(current: str) -> list[tuple[str, list]]:
    """ของใหม่ที่ผู้ใช้ยังไม่เคยเห็น (เรียกตอนเปิดโปรแกรม)

    ติดตั้งใหม่ครั้งแรก (ยังไม่เคยใช้โปรแกรม) ไม่ต้องขึ้น — ทุกอย่างใหม่หมดอยู่แล้ว
    ผู้ใช้เดิมที่อัปเดตจากเวอร์ชันก่อนมีหน้าต่างนี้ (ยังไม่มีค่าที่จำไว้) = ขึ้นของเวอร์ชันปัจจุบัน
    """
    settings = i18n.load_settings()
    seen = settings.get(_SEEN_KEY)
    if seen is None:
        existing_user = any(k in settings for k in ("recent_files", "theme_mode", "language", "update_url",
                                                    "assistant_history", "tool_panel"))
        if not existing_user:
            mark_seen(current)
            return []
        return notes_since(None, current)
    if _key(_minor(seen)) >= _key(_minor(current)):
        return []
    return notes_since(seen, current)


def mark_seen(current: str) -> None:
    i18n.set_setting(_SEEN_KEY, _minor(current))


def to_html(sections: list[tuple[str, list]]) -> str:
    parts = []
    for version, items in sections:
        parts.append(f"<h3 style='margin:10px 0 4px 0'>{i18n.t('new.version', v=version)}</h3><ul style='margin-top:0'>")
        for title, how in items:
            parts.append(f"<li style='margin-bottom:6px'><b>{title}</b><br>{how}</li>")
        parts.append("</ul>")
    return "".join(parts)
