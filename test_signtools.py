"""ทดสอบเครื่องมือลายเซ็น 2.3: ครอปลายเซ็นจากเอกสาร, วาดลายเซ็น, ตรายางพร้อมวันที่"""
import os, sys, tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PIL import Image
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog
from app import i18n, library, signtools
from app.main import MainWindow
from app.pdfops import PdfDocument

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())

# เอกสารที่มี "ลายเซ็น" (เส้นหมึกน้ำเงิน) อยู่ที่มุมล่างขวา
src = tmp / "signed.pdf"
d = fitz.open()
page = d.new_page(width=595, height=842)
page.insert_text((72, 100), "Quotation", fontsize=20)
page.draw_bezier((400, 720), (430, 680), (460, 760), (520, 700), color=(0.1, 0.2, 0.7), width=2.5)
d.save(str(src)); d.close()

# ---- ครอปลายเซ็นจากหน้า: พื้นใส ตัดขอบว่าง เหลือแต่เส้น ----
doc = PdfDocument(src)
path = doc.capture_region(0, fitz.Rect(380, 650, 560, 790))
with Image.open(path) as im:
    assert im.mode == "RGBA"
    alpha = im.getchannel("A")
    assert alpha.getextrema()[0] == 0, "พื้นขาวต้องโปร่งใส"
    w, h = im.size
    assert w < (560 - 380) * 300 / 72 * 0.8, "ต้องตัดขอบว่างรอบลายเซ็นทิ้ง"
assert doc.capture_region(0, fitz.Rect(100, 400, 300, 500)) is None, "กรอบที่มีแต่พื้นขาว = ไม่เจอลายเซ็น"
assert doc.capture_region(0, fitz.Rect(10, 10, 12, 12)) is None, "กรอบเล็กเกิน"
assert not doc.dirty, "ครอปไม่แก้เอกสาร"
print("OK  ครอปลายเซ็นจากหน้า: ตัดพื้นขาว ตัดขอบว่าง ไม่แก้เอกสาร")

# ---- ผ่านหน้าต่าง: เมนูลายเซ็น -> ลากกรอบ -> ตั้งชื่อ -> เข้าคลัง ----
win = MainWindow(); win.resize(1200, 800); win.show(); app.processEvents()
win._open_path(str(src)); app.processEvents()
win.capture_signature_mode()
assert win.viewer._capturing and win.viewer._erasing
with patch.object(QInputDialog, "getText", return_value=("ลายเซ็นลูกค้า", True)):
    win.viewer.captureDragged.emit(0, fitz.Rect(380, 650, 560, 790))
assert "ลายเซ็นลูกค้า" in [p.stem for p in library.list_signatures()]
assert not win.doc.dirty
win.capture_signature_mode()
win.viewer.stop_erase_drag()
assert not win.viewer._capturing, "Esc/ออกจากโหมด = เลิกครอป"
print("OK  เมนูครอปลายเซ็น → ลากกรอบ → ตั้งชื่อ → อยู่ในคลังลายเซ็น")

# ---- วาดลายเซ็น ----
pad_dialog = signtools.SignaturePadDialog()
assert not pad_dialog.ok.isEnabled(), "ยังไม่วาด กดใช้ไม่ได้"
pad = pad_dialog.pad
pad.strokes = [[QPointF(50, 120), QPointF(120, 80), QPointF(200, 150), QPointF(300, 90)],
               [QPointF(320, 140), QPointF(380, 100)]]
pad.changed.emit()
assert pad_dialog.ok.isEnabled()
pad.undo()
assert len(pad.strokes) == 1
pad.strokes.append([QPointF(320, 140), QPointF(380, 100)])
png = pad.to_png()
with Image.open(png) as im:
    assert im.mode == "RGBA" and im.getchannel("A").getextrema() == (0, 255)
    assert im.size[0] > im.size[1] * 2, "ตัดขอบตามเส้นที่วาด (ลายเซ็นยาวแนวนอน)"
pad.clear()
assert pad.to_png() is None
print("OK  วาดลายเซ็น: ย้อนเส้น/ล้างได้ ได้ PNG พื้นใสตัดขอบพอดีเส้น")


def draw_and_accept(dialog):
    if isinstance(dialog, signtools.SignaturePadDialog):
        dialog.pad.strokes = [[QPointF(40, 100), QPointF(200, 60), QPointF(260, 130)]]
        dialog.name.setText("เซ็นเมาส์")
        dialog._accept()
        return QDialog.Accepted
    return QDialog.Rejected


with patch.object(QDialog, "exec", draw_and_accept):
    win.draw_signature()
assert "เซ็นเมาส์" in [p.stem for p in library.list_signatures()]
assert win.viewer.placing, "วาดเสร็จ เปิดไฟล์อยู่ = เข้าโหมดวางลายเซ็นเลย"
win.cancel_placement(quiet=True)
print("OK  วาดลายเซ็นแล้วเก็บเข้าคลัง และเข้าโหมดวางบนหน้าทันที")

# ---- ตรายาง ----
assert signtools.thai_date(date(2026, 11, 4)) == "4 พ.ย. 2569"
stamp_png = signtools.make_stamp("อนุมัติ", signtools.STAMP_COLORS["red"], "4 พ.ย. 2569")
with Image.open(stamp_png) as im:
    assert im.mode == "RGBA" and im.getpixel((0, 0))[3] == 0
    reds = [px for px in im.getdata() if px[3] > 200]
    assert reds and all(px[0] > px[2] for px in reds[:200]), "ตรายางสีแดง"
sd = signtools.StampDialog()
assert sd.text() == "อนุมัติ" and sd.with_date.isChecked()
sd.custom.setText("ส่งบัญชีแล้ว")
assert sd.text() == "ส่งบัญชีแล้ว"
assert sd.preview.pixmap() is not None and not sd.preview.pixmap().isNull()
print("OK  ตรายาง: ข้อความสำเร็จรูป/พิมพ์เอง สีเลือกได้ วันที่ พ.ศ.")


def stamp_accept(dialog):
    if isinstance(dialog, signtools.StampDialog):
        dialog.presets.setCurrentRow(1)
        dialog._accept()
        return QDialog.Accepted
    return QDialog.Rejected


with patch.object(QDialog, "exec", stamp_accept):
    win.stamp_dialog()
assert win.viewer.placing, "เลือกตรายางแล้วเข้าโหมดวางทันที"
win.commit_placement(); app.processEvents()
assert len(win.doc.stamps) == 1
out = tmp / "stamped.pdf"
win.doc.save(out)
with fitz.open(str(out)) as saved:
    assert saved[0].get_images(), "บันทึกแล้วตรายางฝังเป็นรูปในหน้า"
print("OK  เมนูตรายาง → วางบนหน้า → บันทึกแล้วฝังในไฟล์")

for tab in win._tabs:
    tab["doc"].dirty = False
print("\nผ่านทั้งหมด")
