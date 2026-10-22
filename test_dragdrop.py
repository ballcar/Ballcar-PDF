"""ทดสอบลากไฟล์ PDF จาก Explorer มาแทรกในงานที่เปิดอยู่"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(tmp / "appdata")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtCore import QMimeData, QPoint, QPointF, QUrl, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication
from app.main import MainWindow, ThumbList, pdf_paths_from_mime
from app.pdfops import PdfDocument


def make(name, pages):
    doc = fitz.open()
    for i in range(pages):
        doc.new_page(width=400, height=300).insert_text((50, 60), f"{name}-p{i+1}", fontsize=14)
    path = tmp / f"{name}.pdf"
    doc.save(str(path)); doc.close()
    return path


base = make("BASE", 4)
add1 = make("ADD1", 2)
add2 = make("ADD2", 3)
not_pdf = tmp / "note.txt"; not_pdf.write_text("hi")

app = QApplication.instance() or QApplication(sys.argv)


def mime_for(paths):
    m = QMimeData()
    m.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    return m


# ---- อ่านไฟล์ PDF จากสิ่งที่ลากมา ----
assert pdf_paths_from_mime(mime_for([add1, add2])) == [str(add1), str(add2)]
assert pdf_paths_from_mime(mime_for([not_pdf])) == [], "ไฟล์ที่ไม่ใช่ PDF ต้องไม่รับ"
assert pdf_paths_from_mime(mime_for([tmp / "ghost.pdf"])) == [], "ไฟล์ที่ไม่มีอยู่ต้องไม่รับ"
assert pdf_paths_from_mime(QMimeData()) == []
print("OK  คัดเฉพาะไฟล์ .pdf ที่มีอยู่จริงจากสิ่งที่ลากมา")


def fresh(path=base):
    w = MainWindow()
    w.doc = PdfDocument(path); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
    w.resize(1000, 700); w.show(); app.processEvents()
    return w


def drop_on_thumbs(w, paths, row):
    """จำลองลากไฟล์มาปล่อยบนหน้าย่อแถวที่ row (ครึ่งบน = แทรกก่อนหน้านั้น)"""
    rect = w.thumbs.visualRect(w.thumbs.model().index(row, 0))
    pos = QPointF(rect.center().x(), rect.top() + 2)      # ครึ่งบน
    m = mime_for(paths)
    enter = QDragEnterEvent(pos.toPoint(), Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
    w.thumbs.dragEnterEvent(enter)
    accepted = enter.isAccepted()
    drop = QDropEvent(pos, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
    w.thumbs.dropEvent(drop)
    app.processEvents()
    return accepted


# ---- ลากมาปล่อยบนหน้าย่อ -> แทรกตรงตำแหน่งนั้น ----
w = fresh()
assert w.doc.page_count == 4
accepted = drop_on_thumbs(w, [add1], row=1)      # ปล่อยครึ่งบนของหน้า 2 = แทรกก่อนหน้า 2
assert accepted, "ต้องรับการลาก (ก่อนหน้านี้ขึ้นเครื่องหมายห้าม)"
assert w.doc.page_count == 6, f"4+2 = 6 หน้า ได้ {w.doc.page_count}"
# ลำดับ: BASE1, ADD1-1, ADD1-2, BASE2, BASE3, BASE4
assert "BASE-p1" in w.doc.page_text(0)
assert "ADD1-p1" in w.doc.page_text(1) and "ADD1-p2" in w.doc.page_text(2)
assert "BASE-p2" in w.doc.page_text(3)
print("OK  ลากไฟล์มาปล่อยบนหน้าย่อ -> แทรกตรงตำแหน่งที่ปล่อย")

# undo ครั้งเดียวเอาออกหมด
w.undo()
assert w.doc.page_count == 4
print("OK  undo การลากแทรก = ครั้งเดียว")

# ---- ลากหลายไฟล์พร้อมกัน ----
w = fresh()
drop_on_thumbs(w, [add1, add2], row=0)
assert w.doc.page_count == 9, f"4+2+3 = 9 ได้ {w.doc.page_count}"
assert "ADD1-p1" in w.doc.page_text(0) and "ADD2-p1" in w.doc.page_text(2)
print("OK  ลากหลายไฟล์พร้อมกันได้ (แทรกเรียงตามลำดับ)")

# ---- ปล่อยที่ว่างท้ายรายการ -> ต่อท้าย ----
w = fresh()
m = mime_for([add1])
far = QPointF(w.thumbs.viewport().width() / 2, w.thumbs.viewport().height() - 2)
w.thumbs.dropEvent(QDropEvent(far, Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier))
app.processEvents()
assert w.doc.page_count == 6
assert "ADD1-p1" in w.doc.page_text(4), "ปล่อยที่ว่างควรต่อท้าย"
print("OK  ปล่อยที่ว่างท้ายรายการ -> ต่อท้ายเอกสาร")

# ---- ปล่อยบนหน้าต่าง (นอกแถบหน้าย่อ) -> ต่อท้าย ----
w = fresh()
m_win = mime_for([add2])          # ต้องเก็บ reference ไว้ ไม่งั้นถูก GC
enter = QDragEnterEvent(QPoint(600, 400), Qt.CopyAction, m_win,
                        Qt.LeftButton, Qt.NoModifier)
w.dragEnterEvent(enter)
assert enter.isAccepted(), "หน้าต่างต้องรับการลากไฟล์"
drop_win = QDropEvent(QPointF(600, 400), Qt.CopyAction, m_win,
                      Qt.LeftButton, Qt.NoModifier)
w.dropEvent(drop_win)
app.processEvents()
assert w.doc.page_count == 7, f"4+3 = 7 ได้ {w.doc.page_count}"
print("OK  ปล่อยที่หน้าเอกสาร -> ต่อท้าย")

# ---- ยังไม่เปิดไฟล์ -> ลากมาแล้วเปิดให้เลย ----
w = MainWindow(); w.doc = None; w.show(); app.processEvents()
w._on_pdfs_dropped([str(add1)], 0)
assert w.doc is not None and w.doc.page_count == 2, "ต้องเปิดไฟล์ที่ลากมา"
print("OK  ยังไม่เปิดไฟล์ ลากมาแล้วเปิดให้เลย")

# ยังไม่เปิดไฟล์ + ลากหลายไฟล์ -> เปิดไฟล์แรก ที่เหลือต่อท้าย
w = MainWindow(); w.doc = None; w.show(); app.processEvents()
w._on_pdfs_dropped([str(add1), str(add2)], 0)
assert w.doc.page_count == 5, f"2+3 = 5 ได้ {w.doc.page_count}"
print("OK  ยังไม่เปิดไฟล์ + หลายไฟล์ -> เปิดตัวแรก ที่เหลือต่อท้าย")

# ---- ลากไฟล์ที่ไม่ใช่ PDF -> ไม่รับ ไม่เปลี่ยนอะไร ----
w = fresh()
before = w.doc.page_count
m_txt = mime_for([not_pdf])       # เก็บ reference ไว้
enter = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, m_txt,
                        Qt.LeftButton, Qt.NoModifier)
w.thumbs.dragEnterEvent(enter)
assert not enter.isAccepted(), "ไฟล์ที่ไม่ใช่ PDF ต้องไม่รับ"
assert w.doc.page_count == before
print("OK  ลากไฟล์ที่ไม่ใช่ PDF ไม่รับ ไม่เปลี่ยนเอกสาร")

# ---- ลากสลับลำดับภายในยังทำงาน (ไม่ถูกทับ) ----
w = fresh()
assert w.thumbs.dragDropMode() == ThumbList.InternalMove, "ต้องยังลากสลับลำดับได้"
w.doc.reorder_pages([3, 0, 1, 2])
w._refresh_all(keep_row=0)
assert "BASE-p4" in w.doc.page_text(0), "สลับลำดับยังทำงาน"
print("OK  ลากสลับลำดับหน้าภายในยังทำงานเหมือนเดิม")

print("\nผ่านทั้งหมด")
