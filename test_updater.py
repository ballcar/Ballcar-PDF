"""ทดสอบระบบอัปเดตจากเซิร์ฟเวอร์ภายใน (HTTP)"""
import json, os, sys, tempfile, threading
from pathlib import Path
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["APPDATA"] = tempfile.mkdtemp()

from app import updater

# ---- เทียบเวอร์ชัน ----
assert updater.parse_version("1.0.43") == (1, 0, 43)
assert updater.is_newer("1.0.44", "1.0.43")
assert updater.is_newer("1.1.0", "1.0.99")
assert not updater.is_newer("1.0.43", "1.0.43")
assert not updater.is_newer("1.0.42", "1.0.43")
assert updater.parse_version("1.0.100") > updater.parse_version("1.0.99")   # ไม่ใช่เทียบตัวอักษร
print("OK  เทียบเวอร์ชันถูก (รวม 1.0.100 > 1.0.99)")

# ---- normalize url ----
assert updater.normalize_base_url("192.168.1.10:8000") == "http://192.168.1.10:8000"
assert updater.normalize_base_url("http://x:8000/") == "http://x:8000"
assert updater.normalize_base_url("") == ""
print("OK  เติม http:// + ตัด / ท้าย")

# ---- จำลองเซิร์ฟเวอร์จริง ----
srv_dir = Path(tempfile.mkdtemp())
(srv_dir / "Ballcar PDF Installer.exe").write_bytes(b"FAKE-INSTALLER-DATA" * 1000)
(srv_dir / "latest.json").write_text(json.dumps({
    "version": "1.0.44", "file": "Ballcar PDF Installer.exe", "notes": "ทดสอบ"
}), encoding="utf-8")

handler = partial(SimpleHTTPRequestHandler, directory=str(srv_dir))
httpd = HTTPServer(("127.0.0.1", 0), handler)
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}"

# มีเวอร์ชันใหม่กว่า
info = updater.check_for_update(base, "1.0.43")
assert info and info["version"] == "1.0.44", info
assert info["notes"] == "ทดสอบ"
assert info["url"].endswith("Ballcar%20PDF%20Installer.exe"), info["url"]
print(f"OK  ตรวจเจอเวอร์ชันใหม่จากเซิร์ฟเวอร์ ({info['version']})")

# เวอร์ชันเท่ากัน -> ไม่มีอัปเดต
assert updater.check_for_update(base, "1.0.44") is None
assert updater.check_for_update(base, "1.0.45") is None
print("OK  เวอร์ชันเท่ากัน/ใหม่กว่า -> ไม่แจ้งอัปเดต")

# ---- โหลด installer จริงจากเซิร์ฟเวอร์ ----
seen = []
path = updater.download_installer(info["url"], progress=lambda d, t: seen.append((d, t)))
assert path.exists() and path.stat().st_size == len(b"FAKE-INSTALLER-DATA" * 1000)
assert seen and seen[-1][0] == path.stat().st_size, "progress ต้องรายงานจนครบ"
print(f"OK  ดาวน์โหลด installer ได้ครบ ({path.stat().st_size} bytes)")

# ---- เซิร์ฟเวอร์ปิด/ต่อไม่ได้ -> คืน None เงียบๆ ไม่ throw ----
assert updater.check_for_update("http://127.0.0.1:59999", "1.0.0", timeout=1.0) is None
assert updater.check_for_update("", "1.0.0") is None
assert updater.check_for_update("ไม่ใช่ url", "1.0.0", timeout=1.0) is None
print("OK  ต่อเซิร์ฟเวอร์ไม่ได้ -> เงียบ ไม่พัง")

# ---- latest.json เสีย -> ไม่พัง ----
(srv_dir / "latest.json").write_text("{ พัง ", encoding="utf-8")
assert updater.check_for_update(base, "1.0.0") is None
print("OK  latest.json เสีย -> ไม่พัง")

httpd.shutdown()

# ---- settings เก็บ update_url โดยไม่ลบ language ----
from app import i18n
i18n.set_setting("language", "en")
i18n.set_setting("update_url", "http://192.168.1.10:8000")
assert i18n.get_setting("language") == "en", "ตั้ง update_url ต้องไม่ลบ language"
assert i18n.get_setting("update_url") == "http://192.168.1.10:8000"
i18n.set_setting("language", "th")            # คืนค่าเดิม
assert i18n.get_setting("update_url") == "http://192.168.1.10:8000", "เปลี่ยนภาษาต้องไม่ลบ url"
print("OK  settings เก็บหลายค่าไม่ทับกัน (language + update_url)")

print("\nผ่านทั้งหมด")


