"""ทดสอบ 2.3: หน้าต่างมีอะไรใหม่ (ขึ้นครั้งเดียวหลังอัปเดต) + ปักหมุดไฟล์บนหน้าแรก"""
import json, os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog
from app import i18n, recent, whatsnew

i18n.load_language()
settings = i18n.settings_file()

# ---- มีอะไรใหม่ ----
settings.write_text("{}", encoding="utf-8")
assert whatsnew.pending("2.3.0") == [], "ติดตั้งใหม่ครั้งแรก ไม่ต้องขึ้น"
assert i18n.get_setting("whats_new_seen") == "2.3"
assert whatsnew.pending("2.3.0") == []
print("OK  ติดตั้งใหม่ครั้งแรก ไม่ขึ้นหน้าต่างมีอะไรใหม่")

settings.write_text(json.dumps({"update_url": "http://192.168.9.123:8000"}), encoding="utf-8")
sections = whatsnew.pending("2.3.0")
assert [v for v, _ in sections] == ["2.3"], "ผู้ใช้เดิมอัปเดตมา -> ขึ้นของเวอร์ชันนี้"
print("OK  ผู้ใช้เดิมที่อัปเดตมา เห็นของใหม่ของเวอร์ชันนี้")

i18n.set_setting("whats_new_seen", "2.1")
assert [v for v, _ in whatsnew.pending("2.3.4")] == ["2.3", "2.2"], "ข้ามหลายเวอร์ชัน = เห็นครบทุกเวอร์ชันที่พลาด"
whatsnew.mark_seen("2.3.4")
assert whatsnew.pending("2.3.9") == [], "อัปเดตย่อย (2.3.x) ไม่ต้องขึ้นซ้ำ"
assert [v for v, _ in whatsnew.notes_since("0.0", "2.3.0")] == ["2.3", "2.2", "2.1"]
assert "เพิ่มโน้ตตรงนี้" in whatsnew.to_html(whatsnew.notes_since("2.1", "2.2.0", "th"))
assert whatsnew.NOTES["en"].keys() == whatsnew.NOTES["th"].keys()
print("OK  ข้ามหลายเวอร์ชันเห็นครบ · อัปเดตย่อยไม่ขึ้นซ้ำ · มีทั้งไทย/อังกฤษ")

app = QApplication.instance() or QApplication(sys.argv)
from app import main as M
i18n.set_setting("whats_new_seen", "2.1")
w = M.MainWindow()
shown = []
with patch.object(QDialog, "exec", lambda self: shown.append(self.windowTitle()) or 1):
    w.maybe_show_whats_new()
    w.maybe_show_whats_new()
assert len(shown) == 1, "ขึ้นครั้งเดียว ปิดแล้วไม่ขึ้นอีก"
assert i18n.get_setting("whats_new_seen") == ".".join(M.APP_VERSION.split(".")[:2])
help_action = [m for m in w.menuBar().actions() if m.text() == i18n.t("menu.help")][0]
help_menu = help_action.menu()          # เก็บ ref ไว้ ไม่งั้น PySide เก็บขยะเมนูทิ้ง
assert i18n.t("new.menu") in [a.text() for a in help_menu.actions()]
print("OK  เปิดโปรแกรมขึ้นครั้งเดียว · ช่วยเหลือ → มีอะไรใหม่ เปิดซ้ำได้")

# ---- ปักหมุดไฟล์ ----
tmp = Path(tempfile.mkdtemp())
files = []
for name in ("a.pdf", "b.pdf", "form.pdf"):
    d = fitz.open(); d.new_page(); d.save(str(tmp / name)); d.close()
    files.append(tmp / name)
recent.clear()
for f in files:
    recent.add(f)
recent.pin(files[2])
assert recent.is_pinned(files[2]) and recent.pinned() == [files[2].resolve()]
w.home.refresh()
rows = [w.home.recent_list.item(i) for i in range(w.home.recent_list.count())]
assert rows[0].text().startswith("📌 form.pdf") and rows[0].data(Qt.UserRole + 1)
assert len(rows) == 3, "ไฟล์ที่ปักหมุดไม่ขึ้นซ้ำในรายการล่าสุด"
w.home._clear_recent()
rows = [w.home.recent_list.item(i) for i in range(w.home.recent_list.count())]
assert [r.text().split("\n")[0] for r in rows] == ["📌 form.pdf"], "ล้างรายการล่าสุด ไม่ลบปักหมุด"
assert not w.home.empty.isVisible()
recent.unpin(files[2]); w.home.refresh()
assert w.home.recent_list.count() == 0
print("OK  ปักหมุดอยู่บนสุด ไม่ซ้ำ ล้างรายการล่าสุดแล้วยังอยู่ · เลิกปักหมุดได้")

print("\nผ่านทั้งหมด")
