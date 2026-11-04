"""ทดสอบวางรูป/ลายเซ็น: บันทึกแล้วตำแหน่งตรงกับที่เห็น, Shift คงสัดส่วน, ลากไฟล์รูปมาปล่อยบนหน้า"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent, QMouseEvent
from PySide6.QtWidgets import QApplication
from app import i18n
from app.main import MainWindow
from app.pdfops import PdfDocument

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())

pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 100), False)   # รูปสัดส่วน 2:1
pix.set_rect(pix.irect, (200, 30, 30))
img = tmp / "logo.png"
pix.save(str(img))


def make_pdf(name: str, setup=None) -> Path:
    d = fitz.open()
    for _ in range(2):
        p = d.new_page(width=595, height=842)
        if setup:
            setup(p)
    path = tmp / name
    d.save(str(path)); d.close()
    return path


def image_rect(path: Path, page: int = 0) -> fitz.Rect:
    with fitz.open(str(path)) as d:
        p = d[page]
        r = p.get_image_rects(p.get_images()[0][0])[0]
        return r * p.rotation_matrix if p.rotation else r


def close(a: fitz.Rect, b: fitz.Rect) -> bool:
    return all(abs(x - y) < 0.6 for x, y in zip(a, b))


# ---- ยืด/บีบรูปแล้วบันทึก: ตำแหน่งและขนาดต้องตรงกับที่วางไว้ (เดิมรูปหดและเลื่อนลงกลางกรอบ) ----
want = fitz.Rect(100, 100, 300, 300)                     # ยืดรูป 2:1 เป็นสี่เหลี่ยมจัตุรัส
cases = {"ปกติ": None,
         "มี cropbox": lambda p: p.set_cropbox(fitz.Rect(40, 40, 555, 802)),
         "หน้าหมุน 90°": lambda p: p.set_rotation(90)}
for label, setup in cases.items():
    src = make_pdf(f"{label}.pdf", setup)
    doc = PdfDocument(src)
    doc.add_stamp(0, img, want)                           # ลายเซ็น/รูปจากคลัง (ฝังตอนบันทึก)
    out = tmp / f"stamp-{label}.pdf"
    doc.save(out)
    assert close(image_rect(out), want), (label, image_rect(out))
    doc2 = PdfDocument(src)
    doc2.add_image(0, img, want)                          # แทรกรูปภาพ (ฝังทันที)
    out2 = tmp / f"image-{label}.pdf"
    doc2.save(out2)
    assert close(image_rect(out2), want), (label, image_rect(out2))
print(f"OK  บันทึกแล้วรูปอยู่ตรงตำแหน่ง/ขนาดที่วางไว้ ({', '.join(cases)})")

# ---- หน้าต่างโปรแกรม ----
src = make_pdf("doc.pdf")
w = MainWindow()
w.resize(1100, 800); w.show(); app.processEvents()
w._open_path(str(src)); app.processEvents()
w.viewer.set_zoom(1.0); app.processEvents()


def drag(overlay, start: QPoint, end: QPoint, shift: bool) -> None:
    mods = Qt.ShiftModifier if shift else Qt.NoModifier
    g0, g1 = overlay.mapToGlobal(start), overlay.mapToGlobal(end)
    app.sendEvent(overlay, QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(start), QPointF(g0),
                                       Qt.LeftButton, Qt.LeftButton, mods))
    app.sendEvent(overlay, QMouseEvent(QMouseEvent.MouseMove, QPointF(end), QPointF(g1),
                                       Qt.NoButton, Qt.LeftButton, mods))
    app.sendEvent(overlay, QMouseEvent(QMouseEvent.MouseButtonRelease, QPointF(end), QPointF(g1),
                                       Qt.LeftButton, Qt.NoButton, mods))


# ---- Shift + ลากมุม = ย่อ/ขยายโดยคงสัดส่วนรูป, ไม่กด Shift = ยืดได้อิสระเหมือนเดิม ----
w._start_image_placement(str(img), "")
ov = w.viewer.overlay
ov.setGeometry(300, 200, 200, 100)
corner = QPoint(ov.width() - 3, ov.height() - 3)
drag(ov, corner, corner + QPoint(150, 20), shift=True)
assert abs(ov.width() / ov.height() - 2.0) < 0.05, (ov.width(), ov.height())
assert ov.x() == 300 and ov.y() == 200, "มุมตรงข้ามต้องอยู่กับที่"
assert ov.width() > 300, "ต้องขยายตามที่ลาก"
top_left = QPoint(2, 2)
drag(ov, top_left, top_left + QPoint(100, 0), shift=True)       # ย่อจากมุมซ้ายบน
assert abs(ov.width() / ov.height() - 2.0) < 0.05, (ov.width(), ov.height())
right, bottom = ov.geometry().right(), ov.geometry().bottom()
corner = QPoint(ov.width() - 3, ov.height() - 3)
drag(ov, corner, corner + QPoint(0, 80), shift=False)
assert ov.height() / ov.width() > 0.6, "ไม่กด Shift ต้องยืดได้อิสระ"
w.cancel_placement(quiet=True)
print("OK  Shift + ลากมุม ย่อ/ขยายคงสัดส่วนรูป (ไม่กด Shift ยืดได้เหมือนเดิม)")

# ---- ลากไฟล์รูปจาก Explorer มาปล่อยบนหน้า -> เข้าโหมดวางรูปตรงจุดที่ปล่อย ----
mime = QMimeData()
mime.setUrls([QUrl.fromLocalFile(str(img))])
assert w._accepts_drop(mime), "เปิดไฟล์อยู่ ต้องรับไฟล์รูปได้"
viewport = w.viewer.viewport()
drop_at = viewport.mapTo(w, viewport.rect().center())
w.dropEvent(QDropEvent(QPointF(drop_at), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
ov = w.viewer.overlay
assert ov is not None and ov.isVisible(), "ปล่อยไฟล์รูปแล้วต้องเข้าโหมดวางรูป"
center_on_canvas = w.viewer._label.mapFrom(viewport, viewport.rect().center())
assert (ov.geometry().center() - center_on_canvas).manhattanLength() < 4, "รูปต้องอยู่ตรงจุดที่ปล่อย"
w.commit_placement(); app.processEvents()
assert len(w.doc.stamps) == 1, "ยืนยันแล้วรูปต้องลงหน้า (เป็นชั้นลอย ฝังตอนบันทึก)"
placed, placed_page = fitz.Rect(w.doc.stamps[0].rect), w.doc.stamps[0].page
out = tmp / "dropped.pdf"
w.doc.save(out)
assert close(image_rect(out, placed_page), placed), "บันทึกแล้วต้องอยู่ตรงที่วาง"
print("OK  ลากไฟล์รูปมาปล่อยบนหน้า PDF ได้ วางตรงจุดที่ปล่อย")

w.doc.dirty = False
w2 = MainWindow()
assert not w2._accepts_drop(mime), "ยังไม่เปิดไฟล์ ไม่รับไฟล์รูป (ไม่มีหน้าให้วาง)"
print("OK  ยังไม่เปิดไฟล์ ไม่รับการลากไฟล์รูป")

print("\nผ่านทั้งหมด")
