"""ทดสอบว่าคลังลายเซ็นเดิม (PdfTool) ถูกย้ายมาชื่อใหม่ (BallcarPDF) ครบ"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, r"D:\Project\PDF")

fake_appdata = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(fake_appdata)

# จำลองของเดิมที่ผู้ใช้เก็บไว้แล้ว
old = fake_appdata / "PdfTool" / "signatures"
old.mkdir(parents=True)
(old / "ลายเซ็นผู้จัดการ.png").write_bytes(b"PNG-A")
(old / "ตราประทับ.png").write_bytes(b"PNG-B")

from app import library

new = library.library_dir()
assert new == fake_appdata / "BallcarPDF" / "signatures", new
names = sorted(p.name for p in new.glob("*.png"))
assert names == ["ตราประทับ.png", "ลายเซ็นผู้จัดการ.png"], names
assert (new / "ลายเซ็นผู้จัดการ.png").read_bytes() == b"PNG-A"
assert not old.exists(), "ของเดิมควรถูกย้าย ไม่ใช่ก๊อป"
print("OK  ย้ายคลังลายเซ็นเดิมมาชื่อใหม่ครบ")

# เรียกซ้ำต้องไม่พัง
assert library.library_dir() == new
print("OK  เรียกซ้ำไม่พัง")

# เครื่องใหม่ที่ไม่เคยมีของเดิม
os.environ["APPDATA"] = str(Path(tempfile.mkdtemp()))
fresh = library.library_dir()
assert fresh.exists() and list(fresh.glob("*.png")) == []
print("OK  เครื่องใหม่สร้างคลังว่างได้")

# มีทั้งของเดิมและของใหม่อยู่แล้ว -> ห้ามทับของใหม่
base = Path(tempfile.mkdtemp())
os.environ["APPDATA"] = str(base)
(base / "PdfTool" / "signatures").mkdir(parents=True)
(base / "PdfTool" / "signatures" / "เก่า.png").write_bytes(b"OLD")
(base / "BallcarPDF" / "signatures").mkdir(parents=True)
(base / "BallcarPDF" / "signatures" / "ใหม่.png").write_bytes(b"NEW")
result = library.library_dir()
assert (result / "ใหม่.png").read_bytes() == b"NEW", "ของใหม่ต้องไม่ถูกทับ"
print("OK  มีคลังใหม่อยู่แล้วไม่ถูกทับ")

print("\nผ่านทั้งหมด")
