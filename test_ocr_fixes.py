"""ทดสอบคำแก้ OCR ภาษาไทย (2.2): กฎอัตโนมัติ + คำแก้ของผู้ใช้ + หน้าต่างตั้งค่า"""
import os, sys, tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QTableWidget, QTableWidgetItem
from app import i18n, pdfops
from app.main import MainWindow

# ---- กฎอัตโนมัติ (ไม่มีทางเป็นคำที่ถูก) ----
pdfops.set_ocr_corrections([])
fix = pdfops.fix_thai_ocr
assert fix("เเผนก") == "แผนก"
assert fix("ทํา") == "ทำ" and fix("ทํ า") == "ทำ"
assert fix("ค่่า") == "ค่า" and fix("กี้้") == "กี้"
assert fix("ฃอง ฅน") == "ของ คน"
assert fix("Invoice No. 123 ราคา 1,500 บาท") == "Invoice No. 123 ราคา 1,500 บาท", "ข้อความปกติต้องไม่เปลี่ยน"
print("OK  กฎอัตโนมัติ: เเ→แ, ํา→ำ, วรรณยุกต์ซ้ำ, ฃ→ข, ฅ→ค (ข้อความปกติไม่เปลี่ยน)")

# ---- คำแก้ของผู้ใช้: คำยาวก่อน แก้รอบเดียว ไม่แก้ซ้ำในคำที่แก้แล้ว ----
pdfops.set_ocr_corrections([["ษัท", "XX"], ["บรษัท", "บริษัท"], ["ซีเอสเอส", "CSS"]])
assert fix("บรษัท ซีเอสเอส ไทย") == "บริษัท CSS ไทย"
assert fix("ษัท") == "XX"
print("OK  คำแก้ของผู้ใช้ทำงาน คำยาวแก้ก่อน ไม่ไปแก้ซ้ำกลางคำที่แก้แล้ว")

# ---- ใช้ตอนต่อข้อความ OCR (แปลงเป็น Word) ----
spans = [{"text": "เ", "bbox": (0, 0, 5, 10)}, {"text": "เผนก", "bbox": (5, 0, 30, 10)},
         {"text": "บรษัท", "bbox": (60, 0, 90, 10)}]
assert pdfops._join_ocr_spans(spans) == "แผนก บริษัท"
print("OK  แปลงไฟล์สแกนเป็น Word ใช้คำแก้ด้วย")

# ---- หน้าต่างตั้งค่า: แก้ตาราง กดบันทึก -> จำไว้ และใช้ทันที ----
i18n.load_language()
app = QApplication.instance() or QApplication(sys.argv)
i18n.set_setting("ocr_fixes", [["ลูกค า", "ลูกค้า"]])
w = MainWindow()
assert pdfops.fix_thai_ocr("ลูกค า") == "ลูกค้า", "เปิดโปรแกรมแล้วต้องโหลดคำแก้ที่บันทึกไว้"


def edit_and_save(dialog):
    table = dialog.findChild(QTableWidget)
    assert table.rowCount() == 1 and table.item(0, 0).text() == "ลูกค า"
    table.insertRow(1)
    table.setItem(1, 0, QTableWidgetItem("ใบแจงหนี้"))
    table.setItem(1, 1, QTableWidgetItem("ใบแจ้งหนี้"))
    table.insertRow(2)                       # แถวว่าง -> ไม่บันทึก
    return QDialog.Accepted


with patch.object(QDialog, "exec", edit_and_save):
    w.ocr_fixes_dialog()
assert i18n.get_setting("ocr_fixes") == [["ลูกค า", "ลูกค้า"], ["ใบแจงหนี้", "ใบแจ้งหนี้"]]
assert pdfops.fix_thai_ocr("ส่งใบแจงหนี้ให้ลูกค า") == "ส่งใบแจ้งหนี้ให้ลูกค้า"
assert i18n.t("tools.ocr_fixes") in {a.text() for a in w.tool_actions}
print("OK  เครื่องมือ → คำแก้ OCR ภาษาไทย: เพิ่มคำ บันทึก ใช้ได้ทันทีและจำไว้")

print("\nผ่านทั้งหมด")
