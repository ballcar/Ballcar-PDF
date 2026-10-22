"""ทดสอบการดึงหน้าต่างขึ้นมาหน้าสุด (เปิดไฟล์ PDF จาก Explorer/Outlook แล้วต้องไม่ไปอยู่ข้างหลัง)"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication
from app import main as M
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
d = fitz.open()
d.new_page(width=400, height=300).insert_text((40, 60), "hello")
src = tmp / "a.pdf"
d.save(str(src)); d.close()

app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow()
w.doc = PdfDocument(src)
w.viewer.set_document(w.doc)
w._refresh_all(keep_row=0)
w.show()
app.processEvents()

# ---- bring_to_front ต้องเรียกตัวบังคับ foreground ด้วย ----
called = {}
with patch.object(M, "_force_foreground", side_effect=lambda win: called.setdefault("win", win)):
    w.bring_to_front()
assert called.get("win") is w, "bring_to_front ต้องเรียก _force_foreground กับหน้าต่างตัวเอง"
print("OK  bring_to_front เรียกตัวบังคับให้ขึ้นหน้าสุด")

# ---- หน้าต่างต้องไม่ถูกย่อ และยังแสดงอยู่ ----
w.showMinimized(); app.processEvents()
w.bring_to_front(); app.processEvents()
assert w.isVisible(), "ต้องกลับมาแสดงหลังถูกย่อ"
assert not w.isMinimized(), "ต้องคลายจากสถานะย่อ"
print("OK  หน้าต่างที่ถูกย่อไว้ กลับขึ้นมาแสดงได้")

# ---- ไม่พังแม้เรียกซ้ำหลายรอบ / บนแพลตฟอร์มที่ทำไม่ได้ ----
for _ in range(3):
    w.bring_to_front()
app.processEvents()
with patch.object(sys, "platform", "linux"):
    assert M._force_foreground(w) is False, "แพลตฟอร์มอื่นต้องคืน False เงียบๆ ไม่ throw"
print("OK  เรียกซ้ำ/ต่างแพลตฟอร์ม ไม่พัง")

# ---- ตัวที่เผลอเปิดซ้ำต้องยกสิทธิ์ให้ตัวเดิมก่อนสั่งเด้ง ----
import inspect
srccode = inspect.getsource(M._notify_running_instance)
assert "AllowSetForegroundWindow" in srccode, \
    "ต้องเรียก AllowSetForegroundWindow ไม่งั้นตัวที่เปิดอยู่เด้งขึ้นมาไม่ได้"
assert srccode.index("AllowSetForegroundWindow") < srccode.index('b"RAISE"'), \
    "ต้องยกสิทธิ์ก่อนส่งคำสั่ง RAISE"
print("OK  ตัวเปิดซ้ำยกสิทธิ์ให้ตัวเดิมก่อนสั่งเด้ง")

# ---- ตอนเปิดโปรแกรม ต้องมีการสั่งเด้งหน้าสุดหลังปิด splash ----
mainsrc = inspect.getsource(M.main)
assert "bring_to_front" in mainsrc, "main() ต้องสั่งดึงหน้าต่างขึ้นหน้าสุดตอนเปิด"
assert mainsrc.index("_close_splash()") < mainsrc.index("bring_to_front"), \
    "ต้องสั่งหลังปิด splash (splash ปิดแล้วโฟกัสตกไปแอปข้างหลัง)"
print("OK  เปิดโปรแกรมแล้วสั่งดึงขึ้นหน้าสุดหลังปิด splash")



# ---- กันบั๊กเก่ากลับมา: ห้ามผูกเธรดกับโปรเซสอื่น (เคยทำให้ค้าง) ----
import inspect, time

src = inspect.getsource(M._force_foreground)
assert "AttachThreadInput" not in src.split('"""')[2], (
    "_force_foreground ต้องไม่เรียก AttachThreadInput — มันรอเธรดของโปรแกรมอื่น "
    "ถ้าโปรแกรมนั้นค้าง เราจะค้างตามไปด้วย"
)
print("OK  ไม่ใช้ AttachThreadInput แล้ว (ไม่ค้างตามโปรแกรมอื่น)")

# ต้องคืนค่าเร็ว ไม่ว่าอะไรจะอยู่หน้าจอ
w2 = M.MainWindow()
w2.show()
t0 = time.perf_counter()
for _ in range(20):
    M._force_foreground(w2)
elapsed = time.perf_counter() - t0
assert elapsed < 3.0, f"เรียก 20 ครั้งใช้เวลา {elapsed:.1f} วินาที — ช้าผิดปกติ อาจมีจุดบล็อก"
print(f"OK  เรียก 20 ครั้งใน {elapsed*1000:.0f} มิลลิวินาที — ไม่มีจุดบล็อก")
w2.close()

print("")
print("ผ่านทั้งหมด")
