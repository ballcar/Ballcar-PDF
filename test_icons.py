"""ทดสอบไอคอนชุดใหม่ 2.0 (Lucide): ครบทุกไอคอนที่ใช้, เปลี่ยนสีตามธีม, แพ็กไปกับ .exe"""
import os, re, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from app import i18n, icons, theme

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
ROOT = Path(__file__).resolve().parent

# ---- ทุกชื่อไอคอนที่โค้ดใช้ มีไฟล์ SVG จริง + มีไลเซนส์ ----
src = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
used = set(re.findall(r'icon="([a-z0-9-]+)"', src)) | set(re.findall(r'icons\.icon\("([a-z0-9-]+)"', src))
missing = sorted(n for n in used if not icons.available(n))
assert not missing, f"ไม่มีไฟล์ไอคอน: {missing}"
assert len(used) >= 45, used
assert (icons.icons_dir() / "LICENSE").is_file(), "ต้องแนบไลเซนส์ของ Lucide ไปด้วย"
assert "ISC" in (icons.icons_dir() / "LICENSE").read_text(encoding="utf-8")
print(f"OK  ไอคอนที่ใช้ {len(used)} ชื่อ มีไฟล์ครบ พร้อมไลเซนส์ ISC")

# ---- SVG ไม่มีโค้ดแฝง (เป็นไฟล์ที่โหลดมาจากภายนอก) ----
for svg in icons.icons_dir().glob("*.svg"):
    text = svg.read_text(encoding="utf-8").lower()
    assert "<script" not in text and "onload" not in text and "http" not in text.replace(
        "http://www.w3.org/2000/svg", ""), svg.name
print("OK  ไฟล์ SVG ไม่มีสคริปต์หรือลิงก์ภายนอก")


def ink(icon) -> tuple[int, int, int]:
    """สีของเส้นไอคอน (พิกเซลที่ทึบที่สุด)"""
    img = icon.pixmap(48, 48).toImage()
    best = (0, (0, 0, 0))
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() > best[0]:
                best = (c.alpha(), (c.red(), c.green(), c.blue()))
    return best[1]


def close(rgb, hex_color, tol=40):
    want = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return all(abs(a - b) <= tol for a, b in zip(rgb, want))


# ---- ไอคอนสี (ค่าเริ่มต้น): สีประจำไอคอน, ธีมมืดสว่างขึ้น ----
assert theme.colored_icons() is True
theme.save(mode="light"); theme.apply(app)
trash_light = ink(icons.icon("trash-2"))
assert close(trash_light, icons.COLORS["trash-2"]), trash_light
assert close(ink(icons.icon("sheet")), icons.COLORS["sheet"]), "ไอคอน Excel ต้องเป็นสีเขียว"
theme.save(mode="dark"); theme.apply(app)
trash_dark = ink(icons.icon("trash-2"))
assert sum(trash_dark) > sum(trash_light) + 60, f"ธีมมืดสีต้องสว่างขึ้น {trash_light}->{trash_dark}"
missing_color = sorted(n for n in used if n not in icons.COLORS)
assert not missing_color, f"ไอคอนที่ยังไม่มีสีประจำ: {missing_color}"
print(f"OK  ไอคอนสีครบทุกตัว ธีมมืดสว่างขึ้น ({trash_light} -> {trash_dark})")

# ---- ไอคอนขาวดำ: สว่าง = เส้นเข้ม, มืด = เส้นสว่าง ----
theme.save(mode="light", colored=False); theme.apply(app)
light = ink(icons.icon("save"))
theme.save(mode="dark"); theme.apply(app)
dark = ink(icons.icon("save"))
assert sum(light) < 200 and sum(dark) > 500, (light, dark)
theme.save(colored=True)
red = ink(icons.icon("trash-2", "#ff0000"))
assert red[0] > 200 and red[1] < 60, red
assert icons.icon("ไม่มีไอคอนนี้").isNull(), "ไม่มีไฟล์ต้องคืนไอคอนว่าง ไม่ใช่ล้ม"
print(f"OK  เลือกไอคอนขาวดำได้ (สว่าง {light} / มืด {dark}) และกำหนดสีเองได้")

# ---- หน้าต่างหลัก: ทุกปุ่ม/เมนูมีไอคอน และเปลี่ยนธีมแล้วไอคอนเปลี่ยนสีตาม ----
from app import main as M
theme.save(mode="light", colored=False); theme.apply(app)
w = M.MainWindow()
no_icon = [a.text() for a in (*w.tool_actions, *w.page_actions, w.act_open, w.act_save,
                              w.act_print, w.act_undo, w.act_redo) if a.icon().isNull()]
assert not no_icon, f"ไม่มีไอคอน: {no_icon}"
before = ink(w.act_save.icon())
w.change_theme(mode="dark")
app.processEvents()                     # สร้างแถบเครื่องมือ/เมนูใหม่หลังคลิกจบ
after = ink(w.act_save.icon())
assert sum(before) < 200 and sum(after) > 500, f"เปลี่ยนเป็นธีมมืดแล้วไอคอนต้องสว่างขึ้น {before}->{after}"
w.change_theme(colored=True)
app.processEvents()
assert theme.saved_mode() == "dark" and icons.color_of("save") != icons.COLORS["save"]
assert close(ink(w.act_save.icon()), icons.color_of("save"), 40),     "สลับเป็นไอคอนสีแล้วต้องมีผลทันที (ธีมมืด = สีน้ำเงินที่สว่างขึ้น)"
print("OK  ทุกเครื่องมือมีไอคอน และสลับธีม/ไอคอนสีแล้วเปลี่ยนตามทันที")

# ---- ไอคอนใหญ่ขึ้นนิด (2.0) ----
assert w._toolbar.iconSize().width() >= 26
assert all(b.iconSize().width() >= 20 for b in w.tool_panel.visible_buttons())
print("OK  ไอคอนแถบบน 26px / แถบด้านซ้าย 20px")

# ---- ตอน build ต้องแพ็กโฟลเดอร์ไอคอนไปด้วย ----
build = (ROOT / "build-exe.ps1").read_text(encoding="utf-8-sig")
assert '--add-data "app\\icons;app\\icons"' in build, "build-exe.ps1 ต้องแพ็ก app\\icons"
print("OK  build-exe.ps1 แพ็กโฟลเดอร์ไอคอนไปกับ .exe")

print("")
print("ผ่านทั้งหมด")
