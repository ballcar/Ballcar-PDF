"""ทดสอบลากเส้นแบ่งย่อ/ขยายแผงข้างได้"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication
from app.main import MainWindow
from app.pdfops import PdfDocument

tmp = Path(tempfile.mkdtemp())
doc = fitz.open()
for i in range(4):
    doc.new_page(width=595, height=842)
src = tmp / "t.pdf"; doc.save(str(src)); doc.close()

app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow()
w.doc = PdfDocument(src); w.viewer.set_document(w.doc); w._refresh_all(keep_row=0)
w.resize(1200, 800); w.show(); app.processEvents()

sp = w._splitter

# ---- ไม่มีการล็อกความกว้างสูงสุด (ต้นเหตุที่ลากไม่ได้) ----
BIG = 16777215        # QWIDGETSIZE_MAX = ค่าเริ่มต้น = ไม่ล็อก
for name, widget in (("แผงหน้าย่อ", sp.widget(0)), ("thumbs", w.thumbs),
                     ("แผง bookmark", w._bookmark_panel), ("แผงข้อความ", w.text_panel)):
    assert widget.maximumWidth() == BIG, f"{name} ยังถูกล็อกความกว้างสูงสุด ({widget.maximumWidth()})"
print("OK  ไม่มีแผงไหนถูกล็อกความกว้างสูงสุด")

# ---- ลากเส้นแบ่งขยายแผงหน้าย่อได้จริง ----
before = sp.sizes()[0]
sp.setSizes([420, 0, 1200 - 420, 0])
app.processEvents()
after = sp.sizes()[0]
assert after > before + 150, f"ลากขยายไม่ได้ ({before} -> {after})"
assert w.thumbs.width() > 300, f"thumbs ต้องกว้างตาม ได้ {w.thumbs.width()}"
print(f"OK  ลากขยายแผงหน้าย่อได้ ({before}px -> {after}px)")

# ---- ลากย่อเล็กลงได้ ----
sp.setSizes([100, 0, 1100, 0])
app.processEvents()
assert sp.sizes()[0] < 150, f"ย่อไม่ได้ ({sp.sizes()[0]})"
print(f"OK  ลากย่อแผงหน้าย่อได้ ({sp.sizes()[0]}px)")

# ---- เส้นแบ่งจับได้ (กว้างพอ) ----
assert sp.handleWidth() >= 5, f"เส้นแบ่งบางเกินจับยาก ({sp.handleWidth()}px)"
print(f"OK  เส้นแบ่งกว้าง {sp.handleWidth()}px จับลากได้")

# ---- ลากจนแผงหายทั้งอันไม่ได้ (กันงง) ----
assert not sp.childrenCollapsible(), "ไม่ควรให้ลากจนแผงหายทั้งอัน"
print("OK  ลากจนแผงหายทั้งอันไม่ได้")

# ---- ขยายหน้าต่าง: พื้นที่ที่เพิ่มต้องไปที่หน้าเอกสาร ไม่ใช่แผงหน้าย่อ ----
sp.setSizes([200, 0, 1000, 0]); app.processEvents()
left_before, viewer_before = sp.sizes()[0], sp.sizes()[2]
w.resize(1600, 800); app.processEvents()
left_after, viewer_after = sp.sizes()[0], sp.sizes()[2]
assert viewer_after > viewer_before + 200, \
    f"ขยายหน้าต่างแล้วหน้าเอกสารควรกว้างขึ้น ({viewer_before}->{viewer_after})"
assert abs(left_after - left_before) < 40, \
    f"แผงหน้าย่อไม่ควรกว้างขึ้นตาม ({left_before}->{left_after})"
print(f"OK  ขยายหน้าต่าง พื้นที่ไปที่หน้าเอกสาร ({viewer_before}->{viewer_after}px)")

# ---- เปิดแผง bookmark แล้วได้ความกว้างใช้งานได้ (ไม่ใช่ 0) ----
w._toggle_bookmark_panel(True)
app.processEvents()
assert w._bookmark_panel.isVisible()
assert sp.sizes()[1] >= 150, f"เปิดแผง bookmark ต้องได้ความกว้างใช้งานได้ ({sp.sizes()[1]})"
print(f"OK  เปิดแผง bookmark ได้ความกว้าง {sp.sizes()[1]}px")

# แล้วลากปรับได้ด้วย
sp.setSizes([150, 400, 600, 0]); app.processEvents()
assert sp.sizes()[1] > 300, "แผง bookmark ต้องลากขยายได้"
print("OK  แผง bookmark ลากขยายได้")

# ---- เปิดแผงข้อความแล้วได้ความกว้างใช้งานได้ ----
w._toggle_text_panel(True)
app.processEvents()
assert sp.sizes()[3] >= 150, f"เปิดแผงข้อความต้องได้ความกว้าง ({sp.sizes()[3]})"
print(f"OK  เปิดแผงข้อความได้ความกว้าง {sp.sizes()[3]}px")

print("\nผ่านทั้งหมด")


# ---- ภาพย่อโตตามความกว้างแผง แต่ไม่โตเกินพอดี ----
sp.setSizes([190, 0, 1000, 0]); app.processEvents()
w._rebuild_thumbs(0); app.processEvents()
narrow_icon = w.thumbs.iconSize().width()

sp.setSizes([420, 0, 780, 0]); app.processEvents()
w._rebuild_thumbs(0); app.processEvents()
wide_icon = w.thumbs.iconSize().width()

assert wide_icon > narrow_icon + 40, f"แผงกว้างขึ้น ภาพย่อควรโตตาม ({narrow_icon}->{wide_icon})"
assert wide_icon <= 210, f"ภาพย่อไม่ควรใหญ่เกิน ~200px (ได้ {wide_icon}) ไม่งั้นเห็นทีละหน้า"
print(f"OK  ภาพย่อโตตามแผง {narrow_icon}px -> {wide_icon}px (จำกัดไม่เกิน 200)")

# ---- มีตัวหน่วงสร้างภาพย่อใหม่ตอนลาก (ไม่เรนเดอร์ถี่) ----
assert w._thumb_resize_timer.isSingleShot() and w._thumb_resize_timer.interval() >= 100
print("OK  มีตัวหน่วง ไม่เรนเดอร์ภาพย่อถี่ตอนลาก")

print("\nผ่านทั้งหมด (รวมภาพย่อ)")
