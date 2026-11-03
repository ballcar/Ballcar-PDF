"""ทดสอบปุ่มดูเต็มหน้ากระดาษ (Ctrl+0) และดูเต็มจอ (F11 / Esc ออก)"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication
from app import i18n
from app.main import MainWindow
from app.viewer import SHADOW

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp()) / "a.pdf"
d = fitz.open()
for _ in range(3):
    d.new_page(width=595, height=842)
d.save(str(tmp)); d.close()

w = MainWindow(); w.resize(1300, 800); w.show(); app.processEvents()
w._open_path(str(tmp)); app.processEvents()

# ---- ดูเต็มหน้ากระดาษ: หน้าทั้งแผ่นอยู่ในจอ (สูงไม่เกินพื้นที่ดู) ----
w.viewer.set_zoom(3.0)
w.act_fit_page.trigger(); app.processEvents()
page_h = 842 * w.viewer.zoom
page_w = 595 * w.viewer.zoom
assert page_h <= w.viewer.viewport().height(), f"สูง {page_h} เกินจอ {w.viewer.viewport().height()}"
assert page_w <= w.viewer.viewport().width()
assert page_h >= w.viewer.viewport().height() * 0.85, "ควรใหญ่เต็มที่เท่าที่ยังเห็นทั้งหน้า"
fit_width_zoom = (w.viewer.viewport().width() - 2 * SHADOW - 24) / 595
assert w.viewer.zoom < fit_width_zoom, "จอแนวนอน: ดูเต็มหน้าต้องเล็กกว่าพอดีความกว้าง"
assert w.act_fit_page.shortcut().toString() == "Ctrl+0"
print(f"OK  ดูเต็มหน้ากระดาษ ซูม {w.viewer.zoom:.2f} เห็นทั้งแผ่น (Ctrl+0)")

# ---- ดูเต็มจอ: ซ่อนเมนู/แถบซ้าย/แถบสถานะ, F11 หรือ Esc ออก ----
assert w.act_fullscreen.shortcut().toString() == "F11"
w.act_fullscreen.trigger(); app.processEvents()
assert w.isFullScreen()
assert w.menuBar().isHidden() and w.statusBar().isHidden() and w.tool_panel.isHidden()
assert not w._toolbar.isHidden(), "แถบเครื่องมือด้านบนยังต้องอยู่ ให้กดออก/เลื่อนหน้าได้"
assert w.act_fullscreen.text() == i18n.t("tb.exit_fullscreen")
app.sendEvent(w, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
app.processEvents()
assert not w.isFullScreen(), "กด Esc ต้องออกจากเต็มจอ"
assert not w.menuBar().isHidden() and not w.statusBar().isHidden() and not w.tool_panel.isHidden()
assert w.act_fullscreen.text() == i18n.t("tb.fullscreen")
print("OK  ดูเต็มจอซ่อนเมนู/แถบซ้าย/แถบสถานะ และกด Esc ออกได้ แถบกลับมาครบ")

# ---- แถบด้านซ้ายที่ผู้ใช้ปิดไว้ ออกจากเต็มจอแล้วต้องยังปิดอยู่ ----
w._toggle_tool_panel(False)
w.toggle_fullscreen(); app.processEvents(); w.toggle_fullscreen(); app.processEvents()
assert w.tool_panel.isHidden(), "ออกจากเต็มจอแล้วต้องคืนสภาพเดิมที่ผู้ใช้เลือก"
w._toggle_tool_panel(True)
print("OK  ออกจากเต็มจอแล้วคืนการตั้งค่าแถบด้านซ้ายเดิม")

# ---- Esc ของโหมดแก้ไขมาก่อนเต็มจอ ----
w.toggle_fullscreen(); app.processEvents()
w.toggle_highlight_mode(); app.processEvents()
assert w.viewer._highlighting
app.sendEvent(w, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)); app.processEvents()
assert not w.viewer._highlighting and w.isFullScreen(), "Esc ครั้งแรกต้องออกจากโหมดไฮไลต์ก่อน"
app.sendEvent(w, QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)); app.processEvents()
assert not w.isFullScreen()
print("OK  Esc ออกจากโหมดแก้ไขก่อน แล้วค่อยออกจากเต็มจอ")

print("")
print("ผ่านทั้งหมด")
