"""ทดสอบไอคอนหน้าเมนู"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from PySide6.QtWidgets import QApplication
from app.main import MainWindow, emoji_icon
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
d = fitz.open(); d.new_page(); src = tmp / "t.pdf"; d.save(str(src)); d.close()

app = QApplication(sys.argv)

# ---- emoji_icon สร้างไอคอนได้ + cache ----
ic = emoji_icon("📂")
assert not ic.isNull(), "ไอคอนต้องไม่ว่าง"
assert emoji_icon("📂") is ic, "ต้อง cache ไม่สร้างใหม่ทุกครั้ง"
print("OK  สร้างไอคอนจากอิโมจิ + cache")

w = MainWindow()
w.doc = PdfDocument(src); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)

# ---- ทุกเมนูย่อยต้องมีไอคอน ----
def items(title_prefix):
    for m in w.menuBar().actions():
        menu = m.menu()
        if menu and menu.title().startswith(title_prefix):
            return [a for a in menu.actions() if not a.isSeparator()]
    raise AssertionError(f"ไม่เจอเมนู {title_prefix}")


for title in ("ไฟล์", "แก้ไข", "จัดการหน้า", "เครื่องมือ", "มุมมอง", "ภาษา", "ช่วยเหลือ"):
    acts = items(title)
    assert acts, f"เมนู {title} ว่าง"
    missing = [a.text() for a in acts if a.icon().isNull()]
    assert not missing, f"เมนู {title} ยังไม่มีไอคอน: {missing}"
    print(f"OK  เมนู '{title}' มีไอคอนครบ {len(acts)} รายการ")

# ---- เครื่องมือต้องมีครบทุกรายการ (กันเผลอลบ/เพิ่มซ้ำ) ----
TOOLS_COUNT = 19        # เพิ่มรายการใหม่แล้วอัปเดตเลขนี้ด้วย
tools = items("เครื่องมือ")
assert len(tools) == TOOLS_COUNT, \
    f"เมนูเครื่องมือควรมี {TOOLS_COUNT} รายการ ได้ {len(tools)}: {[a.text() for a in tools]}"
print(f"OK  เมนูเครื่องมือครบ {TOOLS_COUNT} รายการ")

# ---- ไม่มีอิโมจิค้างอยู่หน้าข้อความ (ย้ายไปเป็นไอคอนแล้ว) ----
for a in tools:
    assert not a.text().startswith("⚙"), f"ยังมีอิโมจิค้างในข้อความ: {a.text()}"
print("OK  ไม่มีอิโมจิซ้ำค้างในข้อความเมนู")

# ---- เปลี่ยนภาษาแล้วไอคอนยังอยู่ ----
w.change_language("en")
for m in w.menuBar().actions():
    menu = m.menu()
    if menu and menu.title().startswith("Tools"):
        acts = [a for a in menu.actions() if not a.isSeparator()]
        assert acts and all(not a.icon().isNull() for a in acts), "เปลี่ยนภาษาแล้วไอคอนหาย"
        break
else:
    raise AssertionError("ไม่เจอเมนู Tools หลังเปลี่ยนภาษา")
print("OK  เปลี่ยนภาษาแล้วไอคอนยังอยู่")


# ---- ไอคอนต้องไม่จางจนมองไม่เห็น ----
# (เคยพลาดใช้ ↺ ↻ ที่เป็นตัวอักษรลูกศรบางๆ ไม่ใช่อิโมจิ — จางจนแทบมองไม่เห็นในเมนู)
import re
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPainter, QPixmap

source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
used = list(dict.fromkeys(re.findall(r'icon="([^"]+)"', source)
                          + re.findall(r'emoji_icon\("([^"]+)"\)', source)))
assert used, "ไม่เจอไอคอนในโค้ด"

MIN_INK = 200      # จำนวนพิกเซลที่มีหมึกขั้นต่ำ (↺ ได้แค่ 166 = จางเกินไป)
faint = []
for e in used:
    pm = QPixmap(40, 40); pm.fill(Qt.white)
    p = QPainter(pm); p.drawPixmap(4, 4, emoji_icon(e).pixmap(QSize(32, 32))); p.end()
    img = pm.toImage()
    ink = sum(1 for x in range(40) for y in range(40)
              if img.pixelColor(x, y).red() < 250
              or img.pixelColor(x, y).green() < 250
              or img.pixelColor(x, y).blue() < 250)
    if ink < MIN_INK:
        faint.append((e, ink))

if faint:
    # ระบบที่ไม่มีฟอนต์อิโมจิ (เช่น offscreen บน CI) จะจางหมดทุกตัว — ข้ามไป
    if len(faint) < len(used):
        raise AssertionError(f"ไอคอนจางเกินไป (หมึก < {MIN_INK}): {faint}")
    print("SKIP ระบบนี้ไม่มีฟอนต์อิโมจิ ข้ามการวัดความเข้ม")
else:
    print(f"OK  ไอคอนทุกตัวเข้มพอ ({len(used)} ตัว)")

print("\nผ่านทั้งหมด")


# ---- แถบเครื่องมือกระชับ: เครื่องมือแก้ไขรวมใน dropdown เดียว ----
w2 = MainWindow()
w2.doc = None
tb = w2.tools_button
menu = tb.menu()
labels = [a.text() for a in menu.actions() if a.text()]
# ต้องมี 5 เครื่องมือแก้ไข (ทดสอบภาษาอังกฤษ เพราะก่อนหน้าเปลี่ยนเป็น en แล้ว)
for kw in ("Add Text", "Edit Text", "Highlight", "Erase", "Assistant"):
    assert any(kw in x for x in labels), (kw, labels)
# ลายเซ็นเป็นเมนูย่อยซ้อน
submenus = [a.menu() for a in menu.actions() if a.menu()]
assert any(sm is w2.sig_menu for sm in submenus), "ลายเซ็นต้องเป็นเมนูย่อยใน dropdown"
print("OK  เครื่องมือแก้ไขรวมใน dropdown เดียว (มีลายเซ็นเป็นเมนูย่อย)")

# แถบต้องกระชับพอสำหรับจอทั่วไป (ไม่เกิน ~900px)
w2.resize(1050, 150); w2.show()
import PySide6.QtWidgets as _qtw
_qtw.QApplication.processEvents()
need = w2._toolbar.sizeHint().width()
# บน Windows จริง ~774px (offscreen วัดกว้างกว่าเพราะไม่มีฟอนต์อิโมจิ) — เดิม ~1700
assert need < 1200, f"แถบเครื่องมือควรกระชับ (<1200px) ได้ {need}"
print(f"OK  แถบเครื่องมือกระชับ ({need}px offscreen / ~774px จริง) พอดีจอทั่วไป")
