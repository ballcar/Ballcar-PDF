"""ข้อความในโปรแกรม 2 ภาษา (ไทย / English)

ใช้ t("key") เรียกข้อความตามภาษาที่เลือกไว้
ภาษาที่เลือกเก็บใน %APPDATA%\\BallcarPDF\\settings.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_LANG = "th"
_current = DEFAULT_LANG


def settings_file() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home())
    folder = base / "BallcarPDF"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "settings.json"


def load_language() -> str:
    global _current
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
        if data.get("language") in TEXTS:
            _current = data["language"]
    except Exception:
        _current = DEFAULT_LANG   # ไฟล์ยังไม่มีหรือเสีย ใช้ค่าเริ่มต้น
    return _current


def save_language(lang: str) -> None:
    global _current
    if lang not in TEXTS:
        return
    _current = lang
    try:
        settings_file().write_text(
            json.dumps({"language": lang}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass  # เขียนไม่ได้ก็ยังใช้งานต่อได้ แค่ไม่จำภาษาไว้รอบหน้า


def current() -> str:
    return _current


def t(key: str, **kwargs) -> str:
    """ข้อความตามภาษาปัจจุบัน — ถ้าไม่มีคีย์จะคืนคีย์เอง จะได้เห็นว่าตกหล่นตรงไหน"""
    text = TEXTS.get(_current, {}).get(key) or TEXTS[DEFAULT_LANG].get(key, key)
    return text.format(**kwargs) if kwargs else text


TEXTS: dict[str, dict[str, str]] = {
    "th": {
        # เมนูหลัก
        "menu.file": "ไฟล์",
        "menu.edit": "แก้ไข",
        "menu.pages": "จัดการหน้า",
        "menu.tools": "เครื่องมือ",
        "menu.view": "มุมมอง",
        "menu.language": "ภาษา / Language",
        "menu.help": "ช่วยเหลือ",

        # ไฟล์
        "file.open": "เปิด",
        "file.save": "บันทึก",
        "file.save_as": "บันทึกเป็น",
        "file.print": "พิมพ์",
        "file.exit": "ออก",

        # แก้ไข
        "edit.undo": "ย้อนกลับ",
        "edit.redo": "ทำซ้ำ",

        # แถบเครื่องมือ
        "tb.prev": "◀ ก่อนหน้า",
        "tb.next": "ถัดไป ▶",
        "tb.zoom_out": "ซูม −",
        "tb.zoom_in": "ซูม +",
        "tb.fit_width": "พอดีความกว้าง",
        "tb.search_placeholder": "ค้นหาคำใน PDF…",
        "tb.find_next": "ค้นหาถัดไป",
        "tb.clear_find": "ล้างไฮไลต์",
        "tb.signature": "✒ ลายเซ็น",
        "tb.signature_tip": "ลายเซ็นที่บันทึกไว้ — คลิกเลือกแล้ววางได้เลย",
        "tb.add_text": "🅣 เพิ่มข้อความ",

        # เพิ่ม/แก้ไขข้อความ
        "tools.add_text": "เพิ่มข้อความ (คลิกจุดบนหน้า)…",
        "text.click_point": "คลิกตำแหน่งบนหน้าที่จะวางข้อความ (Esc = ยกเลิก)",
        "text.new_title": "เพิ่มข้อความ",
        "text.edit_title": "แก้ไขข้อความ",
        "text.placeholder_input": "พิมพ์ข้อความที่นี่…",
        "text.font_size": "ขนาดตัวอักษร:",
        "text.added": "เพิ่มข้อความแล้ว — ดับเบิลคลิกเพื่อแก้คำ, ลากมุมเพื่อปรับขนาด",
        "text.updated": "แก้ข้อความแล้ว",
        "text.moved": "ย้าย/ปรับขนาดข้อความแล้ว",
        "text.deleted": "ลบข้อความแล้ว — Ctrl+Z เพื่อเอากลับ",
        "text.selected": "เลือกข้อความอยู่",
        "text.selected_hint": "เลือกข้อความแล้ว — แก้/ย้าย/เปลี่ยนสี/ลบ ได้จากแถบด้านบน",
        "text.edit": "✎ แก้คำ",
        "text.color": "🎨 สี",
        "text.delete_btn": "🗑 ลบข้อความ",
        "text.pick_color": "เลือกสีข้อความ",
        "tb.edit_text": "✏ แก้ข้อความเดิม",
        "tb.highlight": "🖍 ไฮไลต์",
        "hl.hint": "ลากคลุมข้อความเพื่อไฮไลต์ · คลิกที่ไฮไลต์เพื่อลบ · Esc = ออก",
        "hl.selected": "โหมดไฮไลต์",
        "hl.color": "🎨 เลือกสี",
        "hl.clear_page": "ล้างไฮไลต์หน้านี้",
        "hl.pick_color": "เลือกสีไฮไลต์",
        "hl.done": "ไฮไลต์ {n} คำแล้ว",
        "hl.removed": "ลบไฮไลต์แล้ว",
        "hl.cleared": "ล้างไฮไลต์ {n} จุดแล้ว",
        "tools.edit_text": "แก้ข้อความเดิมในไฟล์ (คลิกข้อความ)…",
        "edit.click_text": "คลิกข้อความเดิมที่จะแก้ (Esc = ยกเลิก)",
        "edit.edit_title": "แก้ข้อความ",
        "edit.no_text_here": "ตรงนี้ไม่มีข้อความให้แก้ — ลองคลิกตรงตัวอักษร",
        "edit.done_hint": "แก้ข้อความแล้ว — ดับเบิลคลิกแก้อีก, ลากมุมปรับขนาด, Ctrl+Z ย้อน",
        "edit.cant_title": "แก้ข้อความไม่ได้",
        "edit.scanned": "หน้านี้เป็นไฟล์สแกน (รูปภาพ) แก้ข้อความเดิมไม่ได้\n"
                        "ใช้เมนู OCR แปลงเป็นข้อความก่อน หรือใช้ 'เพิ่มข้อความ' วางทับแทน",

        # แบบฟอร์ม PDF
        "tools.fill_form": "กรอกแบบฟอร์ม PDF…",
        "form.title": "กรอกแบบฟอร์ม",
        "form.none_title": "ไม่มีแบบฟอร์ม",
        "form.none": "ไฟล์นี้ไม่มีช่องกรอกแบบฟอร์ม (AcroForm)\n"
                     "ถ้าอยากเติมข้อความลงไป ใช้เมนู 'เพิ่มข้อความ' แทนได้",
        "form.thai_tip": "💡 ช่องฟอร์มมาตรฐานใช้ฟอนต์ที่ไม่มีภาษาไทย — "
                         "ถ้ากรอกภาษาไทย แนะนำ 'กรอกแล้วตรึง' เพื่อให้แสดงผลถูกต้อง",
        "form.fill_editable": "กรอก (ฟอร์มยังแก้ได้)",
        "form.fill_flatten": "กรอกแล้วตรึง (แนะนำสำหรับไทย)",
        "form.fill_failed": "กรอกฟอร์มไม่สำเร็จ",
        "form.filled": "กรอก {n} ช่องแล้ว — อย่าลืมบันทึก",

        # รหัสผ่าน
        "pw.title": "ไฟล์มีรหัสผ่าน",
        "pw.prompt": "ไฟล์ “{name}” ถูกล็อกด้วยรหัสผ่าน\nกรุณาใส่รหัสผ่านเพื่อเปิด:",
        "pw.wrong": "รหัสผ่านไม่ถูกต้อง ลองใหม่อีกครั้ง:",

        # ตั้ง/เปลี่ยน/ลบรหัสผ่าน
        "tools.password": "ตั้ง / เปลี่ยน / ลบ รหัสผ่าน PDF…",
        "pwset.title": "รหัสผ่าน PDF",
        "pwset.current_locked": "ไฟล์นี้เปิดจากไฟล์ที่มีรหัสผ่าน — ตั้งรหัสใหม่หรือลบรหัสได้",
        "pwset.current_open": "ไฟล์นี้ยังไม่มีรหัสผ่าน — ตั้งรหัสเพื่อล็อกได้",
        "pwset.mode_set": "ตั้ง / เปลี่ยนรหัสผ่าน",
        "pwset.mode_remove": "ลบรหัสผ่าน (บันทึกไฟล์ที่ไม่ล็อก)",
        "pwset.pw1": "รหัสผ่านใหม่",
        "pwset.pw2": "พิมพ์รหัสผ่านอีกครั้ง",
        "pwset.empty": "ยังไม่ได้ใส่รหัสผ่าน",
        "pwset.mismatch": "รหัสผ่านสองช่องไม่ตรงกัน",
        "pwset.save_as": "บันทึกไฟล์ที่ตั้งรหัสเป็น",
        "pwset.done": "ตั้งรหัสผ่านแล้ว",
        "pwset.removed": "ลบรหัสผ่านแล้ว",
        "pwset.failed": "ตั้งรหัสผ่านไม่สำเร็จ",

        # จัดการหน้า
        "pages.insert_blank": "แทรกหน้าว่าง (ก่อนหน้าที่เลือก)",
        "pages.insert_pdf": "แทรกไฟล์ PDF อื่น…",
        "pages.delete": "ลบหน้าที่เลือก",
        "pages.move_up": "ย้ายหน้าขึ้น",
        "pages.move_down": "ย้ายหน้าลง",
        "pages.rotate_left": "หมุนซ้าย 90°",
        "pages.rotate_right": "หมุนขวา 90°",
        "pages.rotate_180": "หมุน 180°",

        # เครื่องมือ
        "tools.merge": "รวมไฟล์ PDF…",
        "tools.split": "แยกไฟล์ตามช่วงหน้า…",
        "tools.page_numbers": "เพิ่มเลขหน้า…",
        "tools.save_images": "บันทึกหน้าเป็นรูป (.jpg/.png)…",
        "tools.extract_text": "ดึงข้อความทั้งไฟล์…",
        "tools.ocr": "OCR อ่านข้อความจากไฟล์สแกน…",
        "tools.to_word": "แปลงเป็น Word (.docx)…",
        "tools.to_excel": "ดึงตารางเป็น Excel (.xlsx)…",
        "tools.extract_images": "ดึงรูปภาพในไฟล์ออกมา…",
        "tools.watermark_text": "ใส่ลายน้ำข้อความ…",
        "tools.watermark_image": "ใส่ลายน้ำจากรูป…",
        "tools.signature": "ใส่ลายเซ็น / ตราประทับ…",

        # มุมมอง / ช่วยเหลือ
        "view.show_text": "แสดงข้อความในหน้า",
        "help.about": "เกี่ยวกับโปรแกรม",
        "help.about_title": "เกี่ยวกับ Ballcar PDF",
        "help.about_body": "Ballcar PDF\nเวอร์ชัน {version}\n\nโปรแกรมจัดการไฟล์ PDF",

        # แถบวางลายเซ็น
        "bar.placing_tip": "ลากเพื่อย้าย · ลากมุมเพื่อย่อ/ขยาย",
        "bar.confirm": "✔ ยืนยันวางลายเซ็น",
        "bar.cancel": "✕ ยกเลิก",
        "bar.stamp_selected": "เลือกลายเซ็นอยู่",
        "bar.move_resize": "↔ ย้าย / ปรับขนาด",
        "bar.save_to_library": "💾 เก็บเข้าคลัง",
        "bar.delete_stamp": "🗑 ลบลายเซ็น",
        "bar.done": "เสร็จแล้ว",

        # thumbnail
        "thumb.hint": "ลากเพื่อสลับลำดับ · คลิกขวาดูเมนู",
        "thumb.tip": "ลากหน้าขึ้น-ลงเพื่อสลับลำดับ\nคลิกขวา = ลบ / หมุน / แทรก\nCtrl/Shift+คลิก = เลือกหลายหน้า",
        "thumb.page": "หน้า {n}",
        "viewer.no_file": "ยังไม่ได้เปิดไฟล์ PDF",
        "text.placeholder": "ข้อความในหน้าปัจจุบันจะแสดงที่นี่",
        "title.no_file": "ยังไม่ได้เปิดไฟล์",

        # คลังลายเซ็น
        "lib.empty": "(ยังไม่มีลายเซ็นที่บันทึกไว้)",
        "lib.add": "➕ เพิ่มลายเซ็นเข้าคลัง…",
        "lib.use_once": "ใช้ครั้งเดียวจากไฟล์…",
        "lib.manage": "⚙ จัดการคลังลายเซ็น…",

        # ภาษา
        "lang.thai": "ไทย",
        "lang.english": "English",
        "lang.changed": "เปลี่ยนภาษาแล้ว",
    },
    "en": {
        "menu.file": "File",
        "menu.edit": "Edit",
        "menu.pages": "Pages",
        "menu.tools": "Tools",
        "menu.view": "View",
        "menu.language": "ภาษา / Language",
        "menu.help": "Help",

        "file.open": "Open",
        "file.save": "Save",
        "file.save_as": "Save As",
        "file.print": "Print",
        "file.exit": "Exit",

        "edit.undo": "Undo",
        "edit.redo": "Redo",

        "tb.prev": "◀ Previous",
        "tb.next": "Next ▶",
        "tb.zoom_out": "Zoom −",
        "tb.zoom_in": "Zoom +",
        "tb.fit_width": "Fit Width",
        "tb.search_placeholder": "Search in PDF…",
        "tb.find_next": "Find Next",
        "tb.clear_find": "Clear Highlights",
        "tb.signature": "✒ Signatures",
        "tb.signature_tip": "Saved signatures — click one to place it",
        "tb.add_text": "🅣 Add Text",

        "tools.add_text": "Add Text (click on page)…",
        "text.click_point": "Click where you want the text (Esc = cancel)",
        "text.new_title": "Add Text",
        "text.edit_title": "Edit Text",
        "text.placeholder_input": "Type your text here…",
        "text.font_size": "Font size:",
        "text.added": "Text added — double-click to edit, drag a corner to resize",
        "text.updated": "Text updated",
        "text.moved": "Text moved / resized",
        "text.deleted": "Text deleted — Ctrl+Z to undo",
        "text.selected": "Text selected",
        "text.selected_hint": "Text selected — edit / move / recolor / delete from the bar above",
        "text.edit": "✎ Edit Text",
        "text.color": "🎨 Color",
        "text.delete_btn": "🗑 Delete Text",
        "text.pick_color": "Pick text color",
        "tb.edit_text": "✏ Edit Text",
        "tb.highlight": "🖍 Highlight",
        "hl.hint": "Drag over text to highlight · click a highlight to remove · Esc = exit",
        "hl.selected": "Highlight mode",
        "hl.color": "🎨 Color",
        "hl.clear_page": "Clear highlights on page",
        "hl.pick_color": "Pick highlight color",
        "hl.done": "Highlighted {n} word(s)",
        "hl.removed": "Highlight removed",
        "hl.cleared": "Cleared {n} highlight(s)",
        "tools.edit_text": "Edit Existing Text (click text)…",
        "edit.click_text": "Click the text you want to edit (Esc = cancel)",
        "edit.edit_title": "Edit Text",
        "edit.no_text_here": "No text here — try clicking right on the characters",
        "edit.done_hint": "Text edited — double-click to edit again, drag corner to resize, Ctrl+Z to undo",
        "edit.cant_title": "Cannot edit text",
        "edit.scanned": "This page is a scanned image — existing text can't be edited.\n"
                        "Run OCR first, or use 'Add Text' to overlay instead.",

        "tools.fill_form": "Fill PDF Form…",
        "form.title": "Fill Form",
        "form.none_title": "No Form",
        "form.none": "This file has no fillable form fields (AcroForm).\n"
                     "Use 'Add Text' if you want to place text on it.",
        "form.thai_tip": "💡 Standard form fields use a font without Thai glyphs — "
                         "for Thai values, use 'Fill & Flatten' so they display correctly.",
        "form.fill_editable": "Fill (keep editable)",
        "form.fill_flatten": "Fill & Flatten (best for Thai)",
        "form.fill_failed": "Failed to fill form",
        "form.filled": "Filled {n} field(s) — remember to save",

        "pw.title": "Password Required",
        "pw.prompt": "The file “{name}” is password-protected.\nEnter the password to open it:",
        "pw.wrong": "Incorrect password. Try again:",

        "tools.password": "Set / Change / Remove PDF Password…",
        "pwset.title": "PDF Password",
        "pwset.current_locked": "This file was opened from a password-protected file — set a new password or remove it.",
        "pwset.current_open": "This file has no password — set one to lock it.",
        "pwset.mode_set": "Set / change password",
        "pwset.mode_remove": "Remove password (save unlocked)",
        "pwset.pw1": "New password",
        "pwset.pw2": "Repeat password",
        "pwset.empty": "Password is empty",
        "pwset.mismatch": "The two passwords don't match",
        "pwset.save_as": "Save protected file as",
        "pwset.done": "Password set",
        "pwset.removed": "Password removed",
        "pwset.failed": "Failed to set password",

        "pages.insert_blank": "Insert Blank Page (before selection)",
        "pages.insert_pdf": "Insert Another PDF…",
        "pages.delete": "Delete Selected Pages",
        "pages.move_up": "Move Page Up",
        "pages.move_down": "Move Page Down",
        "pages.rotate_left": "Rotate Left 90°",
        "pages.rotate_right": "Rotate Right 90°",
        "pages.rotate_180": "Rotate 180°",

        "tools.merge": "Merge PDF Files…",
        "tools.split": "Split by Page Range…",
        "tools.page_numbers": "Add Page Numbers…",
        "tools.save_images": "Save Pages as Images (.jpg/.png)…",
        "tools.extract_text": "Extract All Text…",
        "tools.ocr": "OCR Scanned Document…",
        "tools.to_word": "Convert to Word (.docx)…",
        "tools.to_excel": "Extract Tables to Excel (.xlsx)…",
        "tools.extract_images": "Extract Embedded Images…",
        "tools.watermark_text": "Add Text Watermark…",
        "tools.watermark_image": "Add Image Watermark…",
        "tools.signature": "Add Signature / Stamp…",

        "view.show_text": "Show Page Text",
        "help.about": "About",
        "help.about_title": "About Ballcar PDF",
        "help.about_body": "Ballcar PDF\nVersion {version}\n\nPDF management tool",

        "bar.placing_tip": "Drag to move · drag a corner to resize",
        "bar.confirm": "✔ Place Signature",
        "bar.cancel": "✕ Cancel",
        "bar.stamp_selected": "Signature selected",
        "bar.move_resize": "↔ Move / Resize",
        "bar.save_to_library": "💾 Save to Library",
        "bar.delete_stamp": "🗑 Delete Signature",
        "bar.done": "Done",

        "thumb.hint": "Drag to reorder · right-click for menu",
        "thumb.tip": "Drag pages to reorder\nRight-click = delete / rotate / insert\nCtrl/Shift+click = select multiple",
        "thumb.page": "Page {n}",
        "viewer.no_file": "No PDF opened",
        "text.placeholder": "Text of the current page appears here",
        "title.no_file": "No file opened",

        "lib.empty": "(No saved signatures yet)",
        "lib.add": "➕ Add Signature to Library…",
        "lib.use_once": "Use Once from File…",
        "lib.manage": "⚙ Manage Signature Library…",

        "lang.thai": "ไทย",
        "lang.english": "English",
        "lang.changed": "Language changed",
    },
}
