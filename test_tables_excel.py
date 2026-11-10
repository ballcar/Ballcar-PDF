"""ทดสอบ 2.3.2: แปลงเป็น Excel จากไฟล์ที่ทำมาจาก Excel (ตารางหลายอันเรียงกันในหน้าเดียว)

เคยมีปัญหา (MEP.pdf): ตาราง 4 อันถูกรวบเป็นตารางเดียว มีหมายเหตุปนเข้ามา หัวตารางหาย
และภาษาไทยเพี้ยน (สระล่างไปต่อท้ายคำ, วรรณยุกต์ตัวยกกลายเป็น Ŗ ŕ É Ê)
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

import fitz
from openpyxl import load_workbook
from app.pdfops import PdfDocument, _fix_span, _tidy_thai

tmp = Path(tempfile.mkdtemp())
FONT = r"C:\Windows\Fonts\tahoma.ttf"

# หน้าแบบที่ Excel ส่งออก: เส้นแนวนอนยาวเท่ากันทุกตาราง, เส้นซ้าย/ขวาแยกตามตาราง
src = tmp / "stacked.pdf"
d = fitz.open()
page = d.new_page()
page.insert_font(fontname="th", fontfile=FONT)
X0, XM, X1 = 50, 200, 540


def table(top, title_inside, rows, title=None):
    y = top
    lines = [y]
    if title and not title_inside:
        page.insert_text((X0 + 120, top - 6), title, fontname="th", fontsize=11)
    if title and title_inside:
        page.insert_text((X0 + 120, y + 15), title, fontname="th", fontsize=11)
        y += 21
        lines.append(y)
    first_body = y
    for a, b in rows:
        page.insert_text((X0 + 4, y + 15), a, fontname="th", fontsize=10)
        page.insert_text((XM + 4, y + 15), b, fontname="th", fontsize=10)
        y += 21
        lines.append(y)
    for ly in lines:
        page.draw_rect(fitz.Rect(X0, ly - 0.6, X1, ly + 0.6), color=None, fill=(0, 0, 0))
    for x in (X0, X1):
        page.draw_rect(fitz.Rect(x - 0.6, top, x + 0.6, y), color=None, fill=(0, 0, 0))
    page.draw_rect(fitz.Rect(XM - 0.4, first_body, XM + 0.4, y), color=None, fill=(0, 0, 0))
    return y


end = table(120, False, [("ผู้สั่ง", "คุณเอกชัย"), ("ผู้อนุมัติ", "คุณภักดี"), ("ฝ่ายจัดซื้อ", "คุณอลิสรา")],
            title="ผู้มีอำนาจอนุมัติ ใบขอซื้อ RA/RS")
end = table(end + 20, True, [("ผู้รับมอบอำนาจ", "คุณโอภาส")], title="ใบสั่งซื้อ PA/PS")
page.insert_text((X0, end + 25), "หมายเหตุ : อำนาจอนุมัติยึดจากใบขอซื้อ", fontname="th", fontsize=10)
table(end + 60, True, [("ผู้สั่งสินค้า", "คุณภักดี"), ("ผู้รับมอบอำนาจ", "คุณโอภาส")], title="ใบสั่งซื้อ PO")
d.save(str(src)); d.close()

doc = PdfDocument(src)
tables = doc.find_tables(0)
assert len(tables) == 3, f"ตารางเรียงกัน 3 อัน ต้องแยกเป็น 3 ได้ {len(tables)}: {tables}"
assert tables[0][0][0] == "ผู้มีอำนาจอนุมัติ ใบขอซื้อ RA/RS", "หัวตารางที่อยู่เหนือกรอบต้องมาด้วย"
assert tables[0][1] == ["ผู้สั่ง", "คุณเอกชัย"] and len(tables[0]) == 4
assert tables[1] == [["ใบสั่งซื้อ PA/PS", ""], ["ผู้รับมอบอำนาจ", "คุณโอภาส"]], tables[1]
assert all("หมายเหตุ" not in c for t in tables for r in t for c in r), "หมายเหตุนอกกรอบต้องไม่ปนเข้าตาราง"
assert tables[2][-1] == ["ผู้รับมอบอำนาจ", "คุณโอภาส"]
print("OK  ตารางเรียงกันหลายอัน แยกถูก หัวตารางครบ หมายเหตุไม่ปน สระไม่เพี้ยน")

xlsx = tmp / "out.xlsx"
assert doc.to_excel(xlsx) == 3
book = load_workbook(xlsx)
assert book.sheetnames == ["หน้า1-ตาราง1", "หน้า1-ตาราง2", "หน้า1-ตาราง3"]
sheet = book["หน้า1-ตาราง2"]
assert [str(r) for r in sheet.merged_cells.ranges] == ["A1:B1"], "หัวตารางผสานช่องใน Excel"
assert sheet["A1"].value == "ใบสั่งซื้อ PA/PS" and sheet["A1"].font.bold
assert sheet["A2"].value == "ผู้รับมอบอำนาจ" and sheet["B2"].value == "คุณโอภาส"
print("OK  Excel: 1 ตาราง = 1 ชีต หัวตารางผสานช่อง ตัวหนา")

# ---- ทั้งเอกสาร (แบบ ABBYY): หัวเรื่อง/หมายเหตุ/ตาราง เรียงตามหน้า ชีตเดียว ----
whole = tmp / "whole.xlsx"
rows_written = doc.to_excel(whole, mode="document")
ws = load_workbook(whole).active
cells = [[c.value for c in row if c.value] for row in ws.iter_rows()]
cells = [r for r in cells if r]
flat = [v for r in cells for v in r]
assert ws.title == "เอกสาร" and rows_written >= 10
assert flat.index("ผู้มีอำนาจอนุมัติ ใบขอซื้อ RA/RS") < flat.index("ผู้สั่ง")     < flat.index("หมายเหตุ : อำนาจอนุมัติยึดจากใบขอซื้อ") < flat.index("ใบสั่งซื้อ PO"), "เรียงตามหน้า"
assert ["ผู้สั่ง", "คุณเอกชัย"] in cells, "ตารางยังอยู่เป็น 2 คอลัมน์"
assert flat.count("ผู้สั่ง") == 1, "ข้อความในตารางไม่ซ้ำเป็นย่อหน้าอีกรอบ"
note = [c for row in ws.iter_rows() for c in row if c.value and str(c.value).startswith("หมายเหตุ")][0]
assert note.font.size == 10
two = tmp / "pages.xlsx"
d2 = fitz.open(str(src)); d2.new_page().insert_text((72, 72), "หน้าสอง", fontname="th", fontfile=FONT)
d2.save(str(tmp / "two.pdf")); d2.close()
PdfDocument(tmp / "two.pdf").to_excel(two, mode="document", sheet_per_page=True)
assert load_workbook(two).sheetnames == ["หน้า 1", "หน้า 2"]
print("OK  ทั้งเอกสาร: ข้อความ + ตาราง เรียงตามหน้า ไม่ซ้ำ คงขนาดตัวอักษร · แยกชีตตามหน้าได้")

# ---- หน้าต่าง: เลือกแบบ -> จำแบบที่เลือกไว้ ----
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog
from app import i18n
from app.main import MainWindow
i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
w = MainWindow()
w._open_path(str(src)); app.processEvents()
out_ui = tmp / "ui.xlsx"
asked = []
def pick(parent, title, label, items, current, editable):
    asked.append((items, current))
    return items[2], True
with patch.object(w, "_ask_scope", return_value=[0]),         patch.object(QInputDialog, "getItem", side_effect=pick),         patch.object(QFileDialog, "getSaveFileName", return_value=(str(out_ui), "")):
    w.export_excel()
    assert asked[0][1] == 0, "ครั้งแรกเลือกทั้งเอกสารไว้ให้"
    assert load_workbook(out_ui).sheetnames == ["หน้า1-ตาราง1", "หน้า1-ตาราง2", "หน้า1-ตาราง3"]
    w.export_excel()
    assert asked[1][1] == 2, "จำแบบที่เลือกครั้งก่อน"
print("OK  เมนูแปลงเป็น Excel: เลือกแบบได้ จำแบบล่าสุด")

# ---- วรรณยุกต์ตัวยกที่โปรแกรมสร้าง PDF ไม่ได้บอกตัวจริง ----
fix = {"\u0156": "\u0e49", "\u0155": "\u0e48"}
assert _fix_span("ซื\u0156อ ชั\u0156น สั\u0155ง", fix) == "ซื้อ ชั้น สั่ง"
assert _fix_span("Ŗodo", fix) == "Ŗodo", "ตัวอักษรละตินจริง (ไม่ติดตัวไทย) ต้องไม่ถูกแก้"
assert _tidy_thai("อํานาจ") == "อำนาจ"
print("OK  แก้วรรณยุกต์ตัวยกเฉพาะที่ติดตัวไทย · ํา -> ำ")

real = Path(r"C:\Users\chayakul_b\Desktop\MEP.pdf")      # ไฟล์จริงจากออฟฟิศ (ไม่เอาเข้า repo)
if real.exists():
    mep = PdfDocument(real)
    tabs = mep.find_tables(0)
    assert [t[0][0] for t in tabs] == [
        "ผู้มีอำนาจอนุมัติ เอกสารใบขอซื้อ RA/RS", "ผู้มีอำนาจอนุมัติ เอกสารใบสั่งซื้อ PA/PS",
        "ผู้มีอำนาจอนุมัติ เอกสารใบขอซื้อ RO", "ผู้มีอำนาจอนุมัติ เอกสารใบสั่งซื้อ PO"], tabs
    assert tabs[0][1] == ["ผู้สั่ง", "คุณเอกชัย บุญศรี หรือผู้จัดทำเอกสาร"]
    import re
    for i in range(mep.page_count):
        odd = re.findall(r"[Ā-ɏÀ-ÿ]", mep.page_text(i))
        assert not odd, f"หน้า {i + 1}: ยังมีตัวเพี้ยน {odd}"
    assert "ขั้นตอนกระบวนการจัดซื้อ" in mep.page_text(1)
    print("OK  ไฟล์จริง MEP.pdf: 4 ตาราง หัวครบ ภาษาไทยถูก · ดึงข้อความหน้าแผนผังก็ถูก")

print("\nผ่านทั้งหมด")
