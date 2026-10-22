"""ทดสอบ UI: บีบอัด, ครอบตัด, เซ็นทุกหน้า, กู้คืนงานค้าง"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp / "appdata")

import fitz
from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QSpinBox, QMessageBox
from app import autosave
from app.main import MainWindow
from app.pdfops import PdfDocument

# ไฟล์ทดสอบ (มีรูปใหญ่ให้บีบได้)
import random
w = h = 700
samples = bytes(random.randint(0, 255) for _ in range(w * h * 3))
img = fitz.Pixmap(fitz.csRGB, w, h, samples, 0).tobytes("png")
doc = fitz.open()
for i in range(3):
    p = doc.new_page(width=595, height=842)
    p.insert_image(fitz.Rect(20, 20, 575, 780), stream=img)
src = tmp / "doc.pdf"; doc.save(str(src)); doc.close()

sig = tmp / "sig.png"
fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 50)).save(str(sig))

app = QApplication(sys.argv)


def fresh(path=src):
    w = MainWindow()
    w.doc = PdfDocument(path); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
    return w


# ---- บีบอัดผ่าน UI ----
w = fresh()
out = tmp / "small.pdf"
def exec_with(fill):
    def _exec(self):
        fill(self)
        return QDialog.Accepted
    return _exec

def fill_cmp(d):
    d.findChild(QComboBox).setCurrentIndex(2)   # สูง
with patch.object(QDialog, "exec", exec_with(fill_cmp)), \
     patch("app.main.QFileDialog.getSaveFileName", return_value=(str(out), "")), \
     patch("app.main.QMessageBox.information") as info:
    w.compress_dialog()
assert out.exists(), "ต้องได้ไฟล์บีบอัด"
assert out.stat().st_size < src.stat().st_size, "ไฟล์ต้องเล็กลง"
assert info.called
print(f"OK  บีบอัดผ่าน UI ({src.stat().st_size//1024}KB -> {out.stat().st_size//1024}KB)")

# ---- ครอบตัดผ่าน UI ----
w = fresh()
def fill_crop(d):
    for sp in d.findChildren(QSpinBox):
        sp.setValue(10)
with patch("app.main.QInputDialog.getItem", return_value=("ทุกหน้า (3 หน้า)", True)), \
     patch.object(QDialog, "exec", exec_with(fill_crop)):
    w.crop_dialog()
p0 = w.doc.doc.load_page(0)
assert abs(p0.rect.width - 595 * 0.8) < 3, f"กว้างควรเหลือ ~476 ได้ {p0.rect.width}"
print("OK  ครอบตัดผ่าน UI")

# ---- เซ็นทุกหน้าผ่านปุ่มบนแถบ ----
w = fresh()
stamp = w.doc.add_stamp(0, str(sig), fitz.Rect(400, 750, 550, 800))
w.viewer.selected_stamp = stamp
with patch("app.main.QInputDialog.getItem", return_value=("ทุกหน้า (3 หน้า)", True)):
    w.stamp_selected_all_pages()
# หน้า 0 มีอยู่แล้ว 1 อัน + อีก 2 หน้าที่เหลือ = ทุกหน้ามีลายเซ็น
assert all(len(w.doc.stamps_on(i)) >= 1 for i in range(3)), "ทุกหน้าต้องมีลายเซ็น"
assert len(w.doc.stamps_on(0)) == 1, "หน้าที่มีอยู่แล้วไม่ควรซ้ำ"
print("OK  เซ็นทุกหน้าผ่านปุ่มบนแถบ (ไม่วางซ้ำหน้าเดิม)")

# ---- auto-save: ทำงานค้างแล้วมี recovery ----
for r in autosave.pending_recoveries():
    autosave.discard_recovery(r["meta_path"])
w = fresh()
w.doc.crop_pages([0], (0.1, 0, 0, 0))   # ทำ dirty
assert w.doc.dirty
w._autosave_tick()
pend = autosave.pending_recoveries()
assert len(pend) == 1, "tick ต้องเขียน recovery เมื่อ dirty"
print("OK  auto-save tick เขียน recovery เมื่อมีงานค้าง")

# ไม่ dirty -> ไม่เขียนเพิ่ม
for r in autosave.pending_recoveries():
    autosave.discard_recovery(r["meta_path"])
w2 = fresh()
w2._autosave_tick()
assert autosave.pending_recoveries() == [], "ไม่ dirty ไม่ควรเขียน recovery"
print("OK  ไม่มีงานค้าง ไม่เขียน recovery")

# ---- บันทึกแล้วเคลียร์ recovery ----
w = fresh()
w.doc.crop_pages([0], (0.1, 0, 0, 0))
w._autosave_tick()
assert autosave.pending_recoveries()
save_to = tmp / "saved_out.pdf"
with patch("app.main.QFileDialog.getSaveFileName", return_value=(str(save_to), "")):
    w.save_file_as()
assert autosave.pending_recoveries() == [], "บันทึกแล้วต้องเคลียร์ recovery ของ session นี้"
print("OK  บันทึกจริงแล้วเคลียร์ recovery")

# ---- offer_recovery: กู้คืน ----
for r in autosave.pending_recoveries():
    autosave.discard_recovery(r["meta_path"])
# สร้าง recovery ค้างไว้ (จำลองว่ารอบก่อนปิดผิดปกติ)
tmpdoc = PdfDocument(src)
tmpdoc.crop_pages([0], (0.2, 0, 0, 0))
autosave.write_recovery(tmpdoc.doc.tobytes(), str(src), "oldsession")
w = fresh()
with patch("app.main.QMessageBox.question", return_value=QMessageBox.Yes):
    w.offer_recovery()
assert abs(w.doc.doc.load_page(0).rect.width - 595 * 0.8) < 3, "ต้องกู้งานที่ครอบไว้กลับมา"
assert w.doc.dirty, "งานที่กู้มาถือว่ายังไม่บันทึก"
assert autosave.pending_recoveries() == [], "จัดการงานค้างแล้วต้องเอาออกจากคิว"
print("OK  offer_recovery กู้งานค้างกลับมาได้")

# ---- offer_recovery: ไม่กู้ -> ทิ้ง ----
autosave.write_recovery(tmpdoc.doc.tobytes(), str(src), "oldsession2")
w = fresh()
before_w = w.doc.doc.load_page(0).rect.width
with patch("app.main.QMessageBox.question", return_value=QMessageBox.No):
    w.offer_recovery()
assert abs(w.doc.doc.load_page(0).rect.width - before_w) < 1, "กดไม่กู้ ต้องไม่เปลี่ยนเอกสาร"
assert autosave.pending_recoveries() == [], "กดไม่กู้ ต้องทิ้งงานค้าง"
print("OK  offer_recovery กดไม่กู้ -> ทิ้งงานค้าง")

print("\nผ่านทั้งหมด")
