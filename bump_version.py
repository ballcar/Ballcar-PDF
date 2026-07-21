"""เพิ่มเลขเวอร์ชันอัตโนมัติ (รันตอน build)

กติกา: patch +1 ไปเรื่อยๆ ถึง .99 แล้วปัดขึ้น minor
    1.0.1 -> 1.0.2 -> ... -> 1.0.99 -> 1.1.0 -> 1.1.1 -> ...
"""
import json
import sys
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent / "version.json"
PATCH_MAX = 99


def read_version() -> str:
    if not VERSION_FILE.exists():
        return "1.0.1"
    return json.loads(VERSION_FILE.read_text(encoding="utf-8"))["version"]


def next_version(current: str) -> str:
    major, minor, patch = (int(part) for part in current.split("."))
    if patch >= PATCH_MAX:
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump() -> str:
    new = next_version(read_version())
    VERSION_FILE.write_text(
        json.dumps({"version": new}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return new


if __name__ == "__main__":
    if "--show" in sys.argv:
        print(read_version())
    else:
        print(bump())
