"""ทดสอบ 2.3: เปรียบเทียบเอกสาร (รายงานวางคู่ + ไฮไลต์จุดต่าง) และหน้าตั้งค่ารวม"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
                               QInputDialog, QLineEdit)
from app import compare, i18n, theme
from app.main import MainWindow

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())


def make(name, lines, extra_page=False):
    d = fitz.open()
    p = d.new_page()
    for k, line in enumerate(lines):
        p.insert_text((72, 100 + 30 * k), line, fontsize=14)
    if extra_page:
        d.new_page().insert_text((72, 100), "Appendix A", fontsize=14)
    d.save(str(tmp / name)); d.close()
    return tmp / name


old = make("quote-v1.pdf", ["Notebook price 39,900.00 baht", "Delivery within 7 days", "Warranty 3 years"])
new = make("quote-v2.pdf", ["Notebook price 41,500.00 baht", "Delivery within 7 days"], extra_page=True)

# ---- เทียบรายหน้า ----
with fitz.open(str(old)) as a, fitz.open(str(new)) as b:
    diff = compare.diff_pages(a[0], b[0])
    assert diff.changes == 2, diff                      # ราคาเปลี่ยน + บรรทัดรับประกันหายไป
    assert len(diff.added) == 1 and len(diff.removed) == 4   # ราคาเดิม 1 คำ + "Warranty 3 years" 3 คำ
    same = compare.diff_pages(a[0], a[0])
    assert same.changes == 0 and not same.removed and not same.added
print("OK  เทียบรายหน้า: คำที่แก้ = 1 จุด, บรรทัดที่หาย = 1 จุด, ไฟล์เดียวกัน = 0")

# ---- รายงาน: หน้าคู่ (เดิม | ใหม่) จำนวนหน้าเท่าฉบับที่ยาวกว่า ----
out, total = compare.compare_files(old, new, tmp / "report.pdf",
                                   {"old": "เดิม", "new": "ใหม่", "page": "หน้า",
                                    "changes": "ต่าง {n} จุด", "same": "เหมือนกัน",
                                    "missing": "(ไม่มีหน้านี้)"})
with fitz.open(str(out)) as rep:
    assert rep.page_count == 2 and total == 2 + 1      # หน้า 2 มีแค่ฉบับใหม่ = ต่าง 1 จุด
    assert rep[0].rect.width > 595 * 2
    text = rep[0].get_text()
    assert "quote-v1.pdf" in text and "quote-v2.pdf" in text
    assert "ต่าง 2 จุด" in text and "39,900.00" in text and "41,500.00" in text
    assert "(ไม่มีหน้านี้)" in rep[1].get_text()
    assert rep[0].get_drawings(), "ต้องมีกรอบไฮไลต์จุดต่าง"
print("OK  รายงานเปรียบเทียบ: หน้าเดิม|ใหม่ คู่กัน หัวกระดาษบอกชื่อไฟล์/จำนวนจุดต่าง หน้าที่ขาดบอกชัด")

# ---- ผ่านหน้าต่าง: เปิดฉบับเดิม -> เปรียบเทียบ -> รายงานเปิดเป็นแท็บใหม่ ----
w = MainWindow(); w.resize(1200, 800); w.show(); app.processEvents()
w._open_path(str(old)); app.processEvents()
w.doc.rotate_pages([0], 0)        # ยังไม่บันทึก ก็เทียบได้ (ใช้สภาพปัจจุบัน)
with patch.object(QFileDialog, "getOpenFileName", return_value=(str(new), "")):
    w.compare_dialog()
app.processEvents()
assert w.tab_bar.count() == 2 and w.doc.page_count == 2
assert i18n.t("cmpdoc.file", a="quote-v1", b="quote-v2") == w.doc.path.name
assert i18n.t("cmpdoc.menu") in {a.text() for a in w.tool_actions}
print("OK  เครื่องมือ → เปรียบเทียบเอกสาร: รายงานเปิดเป็นแท็บใหม่")

# ---- หน้าตั้งค่ารวม ----
start_mode = theme.saved_mode()


def change_settings(dialog):
    combos = dialog.findChildren(QComboBox)
    mode = [c for c in combos if c.findData("dark") >= 0][0]
    mode.setCurrentIndex(mode.findData("dark"))
    edits = dialog.findChildren(QLineEdit)
    edits[0].setText("Ball")                                   # ชื่อผู้เขียนโน้ต
    edits[1].setText("192.168.9.50:8000")                      # เซิร์ฟเวอร์อัปเดต
    tools = [c for c in dialog.findChildren(QCheckBox) if c.text() == i18n.t("view.show_tools")][0]
    tools.setChecked(False)
    return QDialog.Accepted


with patch.object(QDialog, "exec", change_settings):
    w.settings_dialog()
app.processEvents()
assert theme.saved_mode() == "dark"
assert i18n.get_setting("note_author") == "Ball"
assert i18n.get_setting("update_url") == "http://192.168.9.50:8000"
assert not w.tool_panel.isVisible()
file_menu = [m for m in w.menuBar().actions() if m.text() == i18n.t("menu.file")][0]
fm = file_menu.menu()
settings_act = [a for a in fm.actions() if a.text() == i18n.t("settings.menu")][0]
assert settings_act.shortcut().toString() == "Ctrl+,"
print("OK  ไฟล์ → ตั้งค่า (Ctrl+,): ธีม ชื่อผู้เขียนโน้ต เซิร์ฟเวอร์อัปเดต แถบเครื่องมือ บันทึกแล้วมีผลทันที")

# โน้ตใช้ชื่อผู้เขียนที่ตั้งไว้
w.tab_bar.setCurrentIndex(0); app.processEvents()
with patch.object(QInputDialog, "getMultiLineText", return_value=("ตรวจราคาแล้ว", True)):
    w.viewer.notePointPicked.emit(0, 100.0, 300.0)
assert [c["author"] for c in w.doc.comments() if c["text"] == "ตรวจราคาแล้ว"] == ["Ball"]
print("OK  โน้ตใหม่ใช้ชื่อผู้เขียนจากหน้าตั้งค่า")

theme.save(mode=start_mode)
for tab in w._tabs:
    tab["doc"].dirty = False
print("\nผ่านทั้งหมด")
