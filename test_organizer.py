"""ทดสอบจัดเรียงหน้าแบบตาราง (2.1): สลับแทนพื้นที่เอกสาร, ลากสลับลำดับ, หมุน/ลบหน้าที่เลือก, ย้อนกลับ"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication
from app import i18n
from app.main import MainWindow

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp()) / "five.pdf"
d = fitz.open()
for n in range(1, 6):
    d.new_page(width=595, height=842).insert_text((72, 100), f"PAGE{n}", fontsize=30)
d.save(str(tmp)); d.close()


def order(w) -> list[str]:
    return [w.doc.doc[i].get_text().strip() for i in range(w.doc.page_count)]


w = MainWindow()
w.resize(1280, 800); w.show(); app.processEvents()
assert not w.act_organize.isEnabled() or not w.doc, "ยังไม่เปิดไฟล์"
w.act_organize.setChecked(True); app.processEvents()
assert not w.act_organize.isChecked() and w._doc_stack.currentWidget() is w.home, \
    "ยังไม่เปิดไฟล์ กดจัดเรียงหน้าแล้วต้องไม่เข้าโหมดตาราง"

w._open_path(str(tmp)); app.processEvents()
w.goto_page(2); app.processEvents()
grid = w.organizer.grid

# ---- เปิดโหมดตาราง: แทนพื้นที่เอกสาร, ซ่อนแถบภาพย่อ, เลือกหน้าที่ดูอยู่ไว้ ----
w.act_organize.setChecked(True); app.processEvents()
assert w._doc_stack.currentWidget() is w.organizer
assert grid.count() == 5 and grid.selected_rows() == [2]
assert not w._thumb_panel.isVisible(), "ตารางแสดงภาพหน้าอยู่แล้ว ไม่ต้องมีแถบภาพย่อซ้ำ"
assert w.act_organize.shortcut().toString() == "Ctrl+G"
print("OK  Ctrl+G สลับพื้นที่เอกสารเป็นตารางภาพหน้า เลือกหน้าที่ดูอยู่ไว้ให้")

# ---- ลากสลับลำดับ (จำลองผลการลาก: หน้า 5 ไปไว้หน้าแรก) ----
grid.clearSelection(); grid.item(4).setSelected(True)
grid.orderChanged.emit([4, 0, 1, 2, 3]); app.processEvents()
assert order(w) == ["PAGE5", "PAGE1", "PAGE2", "PAGE3", "PAGE4"], order(w)
assert grid.count() == 5 and grid.item(0).text() == i18n.t("thumb.page", n=1)
print("OK  ลากสลับลำดับในตาราง = เรียงหน้าในเอกสารจริง")

# ---- หมุน/ลบ หลายหน้าที่เลือกในตาราง ด้วยคำสั่งเดียวกับเมนู ----
acts = {a.text(): a for a in w.page_actions}
grid.clearSelection()
for r in (1, 2):
    grid.item(r).setSelected(True)
acts[i18n.t("pages.rotate_right")].trigger(); app.processEvents()
assert [w.doc.doc[i].rotation for i in range(5)] == [0, 90, 90, 0, 0]
assert grid.selected_rows() == [1], "หลังหมุน ตารางวาดใหม่และยังอยู่ที่หน้าเดิม"
grid.clearSelection(); grid.item(0).setSelected(True)
acts[i18n.t("pages.delete")].trigger(); app.processEvents()
assert w.doc.page_count == 4 and grid.count() == 4 and order(w)[0] == "PAGE1"
print("OK  หมุน/ลบหน้าที่เลือกในตาราง (ปุ่มบนแถบ/เมนูเดียวกัน)")

# ---- ย้อนกลับได้ ตารางตามทัน ----
w.undo(); app.processEvents()
assert w.doc.page_count == 5 and grid.count() == 5 and order(w)[0] == "PAGE5"
print("OK  Ctrl+Z ย้อนกลับได้ ตารางอัปเดตตาม")

# ---- คลิกขวาในตาราง = เมนูคำสั่งกับหน้าที่เลือก ----
grid.clearSelection(); grid.item(3).setSelected(True)
menu = w.build_page_menu()
labels = [a.text() for a in menu.actions()]
assert any("หน้า 4" in x for x in labels), labels
print("OK  คลิกขวาในตารางได้เมนูของหน้าที่เลือก")

# ---- ดับเบิลคลิกหน้า = กลับโหมดเอกสารที่หน้านั้น ----
grid.pageActivated.emit(3); app.processEvents()
assert not w.act_organize.isChecked() and w._doc_stack.currentWidget() is w.viewer
assert w.viewer.index == 3 and w._thumb_panel.isVisible()
print("OK  ดับเบิลคลิกหน้าในตาราง กลับไปดูหน้านั้น แถบภาพย่อกลับมา")

# ---- ปุ่มเสร็จ / ปรับขนาดภาพ ----
w.act_organize.setChecked(True); app.processEvents()
small = grid.iconSize().width()
w.organizer.zoom.setValue(w.organizer.zoom.value() + 120)
w.organizer.sizeChanged.emit(w.organizer.zoom.value()); app.processEvents()
assert grid.iconSize().width() > small, "ขยายภาพหน้าในตารางได้"
w.organizer.done_button.click(); app.processEvents()
assert not w.act_organize.isChecked() and w._doc_stack.currentWidget() is w.viewer
print("OK  ปรับขนาดภาพในตารางได้ · ปุ่มเสร็จกลับโหมดเอกสาร")

# ---- เปลี่ยนธีม/ภาษา (สร้างแถบเครื่องมือใหม่) ระหว่างจัดเรียงหน้า ต้องยังอยู่ในโหมดตาราง ----
w.act_organize.setChecked(True); app.processEvents()
w._rebuild_ui(); app.processEvents()
assert w.act_organize.isChecked() and w._doc_stack.currentWidget() is w.organizer
assert not w._thumb_panel.isVisible()
print("OK  เปลี่ยนธีม/ภาษาระหว่างจัดเรียงหน้า ยังอยู่ในโหมดตาราง")

# ---- เปลี่ยนธีมตอนดูเอกสาร: แถบภาพย่อต้องกว้างเท่าเดิม (คำแนะนำยาวของแถบตารางเคยดันจนแคบ) ----
w.act_organize.setChecked(False); app.processEvents()
before = w._thumb_panel.width()
w._rebuild_ui(); app.processEvents()
assert abs(w._thumb_panel.width() - before) <= 2, (before, w._thumb_panel.width())
assert w.organizer.minimumSizeHint().width() < 700, w.organizer.minimumSizeHint()
print("OK  เปลี่ยนธีม/ภาษาแล้วแถบภาพย่อไม่ถูกบีบแคบ")

w.doc.dirty = False
print("\nผ่านทั้งหมด")
