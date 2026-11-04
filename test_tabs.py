"""ทดสอบแท็บ (2.1): เปิดหลายไฟล์ในหน้าต่างเดียว, สลับแท็บจำหน้าเดิม, ปิดแท็บ, เปิดไฟล์จาก Explorer มาเป็นแท็บ"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication, QMessageBox
from app import i18n
from app import main as M

i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
tmp = Path(tempfile.mkdtemp())


def make(name: str, pages: int) -> Path:
    d = fitz.open()
    for n in range(pages):
        d.new_page().insert_text((72, 100), f"{name}-{n + 1}", fontsize=20)
    p = tmp / name
    d.save(str(p)); d.close()
    return p


a, b, c = make("a.pdf", 5), make("b.pdf", 3), make("c.pdf", 2)
w = M.MainWindow()
w.resize(1200, 800); w.show(); app.processEvents()
assert w.tab_bar.isHidden(), "ยังไม่เปิดไฟล์ ไม่ต้องมีแถบแท็บ"

# ---- เปิดหลายไฟล์ = หลายแท็บ ----
w._open_path(str(a)); app.processEvents()
w.goto_page(3); app.processEvents()
w._open_path(str(b)); app.processEvents()
assert w.tab_bar.count() == 2 and w.tab_bar.isVisible()
assert w.doc.path.name == "b.pdf" and w.tab_bar.currentIndex() == 1
assert [w.tab_bar.tabText(i) for i in range(2)] == ["a.pdf", "b.pdf"]
print("OK  เปิดไฟล์ที่สอง = แท็บใหม่ ไฟล์แรกยังเปิดอยู่")

# ---- เปิดไฟล์ที่เปิดอยู่แล้ว = สลับไปแท็บนั้น ไม่เปิดซ้ำ; กลับมาแล้วอยู่หน้าเดิม ----
w._open_path(str(a)); app.processEvents()
assert w.tab_bar.count() == 2 and w.doc.path.name == "a.pdf"
assert w.viewer.index == 3, f"กลับมาแท็บเดิมต้องอยู่หน้าเดิม ได้หน้า {w.viewer.index + 1}"
assert w.thumbs.count() == 5
print("OK  เปิดไฟล์ที่เปิดอยู่แล้ว = สลับไปแท็บนั้น และกลับมาอยู่หน้าเดิม")

# ---- แก้ไขแล้วชื่อแท็บมี * ; สลับแท็บไม่ทำให้งานหาย ----
w.rotate_selected(90); app.processEvents()
assert w.tab_bar.tabText(0) == "a.pdf *"
w.tab_bar.setCurrentIndex(1); app.processEvents()
assert w.doc.path.name == "b.pdf" and not w.doc.dirty
w.tab_bar.setCurrentIndex(0); app.processEvents()
assert w.doc.dirty and w.doc.doc[3].rotation == 90
print("OK  แท็บที่แก้แล้วมี * และสลับไปมางานไม่หาย")

# ---- สลับแท็บระหว่างวางรูป = ยกเลิกการวางรูปค้าง ----
img = tmp / "i.png"
pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 20), False); pix.save(str(img))
w._start_image_placement(str(img), "")
assert w.viewer.placing
w.next_tab(); app.processEvents()
assert not w.viewer.placing and w.doc.path.name == "b.pdf"
print("OK  สลับแท็บแล้วโหมดวางรูปค้างถูกยกเลิก ไม่ไปวางผิดไฟล์")

# ---- ปิดแท็บ: ไม่ได้แก้ปิดเลย, แก้แล้วถามก่อน (กดยกเลิก = ไม่ปิด) ----
w._open_path(str(c)); app.processEvents()
assert w.close_tab(2) and w.tab_bar.count() == 2
with patch.object(QMessageBox, "question", return_value=QMessageBox.Cancel) as ask:
    assert not w.close_tab(0), "กดยกเลิกต้องไม่ปิด"
    assert ask.called and w.tab_bar.count() == 2
with patch.object(QMessageBox, "question", return_value=QMessageBox.Discard):
    assert w.close_tab(0)
assert w.tab_bar.count() == 1 and w.doc.path.name == "b.pdf"
print("OK  ปิดแท็บ: ไม่ได้แก้ปิดทันที · แก้แล้วถามก่อน")

# ---- ปิดแท็บสุดท้าย = กลับหน้าแรก ----
w.close_tab(); app.processEvents()
assert w.doc is None and w.tab_bar.isHidden() and w._doc_stack.currentWidget() is w.home
print("OK  ปิดแท็บสุดท้าย กลับหน้าแรก")

# ---- ดับเบิลคลิกไฟล์ใน Explorer ขณะโปรแกรมเปิดอยู่ = แท็บใหม่ในหน้าต่างเดิม ----
M._SINGLE_INSTANCE_KEY = M._SINGLE_INSTANCE_KEY + "-test-" + str(os.getpid())
server = M._listen_single_instance(w)
assert M._notify_running_instance(str(a)), "ต้องเจอโปรแกรมที่เปิดอยู่"
for _ in range(50):
    app.processEvents()
    if w.doc is not None:
        break
    QApplication.instance().thread().msleep(20)
assert w.doc is not None and w.doc.path.name == "a.pdf" and w.tab_bar.count() == 1
assert M._notify_running_instance(str(b))
for _ in range(50):
    app.processEvents()
    if w.tab_bar.count() == 2:
        break
    QApplication.instance().thread().msleep(20)
assert w.tab_bar.count() == 2 and w.doc.path.name == "b.pdf"
print("OK  เปิดไฟล์จาก Explorer/Outlook ขณะโปรแกรมเปิดอยู่ = แท็บใหม่ในหน้าต่างเดิม")

# ---- ปิดโปรแกรม: ถามทุกแท็บที่ยังไม่บันทึก ----
w.rotate_selected(90)
w.tab_bar.setCurrentIndex(0); app.processEvents()
w.rotate_selected(90)
with patch.object(QMessageBox, "question", return_value=QMessageBox.Discard) as ask:
    assert w.close()
    assert ask.call_count == 2, "สองแท็บที่ยังไม่บันทึกต้องถามทั้งสอง"
print("OK  ปิดโปรแกรม ถามทุกแท็บที่ยังไม่บันทึก")

print("\nผ่านทั้งหมด")
