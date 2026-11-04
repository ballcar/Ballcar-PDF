"""ทดสอบแถบเครื่องมือด้านซ้าย 2.0: แบ่งหมวด ครบทุกเครื่องมือ ค้นหา Enter ใช้งาน เปิด/ปิดแถบ"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication
from app import i18n
from app.toolpanel import short_name

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)

# ---- ชื่อสั้นในแถบแคบ ----
assert short_name("แทรกรูปภาพ (ลากย้าย/ย่อขยายได้)…") == "แทรกรูปภาพ"
assert short_name("🖍 ไฮไลต์") == "ไฮไลต์"
assert short_name("✏ แก้ข้อความเดิม") == "แก้ข้อความเดิม"
assert short_name("หมุนซ้าย 90°") == "หมุนซ้าย 90°"
assert short_name("แปลงเป็น Word (.docx)…") == "แปลงเป็น Word"
assert short_name("&Open") == "Open"
print("OK  ชื่อสั้น: ตัด emoji วงเล็บอธิบาย และ …")

from app import main as M

w = M.MainWindow()
panel = w.tool_panel
buttons = panel.visible_buttons()

# ---- ครบทุกเครื่องมือในเมนูเครื่องมือ/จัดการหน้า และไม่ซ้ำ ----
in_panel = [b.action for b in buttons]
# เมนูเครื่องมือมี "เพิ่มข้อความ/แก้ข้อความเดิม" ซ้ำกับปุ่มบนแถบเครื่องมือ (เปิดหน้าต่างเดียวกัน)
# แถบด้านซ้ายแสดงครั้งเดียวโดยใช้ตัวของแถบเครื่องมือ
same_as_toolbar = {i18n.t("tools.add_text"), i18n.t("tools.edit_text")}
for action in (*w.tool_actions, *w.page_actions):
    if action.text() in same_as_toolbar:
        continue
    assert in_panel.count(action) == 1, f"แถบต้องมี '{action.text()}' หนึ่งครั้ง"
for action in (w.act_add_text, w.act_edit_text, w.act_highlight, w.act_markup, w.act_erase,
               w.act_assistant):
    assert action in in_panel, action.text()
groups = [h.text() for h, _ in panel._groups]
assert groups[0] == i18n.t("group.edit") and i18n.t("group.convert") in groups
print(f"OK  {len(buttons)} เครื่องมือ ครบทุกรายการในเมนู แบ่ง {len(groups)} หมวด")

# ---- ยังไม่เปิดไฟล์: เครื่องมือที่ต้องใช้ไฟล์ปิดอยู่ เปิดไฟล์แล้วใช้ได้ ----
word = next(b for b in buttons if b.action.text() == i18n.t("tools.to_word"))
assert not word.isEnabled(), "ยังไม่เปิดไฟล์ ปุ่มแปลง Word ต้องกดไม่ได้"
tmp = Path(tempfile.mkdtemp()) / "a.pdf"
d = fitz.open(); d.new_page().insert_text((72, 72), "hello"); d.save(str(tmp)); d.close()
w._open_path(str(tmp))
assert word.isEnabled(), "เปิดไฟล์แล้วปุ่มต้องกดได้ตามเมนู"
print("OK  ปุ่มเปิด/ปิดใช้งานตามสถานะไฟล์เหมือนเมนู")

# ---- ค้นหา: กรองตามชื่อ / ชื่อหมวด / ไม่พบ / Enter ใช้เครื่องมือแรก ----
panel.search.setText("word")
assert [b.action for b in panel.visible_buttons()] == [word.action]
panel.search.setText("หมุน")
assert len(panel.visible_buttons()) == 3
panel.search.setText(i18n.t("group.security"))          # ค้นชื่อหมวด = ทั้งหมวด
assert [b.action.text() for b in panel.visible_buttons()] == [i18n.t("tools.password"),
                                                              i18n.t("tools.cover_text"),
                                                              i18n.t("risk.menu")]
panel.search.setText("ไม่มีเครื่องมือนี้แน่นอน")
assert panel.visible_buttons() == [] and not panel.empty.isHidden()
fired = []
panel.search.setText("word")
word.action.triggered.disconnect()
word.action.triggered.connect(lambda *_: fired.append("word"))
panel.search.returnPressed.emit()
assert fired == ["word"], "กด Enter ต้องใช้เครื่องมือแรกที่ตรง"
panel.search.setText("")
assert len(panel.visible_buttons()) == len(buttons)
print("OK  ค้นหาเครื่องมือ (ชื่อ/หมวด) และกด Enter ใช้งานได้")

# ---- เปิด/ปิดแถบ และจำค่า ----
w._toggle_tool_panel(False)
assert panel.isHidden() and i18n.get_setting("tool_panel") is False
w._toggle_tool_panel(True)
assert not panel.isHidden() and i18n.get_setting("tool_panel") is True
panel.hide(); panel.focus_search()
assert not panel.isHidden(), "Ctrl+K ต้องเปิดแถบขึ้นมาให้พิมพ์ค้นหา"
print("OK  เปิด/ปิดแถบได้ จำค่าไว้ และ Ctrl+K เปิดช่องค้นหา")

# ---- ยุบเหลือแถบไอคอน / ขยายกลับ และจำค่า ----
from PySide6.QtCore import Qt
panel.search.setText("word")
panel.set_collapsed(True)
assert panel.width() == panel.COLLAPSED_WIDTH and panel.search.isHidden()
assert len(panel.visible_buttons()) == len(buttons), "ยุบแล้วต้องเห็นไอคอนครบทุกเครื่องมือ"
assert all(b.toolButtonStyle() == Qt.ToolButtonIconOnly for b in buttons)
assert all(b.toolTip() for b in buttons), "ยุบแล้วต้องดูชื่อเครื่องมือได้จาก tooltip"
assert i18n.get_setting("tool_panel_collapsed") is True
panel.focus_search()                     # Ctrl+K ตอนยุบอยู่ -> ขยายให้พิมพ์ได้
assert not panel.collapsed and panel.width() == panel.WIDTH and not panel.search.isHidden()
assert i18n.get_setting("tool_panel_collapsed") is False
panel.collapse_button.click(); assert panel.collapsed
panel.collapse_button.click(); assert not panel.collapsed
# ค่าที่จำไว้ต้องถูกใช้ตอนเปิดหน้าต่างใหม่
i18n.set_setting("tool_panel_collapsed", True)
assert M.MainWindow().tool_panel.collapsed
i18n.set_setting("tool_panel_collapsed", False)
print("OK  ยุบเหลือแถบไอคอน/ขยายกลับได้ จำค่าไว้ และ Ctrl+K ขยายให้อัตโนมัติ")

# ---- แผงภาพย่อ: อยู่ขวาสุด แสดงเฉพาะไฟล์หลายหน้า ----
sp = w._splitter
assert sp.indexOf(w._thumb_panel) == sp.count() - 1, "แผงภาพย่อต้องอยู่ขวาสุด"
assert sp.indexOf(w._thumb_panel) > sp.indexOf(w._viewer_area)
assert M.MainWindow()._thumb_panel.isHidden(), "ยังไม่เปิดไฟล์ ไม่ต้องมีแผงภาพย่อ"
assert w._thumb_panel.isHidden(), "ไฟล์หน้าเดียว ไม่ต้องมีแผงภาพย่อ"
multi = Path(tempfile.mkdtemp()) / "multi.pdf"
d = fitz.open()
for _ in range(3):
    d.new_page()
d.save(str(multi)); d.close()
w.resize(1200, 800); w.show(); app.processEvents()
w._open_path(str(multi)); app.processEvents()
assert not w._thumb_panel.isHidden() and sp.sizes()[sp.indexOf(w._thumb_panel)] >= 150
w.doc.delete_pages([1, 2]); w._refresh_all(keep_row=0)       # ลบจนเหลือหน้าเดียว
assert w._thumb_panel.isHidden(), "ลบจนเหลือหน้าเดียวแล้ว แผงภาพย่อต้องหาย"
w.insert_blank(); app.processEvents()                       # แทรกจนเป็น 2 หน้า
assert not w._thumb_panel.isHidden(), "กลับมาหลายหน้า แผงภาพย่อต้องกลับมา"
print("OK  แผงภาพย่ออยู่ขวาสุด แสดงเฉพาะไฟล์หลายหน้า (ซ่อน/แสดงตามจำนวนหน้า)")

# ---- เปลี่ยนสี (สร้างเมนูใหม่) / เปลี่ยนภาษา แล้วแถบยังทำงาน ไม่พัง ----
w.change_theme(accent="green")
app.processEvents()
w._update_state()
w.change_language("en")
app.processEvents()
assert panel.title.text() == "All tools"
assert "Convert to Word" in [b.text() for b in panel.visible_buttons()]
w.change_language("th")
print("OK  เปลี่ยนสี/ภาษาแล้วแถบสร้างใหม่ถูกต้อง")

print("")
print("ผ่านทั้งหมด")
