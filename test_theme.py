"""ทดสอบธีม 2.0: โหมดสว่าง/มืด/ตาม Windows, สีหลัก, จำค่าที่เลือก, เมนูมุมมอง → ธีมและสี"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel
from app import i18n, theme

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)

# ---- ค่าเริ่มต้น: ตาม Windows + แดง Ballcar ----
assert theme.saved_mode() == "system" and theme.saved_accent() == "ballcar"
print("OK  ค่าเริ่มต้น ตาม Windows + แดง Ballcar")

# ---- สว่าง/มืด ได้สีต่างกันจริง และตัวหนังสืออ่านออกบนพื้น ----
light, dark = theme.build_palette(False, "blue"), theme.build_palette(True, "blue")
assert light.window != dark.window and light.text != dark.text
assert light.accent == dark.accent == theme.ACCENTS["blue"]
assert theme._readable_on("#ffeb3b") == "#1a1a1a"     # พื้นเหลือง -> ตัวหนังสือดำ
assert theme._readable_on("#1f2124") == "#ffffff"     # พื้นเข้ม -> ตัวหนังสือขาว
print("OK  สว่าง/มืดต่างกัน ตัวหนังสือบนสีหลักอ่านออก")

# ---- สีเอง: รับรหัสสีถูกรูปแบบ ค่าเพี้ยนกลับไปใช้สีเริ่มต้น ----
assert theme.resolve_accent("#12AB34") == "#12ab34"
for bad in ("#12", "red", "#zzzzzz", None, 123):
    assert theme.resolve_accent(bad) == theme.ACCENTS["ballcar"], bad
print("OK  สีเองรับรหัสสี ค่าเพี้ยนไม่ทำให้โปรแกรมพัง")

# ---- จำค่า + ใช้กับทั้งโปรแกรม ----
theme.save(mode="dark", accent="green")
assert theme.saved_mode() == "dark" and theme.saved_accent() == "green"
p = theme.apply(app)
assert p.dark and app.palette().color(QPalette.Window).name() == p.window
assert app.palette().color(QPalette.Highlight).name() == theme.ACCENTS["green"]
assert app.styleSheet() == theme.stylesheet(p)
theme.save(mode="อะไรก็ไม่รู้")            # ค่าเพี้ยนไม่บันทึก
assert theme.saved_mode() == "dark"
print("OK  จำโหมด/สี และใช้กับทั้งโปรแกรมทันที")

# ---- สไตล์กลางครอบคลุม role ที่วิดเจ็ตใช้ ----
qss = theme.stylesheet(p)
for selector in ('QLabel[role="hint"]', 'QFrame[role="divider"]', 'QPushButton[role="primary"]',
                 'QLineEdit[invalid="true"]', "#viewerArea", "#selPopup", "#toolsButton",
                 *(f'QWidget[role="modebar-{k}"]' for k in ("info", "warn", "success",
                                                           "danger", "note"))):
    assert selector in qss, f"ธีมต้องมีสไตล์ของ {selector}"
hint = QLabel("x"); hint.setProperty("role", "hint"); hint.ensurePolished()
assert hint.palette().color(QPalette.WindowText).name() == p.text_muted
print("OK  สไตล์กลางครอบคลุมแถบโหมด ข้อความอธิบาย ปุ่มหลัก ช่องกรอกผิด")

# ---- ไม่เหลือสีกำหนดตายตัวในโค้ด (นอกจากช่องตัวอย่างสีที่ผู้ใช้เลือก) ----
src = (Path(__file__).parent / "app" / "main.py").read_text(encoding="utf-8")
leftover = [l.strip() for l in src.splitlines()
            if ".setStyleSheet(" in l and "swatch" not in l]
assert not leftover, f"ยังมีสีตายตัวที่ไม่ผ่านธีม: {leftover}"
print("OK  ไม่มีสีตายตัวหลงเหลือใน main.py")

# ---- เมนู มุมมอง → ธีมและสี ใช้งานได้จริง ----
from app import main as M
theme.save(mode="light", accent="ballcar"); theme.apply(app)
w = M.MainWindow()
app.processEvents()     # ให้เมนูชุดเก่า (ถ้ามีการสร้างใหม่) ถูกลบจริงก่อน
# เก็บ reference ของ action ไว้ตลอด — ปล่อยให้ Python เก็บขยะ wrapper แล้ว QMenu จะหลุดไปด้วย
bar_actions = w.menuBar().actions()
view = next(a.menu() for a in bar_actions if a.text() == i18n.t("menu.view"))
view_actions = view.actions()
tm = next(a.menu() for a in view_actions if a.text() == i18n.t("theme.menu"))
theme_actions = tm.actions()
mode_names = {i18n.t(f"theme.mode.{m}") for m in theme.MODES}
modes = {a.text(): a for a in theme_actions if a.isCheckable() and a.text() in mode_names}
assert any(a.text() == i18n.t("theme.colored_icons") for a in theme_actions), "ต้องมีตัวเลือกไอคอนสี"
assert set(modes) == {i18n.t(f"theme.mode.{m}") for m in theme.MODES}
assert modes[i18n.t("theme.mode.light")].isChecked()
modes[i18n.t("theme.mode.dark")].trigger()
assert theme.saved_mode() == "dark" and app.palette().color(QPalette.Window).name() == "#1f2124"
acc_menu = next(a.menu() for a in theme_actions if a.text() == i18n.t("theme.accent"))
accent_actions = acc_menu.actions()
blue = next(a for a in accent_actions if a.text() == i18n.t("theme.accent.blue"))
blue.trigger()
assert theme.saved_accent() == "blue"
assert app.palette().color(QPalette.Highlight).name() == theme.ACCENTS["blue"]
print("OK  เมนู มุมมอง → ธีมและสี เปลี่ยนโหมดและสีได้ทันที")

print("")
print("ผ่านทั้งหมด")
