"""ตรวจ + โหลดอัปเดตจากเซิร์ฟเวอร์ภายใน (เครื่องพี่ปล่อยผ่าน HTTP)

ฝั่งเซิร์ฟเวอร์เก็บ 2 ไฟล์ในโฟลเดอร์เดียว:
  latest.json  = {"version": "1.0.44", "file": "Ballcar PDF Installer.exe", "notes": "..."}
  Ballcar PDF Installer.exe

ไคลเอนต์อ่าน latest.json เทียบเวอร์ชัน ถ้าใหม่กว่าก็โหลด installer มารันทับ
ใช้ urllib (มากับ Python ที่แพ็กใน .exe อยู่แล้ว) ไม่ต้องพึ่งไลบรารีนอก
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

# ค่าเริ่มต้นเซิร์ฟเวอร์อัปเดต (ฝังไว้ให้ทุกเครื่องชี้มาที่เครื่องพี่อัตโนมัติ)
# ใช้ IP เป็นหลัก เพราะบางเครื่องในวงแปลชื่อเครื่อง (NetBIOS/DNS) ไม่ออก แล้วต่อไม่ติดเงียบๆ
# แต่ IP เป็น DHCP เปลี่ยนได้ จึงมีชื่อเครื่องเป็นตัวสำรองไว้ลองต่อทีหลัง
# เครื่องลูกเปลี่ยนเองได้ที่เมนู ช่วยเหลือ > ตั้งค่าเซิร์ฟเวอร์อัปเดต
DEFAULT_UPDATE_URL = "http://192.168.9.123:8000"
FALLBACK_UPDATE_URLS = [
    "http://CHAYAKUL-ITDDEL:8000",     # ชื่อเครื่อง — ใช้ได้ถ้า IP เปลี่ยนตาม DHCP
    "http://192.168.9.122:8000",       # อีกใบของเครื่องเดียวกัน (Wi-Fi)
]


def candidate_urls(configured: str = "") -> list:
    """ลำดับที่อยู่ที่จะลองต่อ — ที่ผู้ใช้ตั้งเองมาก่อนเสมอ แล้วค่อยไล่ค่าเริ่มต้น/ตัวสำรอง"""
    urls = []
    for u in [configured, DEFAULT_UPDATE_URL, *FALLBACK_UPDATE_URLS]:
        u = normalize_base_url(u)
        if u and u not in urls:
            urls.append(u)
    return urls


def check_for_update_any(configured: str, current_version: str,
                         timeout: float = 2.0) -> dict | None:
    """ลองทีละที่อยู่จนกว่าจะต่อติด — กันเคสแปลชื่อเครื่องไม่ออก หรือ IP เปลี่ยน

    คืนผลจากที่แรกที่ตอบมาได้ (ถึงจะบอกว่าไม่มีอัปเดตก็ถือว่าติดต่อสำเร็จ แล้วหยุดลอง)
    """
    for url in candidate_urls(configured):
        reachable, info = probe(url, current_version, timeout)
        if reachable:
            return info
    return None


def parse_version(text: str) -> tuple:
    """'1.0.44' -> (1, 0, 44) สำหรับเทียบมากน้อย (ตัวที่ไม่ใช่เลขถือเป็น 0)"""
    parts = []
    for chunk in str(text).strip().split("."):
        num = "".join(c for c in chunk if c.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts) if parts else (0,)


def is_newer(server: str, current: str) -> bool:
    return parse_version(server) > parse_version(current)


def normalize_base_url(url: str) -> str:
    """เติม http:// ถ้าไม่มี และตัด / ท้ายทิ้ง"""
    url = (url or "").strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url


def probe(base_url: str, current_version: str, timeout: float = 3.0) -> tuple:
    """ลองต่อที่อยู่เดียว — คืน (ต่อติดไหม, ข้อมูลอัปเดตหรือ None)

    แยก "ต่อไม่ติด" ออกจาก "ต่อติดแต่ไม่มีอัปเดต" เพื่อให้ผู้เรียกรู้ว่าควรลองที่อยู่ถัดไปไหม
    """
    base = normalize_base_url(base_url)
    if not base:
        return (False, None)
    try:
        with urllib.request.urlopen(base + "/latest.json", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8-sig"))   # ทน BOM ที่ PowerShell อาจใส่นำหน้า
    except Exception:
        return (False, None)      # เซิร์ฟเวอร์ปิด/ต่อไม่ได้/ชื่อเครื่องแปลไม่ออก
    return (True, _build_info(base, data, current_version))


def _build_info(base: str, data: dict, current_version: str) -> dict | None:
    version = str(data.get("version", "")).strip()
    if not version or not is_newer(version, current_version):
        return None
    filename = data.get("file") or "Ballcar PDF Installer.exe"
    return {
        "version": version,
        "file": filename,
        "notes": data.get("notes", ""),
        "url": base + "/" + urllib.parse.quote(filename),
    }


def check_for_update(base_url: str, current_version: str, timeout: float = 3.0) -> dict | None:
    """คืนข้อมูลอัปเดตถ้ามีเวอร์ชันใหม่กว่า, None ถ้าไม่มี/ต่อไม่ได้ (ไม่ throw)

    คืน dict: {version, file, notes, url} — ตรวจที่อยู่เดียวตามที่ระบุ
    """
    return probe(base_url, current_version, timeout)[1]


def download_installer(url: str, progress=None, timeout: float = 30.0) -> Path:
    """โหลด installer ลงโฟลเดอร์ชั่วคราว คืน path — progress(bytes_done, bytes_total)"""
    dest = Path(tempfile.gettempdir()) / "BallcarPDF-Update-Installer.exe"
    req = urllib.request.Request(url, headers={"User-Agent": "BallcarPDF-Updater"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    return dest


def installed_app_exe() -> Path | None:
    """path ของ .exe ที่กำลังรัน (ใช้เปิดโปรแกรมใหม่หลังอัปเดต) — เฉพาะตอนเป็น .exe จริง"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return None


def apply_update(installer_path: str | Path) -> bool:
    """รัน installer ทับแบบเงียบ แล้วเปิดโปรแกรมใหม่ให้ (โปรแกรมนี้ต้องปิดตัวเองต่อ)

    ใช้ตัวช่วย (PowerShell แยกโปรเซส) เพราะโปรแกรมกำลังจะถูกปิดเพื่อเขียนทับไฟล์
    """
    installer_path = str(installer_path)
    app_exe = installed_app_exe()
    if app_exe is None:
        # รันจากซอร์ส (dev) — เปิด installer เฉยๆ ไม่ relaunch
        subprocess.Popen([installer_path], close_fds=True)
        return True
    # PowerShell: รอ installer เสร็จ (ปิดโปรแกรมเก่า+เขียนทับ) แล้วเปิดโปรแกรมใหม่
    ps = (
        f"Start-Process -Wait -FilePath '{installer_path}' "
        f"-ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'; "
        f"Start-Process -FilePath '{app_exe}'"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return True
