"""ทดสอบระบบเวอร์ชัน + สลับภาษาไทย/อังกฤษ"""
import json
import os
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ["APPDATA"] = tempfile.mkdtemp()   # กันไปแตะ settings จริงในเครื่อง

import fitz
from PySide6.QtWidgets import QApplication
from app import i18n
from app.i18n import t
from bump_version import next_version

# ---------- เวอร์ชัน ----------
assert next_version("1.0.1") == "1.0.2"
assert next_version("1.0.8") == "1.0.9"
assert next_version("1.0.98") == "1.0.99"
assert next_version("1.0.99") == "1.1.0", next_version("1.0.99")
assert next_version("1.1.0") == "1.1.1"
assert next_version("1.1.99") == "1.2.0"
assert next_version("1.99.99") == "1.100.0"
print("OK  กติกาเลขเวอร์ชัน (ถึง .99 แล้วปัดขึ้น minor)")

current = json.loads(Path("version.json").read_text(encoding="utf-8"))["version"]
parts = current.split(".")
assert len(parts) == 3 and all(p.isdigit() for p in parts), current
assert int(parts[2]) <= 99, "patch ต้องไม่เกิน 99"
print(f"OK  version.json ถูกรูปแบบ (ตอนนี้ {current})")

# ---------- ภาษา ----------
app = QApplication(sys.argv)
from app.main import APP_VERSION, MainWindow
from app.pdfops import PdfDocument

assert APP_VERSION == current, (APP_VERSION, current)
print(f"OK  โปรแกรมอ่านเวอร์ชันได้ ({APP_VERSION})")

# ทุกคีย์ต้องมีครบทั้งสองภาษา
th_keys = set(i18n.TEXTS["th"])
en_keys = set(i18n.TEXTS["en"])
assert th_keys == en_keys, f"คีย์ไม่ครบ: ขาดใน en {th_keys - en_keys}, ขาดใน th {en_keys - th_keys}"
assert len(th_keys) > 50, len(th_keys)
print(f"OK  ข้อความครบทั้ง 2 ภาษา ({len(th_keys)} คีย์)")

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(2):
    p = doc.new_page(width=595, height=842)
    p.insert_text((72, 120), f"MARK{i+1}", fontsize=30)
src = tmp / "t.pdf"
doc.save(str(src)); doc.close()

i18n.save_language("th")
w = MainWindow()
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)


def menu_titles(win):
    return [m.title() for m in win.menuBar().findChildren(type(win.menuBar().addMenu("x")))
            if m.title()]


def top_menus(win):
    return [a.text() for a in win.menuBar().actions()]


assert "ไฟล์" in top_menus(w), top_menus(w)
assert w.act_open.text() == "เปิด", w.act_open.text()
assert w.thumbs.item(0).text() == "หน้า 1"
print("OK  เริ่มต้นเป็นภาษาไทย:", top_menus(w))

# ---- สลับเป็นอังกฤษ ----
w.change_language("en")
assert i18n.current() == "en"
assert "File" in top_menus(w), top_menus(w)
assert "Tools" in top_menus(w)
assert w.act_open.text() == "Open", w.act_open.text()
assert w.act_undo.text().endswith("Undo"), w.act_undo.text()
assert w.tools_button.text().strip() == "✎ Edit Tools", w.tools_button.text()
assert w.sig_menu.title() == "✒ Signatures", w.sig_menu.title()
assert w.search_box.placeholderText() == "Search in PDF…"
assert w.thumbs.item(0).text() == "Page 1", w.thumbs.item(0).text()
assert w._ok_btn.text() == "✔ Place Signature"
assert w._done_btn.text() == "Done"
print("OK  สลับเป็นอังกฤษ เมนู/ปุ่ม/thumbnail เปลี่ยนครบ:", top_menus(w))

# เมนูเครื่องมือต้องเป็นอังกฤษด้วย
tools = [a.text() for a in w.tool_actions]
assert any("Convert to Word" in x for x in tools), tools
assert any("OCR" in x for x in tools), tools
print("OK  เมนูเครื่องมือแปลครบ")

# ---- ไม่มีเมนูซ้ำหลังสลับหลายรอบ ----
for _ in range(3):
    w.change_language("th")
    w.change_language("en")
titles = top_menus(w)
assert len(titles) == len(set(titles)), f"เมนูซ้ำ: {titles}"
assert len(w.findChildren(type(w._toolbar))) == 1, "แถบเครื่องมือซ้อนกัน"
print("OK  สลับไปมาหลายรอบ ไม่มีเมนู/แถบเครื่องมือซ้อน")

# ---- คำค้นไม่หายตอนเปลี่ยนภาษา ----
w.search_box.setText("MARK")
w.change_language("th")
assert w.search_box.text() == "MARK", w.search_box.text()
print("OK  คำค้นในช่องค้นหาไม่หายตอนเปลี่ยนภาษา")

# ---- เอกสารและสถานะไม่หาย ----
assert w.doc is not None and w.doc.page_count == 2
assert w.thumbs.count() == 2
print("OK  เอกสารที่เปิดอยู่ไม่หายตอนเปลี่ยนภาษา")

# ---- จำภาษาไว้รอบหน้า ----
w.change_language("en")
saved = json.loads(i18n.settings_file().read_text(encoding="utf-8"))
assert saved["language"] == "en", saved
i18n._current = "th"
assert i18n.load_language() == "en", "ต้องจำภาษาที่เลือกไว้"
print("OK  จำภาษาไว้ให้รอบหน้า")

# ---- ไฟล์ settings เสีย ต้องไม่พัง ----
i18n.settings_file().write_text("{ พัง", encoding="utf-8")
assert i18n.load_language() == "th", "ไฟล์เสียต้องกลับไปใช้ค่าเริ่มต้น"
print("OK  ไฟล์ตั้งค่าเสียก็ไม่พัง")

# ---- คีย์ที่ไม่มีต้องไม่ทำให้ล่ม ----
assert t("ไม่มีคีย์นี้") == "ไม่มีคีย์นี้"
print("OK  คีย์ที่ไม่มีไม่ทำให้โปรแกรมล่ม")

# ---- ชื่อหน้าต่างมีเวอร์ชัน ----
w._update_state()
assert APP_VERSION in w.windowTitle(), w.windowTitle()
assert "Ballcar PDF" in w.windowTitle()
print("OK  ชื่อหน้าต่างมีเวอร์ชัน:", w.windowTitle())

print("\nผ่านทั้งหมด")
