"""ทดสอบหน้าแรก 2.0: แสดงตอนยังไม่เปิดไฟล์, ไฟล์ล่าสุด, การ์ดงานหลัก, รวมไฟล์/Batch ใช้ได้โดยไม่ต้องเปิดไฟล์"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication, QPushButton
from app import i18n, recent

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())


def make(name: str, pages: int = 1) -> Path:
    d = fitz.open()
    for _ in range(pages):
        d.new_page().insert_text((72, 72), name)
    p = tmp / name
    d.save(str(p)); d.close()
    return p


a, b, c = make("a.pdf"), make("b.pdf"), make("c.pdf")

# ---- รายการไฟล์ล่าสุด: ใหม่สุดอยู่บน ไม่ซ้ำ จำกัดจำนวน ไฟล์ที่หายไม่แสดง ----
assert recent.items() == []
recent.add(a); recent.add(b); recent.add(a)
assert [p.name for p in recent.items()] == ["a.pdf", "b.pdf"], recent.items()
for n in range(recent.MAX_ITEMS + 3):
    recent.add(make(f"x{n}.pdf"))
assert len(i18n.get_setting("recent_files")) == recent.MAX_ITEMS
recent.clear(); recent.add(c); recent.add(b)
c.rename(tmp / "moved.pdf")
assert [p.name for p in recent.items()] == ["b.pdf"], "ไฟล์ที่ถูกย้าย/ลบไม่ต้องแสดง"
assert len(i18n.get_setting("recent_files")) == 2, "แต่ยังเก็บไว้ เผื่อเป็นไดรฟ์ที่ยังไม่ได้เสียบ"
recent.remove(b)
assert recent.items() == []
print("OK  ไฟล์ล่าสุด: ใหม่สุดอยู่บน ไม่ซ้ำ จำกัด 12 รายการ ไฟล์ที่หายไม่แสดง เอาออกได้")

from app import main as M

# ---- ยังไม่เปิดไฟล์ = หน้าแรก / เปิดไฟล์ = หน้าเอกสาร ----
recent.add(a)
w = M.MainWindow()
assert w._doc_stack.currentWidget() is w.home
assert w.home.recent_list.count() == 1 and w.home.empty.isHidden()
cards = w.home.findChildren(QPushButton)
assert [c.property("title") for c in cards if c.property("role") == "card"] == \
       [i18n.t("home.open"), i18n.t("home.merge"), i18n.t("home.batch")]
print("OK  ยังไม่เปิดไฟล์แสดงหน้าแรก พร้อมการ์ดงานหลัก 3 อย่าง และไฟล์ล่าสุด")

# ---- รวมไฟล์ / Batch ใช้ได้โดยไม่ต้องเปิดไฟล์ (เครื่องมืออื่นยังต้องเปิดไฟล์ก่อน) ----
acts = {x.text(): x for x in w.tool_actions}
assert acts[i18n.t("tools.merge")].isEnabled() and acts[i18n.t("tools.batch")].isEnabled()
assert not acts[i18n.t("tools.to_word")].isEnabled()
print("OK  รวมไฟล์/Batch กดได้ตั้งแต่ยังไม่เปิดไฟล์ เครื่องมืออื่นยังรอไฟล์")

# ---- คลิกไฟล์ล่าสุด -> เปิดไฟล์ สลับไปหน้าเอกสาร และไฟล์นั้นขึ้นบนสุด ----
recent.add(b)
w.home.refresh()
first = w.home.recent_list.item(0)
assert Path(first.data(256)).name == "b.pdf"           # Qt.UserRole = 256
w.home.recent_list.itemClicked.emit(w.home.recent_list.item(1))   # a.pdf
assert w.doc and w.doc.path.name == "a.pdf"
assert w._doc_stack.currentWidget() is w.viewer
assert recent.items()[0].name == "a.pdf", "เปิดแล้วต้องขึ้นบนสุดของรายการ"
print("OK  คลิกไฟล์ล่าสุดแล้วเปิดไฟล์ สลับเป็นหน้าเอกสาร และย้ายขึ้นบนสุด")

# ---- เปิดไฟล์ทางปกติ (เมนู/ลากวาง) ก็บันทึกลงไฟล์ล่าสุด ----
w._open_path(str(b))
assert recent.items()[0].name == "b.pdf"
print("OK  เปิดไฟล์ทางไหนก็บันทึกลงไฟล์ล่าสุด")

# ---- ล้างรายการ / ไม่มีไฟล์ล่าสุดแสดงข้อความแทน ----
w2 = M.MainWindow()
w2.home.clear_button.click()
assert w2.home.recent_list.isHidden() and not w2.home.empty.isHidden() and recent.items() == []
print("OK  ล้างรายการแล้วแสดงข้อความแทนรายการว่าง")

# ---- เปลี่ยนภาษาแล้วหน้าแรกเปลี่ยนตาม ----
w2.change_language("en")
assert w2.home.recent_title.text() == "Recent"
w2.change_language("th")
print("OK  เปลี่ยนภาษาแล้วหน้าแรกเปลี่ยนตาม")

print("")
print("ผ่านทั้งหมด")
