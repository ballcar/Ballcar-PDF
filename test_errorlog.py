"""ทดสอบตัวจับ error + log และตัวกันเปิดซ้ำ"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp / "appdata")

from app import errorlog

# ---- log dir สร้างได้ + เขียน log ----
errorlog._logger = None
log = errorlog.setup_logging("1.0.test")
errorlog.log_info("ข้อความทดสอบ %s", "abc")
for h in log.handlers:
    h.flush()
logfile = errorlog.log_dir() / "ballcar-pdf.log"
assert logfile.exists(), "ต้องมีไฟล์ log"
content = logfile.read_text(encoding="utf-8")
assert "เปิดโปรแกรม" in content and "ข้อความทดสอบ abc" in content
print("OK  เขียน log ไฟล์ได้ (ไทยด้วย)")

# ---- excepthook เขียน error ลง log + เรียก on_crash ----
crashed = {"called": False}
def on_crash():
    crashed["called"] = True

with patch.object(errorlog, "_show_dialog") as dlg:   # ไม่เด้งกล่องจริงตอนเทสต์
    errorlog.install_excepthook(on_crash=on_crash)
    try:
        raise ValueError("บั๊กจำลอง 12345")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    assert dlg.called, "ต้องเด้งกล่องบอกผู้ใช้"
assert crashed["called"], "ต้องเรียก on_crash (เซฟงานกู้คืน) ก่อน"
for h in errorlog.setup_logging().handlers:
    h.flush()
assert "บั๊กจำลอง 12345" in logfile.read_text(encoding="utf-8"), "error ต้องถูกเขียนลง log"
print("OK  excepthook เขียน error ลง log + เซฟงานก่อนเด้งกล่อง")

# ---- KeyboardInterrupt ต้องไม่ถูกดัก (ให้ Ctrl+C ทำงานปกติ) ----
import app.errorlog as el
handled = {"shown": False}
with patch.object(el, "_show_dialog", lambda d: handled.__setitem__("shown", True)):
    el.install_excepthook()
    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        # ต้องไม่เด้งกล่อง (ส่งต่อให้ระบบ) — เรียก hook ตรงๆ
        try:
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        except Exception:
            pass
assert not handled["shown"], "KeyboardInterrupt ไม่ควรเด้งกล่อง error"
print("OK  KeyboardInterrupt ไม่ถูกดัก")

# ---- single-instance: bring_to_front มีจริง + ทำงานไม่ error ----
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import fitz
from PySide6.QtWidgets import QApplication
from app.main import MainWindow, _notify_running_instance, _listen_single_instance
from app.pdfops import PdfDocument

app = QApplication.instance() or QApplication(sys.argv)

# ยังไม่มี server -> notify ต้องคืน False
assert _notify_running_instance() is False, "ยังไม่มีตัวเปิดอยู่ ต้องคืน False"
print("OK  ยังไม่มีโปรแกรมเปิดอยู่ -> notify คืน False (เปิดใหม่ได้)")

d = tmp / "t.pdf"; doc = fitz.open(); doc.new_page(); doc.save(str(d)); doc.close()
w = MainWindow()
w.doc = PdfDocument(d); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
server = _listen_single_instance(w)
app.processEvents()

# ตอนนี้มี server แล้ว -> notify ต้องคืน True (ตัวใหม่ควรออก)
raised = {"n": 0}
orig = w.bring_to_front
w.bring_to_front = lambda: (raised.__setitem__("n", raised["n"] + 1), orig())[1]
assert _notify_running_instance() is True, "มีตัวเปิดอยู่แล้ว ต้องคืน True"
for _ in range(5):
    app.processEvents()
assert raised["n"] >= 1, "ตัวที่เปิดอยู่ต้องถูกสั่งให้เด้งขึ้นมา"
print("OK  เปิดซ้ำ -> ตัวเดิมเด้งขึ้นมา + ตัวใหม่ออก (ไม่ได้ 2 หน้าต่าง)")

server.close()
print("\nผ่านทั้งหมด")