# ---- ค่าเริ่มต้นที่ฝังไว้ (เครื่องลูกไม่ต้องตั้งเอง) ----
assert updater.DEFAULT_UPDATE_URL.startswith("http://"), updater.DEFAULT_UPDATE_URL
# เครื่องใหม่ (settings ว่าง) ต้องมีค่า default ให้ใช้
import os, tempfile
os.environ["APPDATA"] = tempfile.mkdtemp()     # จำลองเครื่องใหม่
from app import i18n as _i18n
assert _i18n.get_setting("update_url", "") == "", "เครื่องใหม่ยังไม่มีค่าที่ตั้งเอง"
effective = _i18n.get_setting("update_url", "") or updater.DEFAULT_UPDATE_URL
assert effective == updater.DEFAULT_UPDATE_URL
print(f"OK  เครื่องใหม่ใช้ค่าเริ่มต้นที่ฝังไว้ ({effective})")


# ---- ค่าเริ่มต้นต้องเป็น IP (บางเครื่องแปลชื่อเครื่องไม่ออก) + มีชื่อเครื่องเป็นตัวสำรอง ----
import re
assert re.match(r"^http://\d+\.\d+\.\d+\.\d+:\d+$", updater.DEFAULT_UPDATE_URL), \
    f"ค่าเริ่มต้นควรเป็น IP ได้ {updater.DEFAULT_UPDATE_URL}"
assert any("CHAYAKUL" in u.upper() for u in updater.FALLBACK_UPDATE_URLS), \
    "ควรมีชื่อเครื่องเป็นตัวสำรอง เผื่อ IP เปลี่ยนตาม DHCP"
print(f"OK  ค่าเริ่มต้นเป็น IP ({updater.DEFAULT_UPDATE_URL}) + มีตัวสำรอง")

# ---- ลำดับการลอง: ที่ผู้ใช้ตั้งเองมาก่อนเสมอ แล้วไม่ซ้ำกัน ----
order = updater.candidate_urls("http://10.0.0.9:8000")
assert order[0] == "http://10.0.0.9:8000", f"ที่ตั้งเองต้องมาก่อน ได้ {order[0]}"
assert updater.DEFAULT_UPDATE_URL in order
assert len(order) == len(set(order)), "ต้องไม่มีที่อยู่ซ้ำ"
assert updater.candidate_urls("")[0] == updater.DEFAULT_UPDATE_URL
# ตั้งเองซ้ำกับค่าเริ่มต้น ต้องไม่ลองสองรอบ
assert updater.candidate_urls(updater.DEFAULT_UPDATE_URL).count(updater.DEFAULT_UPDATE_URL) == 1
print("OK  ลำดับการลอง: ที่ตั้งเองมาก่อน ไม่ซ้ำ")

# ---- ต่อที่แรกไม่ติด ต้องไล่ลองที่ถัดไปจนเจอ ----
srv_dir2 = Path(tempfile.mkdtemp())
(srv_dir2 / "Ballcar PDF Installer.exe").write_bytes(b"X" * 10)
(srv_dir2 / "latest.json").write_text(json.dumps({"version": "9.9.9"}), encoding="utf-8")
httpd2 = HTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(srv_dir2)))
port2 = httpd2.server_address[1]
threading.Thread(target=httpd2.serve_forever, daemon=True).start()
good = f"http://127.0.0.1:{port2}"
dead = "http://127.0.0.1:59998"          # ไม่มีอะไรฟังอยู่

orig_default, orig_fb = updater.DEFAULT_UPDATE_URL, updater.FALLBACK_UPDATE_URLS
updater.DEFAULT_UPDATE_URL = dead
updater.FALLBACK_UPDATE_URLS = [good]
info2 = updater.check_for_update_any("", "1.0.0", timeout=1.0)
assert info2 and info2["version"] == "9.9.9", f"ต้องข้ามที่ตายไปเจอที่ดี ได้ {info2}"
assert info2["url"].startswith(good), "ต้องโหลดจากที่อยู่ที่ต่อติดจริง"
print("OK  ที่แรกต่อไม่ติด -> ไล่ลองตัวสำรองจนเจอ")

# ---- ต่อติดแล้วแต่ไม่มีอัปเดต ต้องหยุด ไม่ไปลองที่อื่นต่อ ----
reachable, info3 = updater.probe(good, "9.9.9", timeout=1.0)
assert reachable is True and info3 is None, "ต่อติดแต่เวอร์ชันเท่ากัน -> (True, None)"
assert updater.probe(dead, "1.0.0", timeout=1.0) == (False, None)
print("OK  แยก 'ต่อไม่ติด' ออกจาก 'ต่อติดแต่ไม่มีอัปเดต'")

# ---- ทุกที่อยู่ต่อไม่ติด -> None เงียบๆ ไม่ throw ----
updater.FALLBACK_UPDATE_URLS = ["http://127.0.0.1:59997"]
assert updater.check_for_update_any("", "1.0.0", timeout=1.0) is None
print("OK  ต่อไม่ติดทุกที่ -> เงียบ ไม่พัง")

updater.DEFAULT_UPDATE_URL, updater.FALLBACK_UPDATE_URLS = orig_default, orig_fb
httpd2.shutdown()

print("\nผ่านทั้งหมด (รวมค่าเริ่มต้น + ตัวสำรอง)")
