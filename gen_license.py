"""
gen_license.py — Generate license keys and signed .lic files for customers.

Usage:
  python gen_license.py --days 30 "CustomerName — notes"
  python gen_license.py --days 365 --hwid ABC123 "CustomerName"
  python gen_license.py --lic --days 30 --hwid ABC123 "CustomerName"
  python gen_license.py --list
  python gen_license.py --deactivate LICENSE-KEY
  python gen_license.py --reactivate LICENSE-KEY
  python gen_license.py --edit-note LICENSE-KEY "New note text"
"""
import base64
import json
import sqlite3
import secrets
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "licenses.db"
KEYS_DIR = Path(__file__).parent / "keys"


def _load_private_key():
    from cryptography.hazmat.primitives import serialization
    key_path = KEYS_DIR / "private.pem"
    if not key_path.exists():
        print("[!] No private key found. Generate one first with: python gen_keys.py")
        sys.exit(1)
    return serialization.load_pem_private_key(key_path.read_bytes(), password=None)


def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            hwid TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            last_checkin TEXT,
            note TEXT
        )
    """)
    conn.commit()
    conn.close()


def _format_key(raw: str) -> str:
    raw = raw.upper()[:20]
    return "-".join(raw[i:i+5] for i in range(0, len(raw), 5))


def _generate():
    raw = secrets.token_hex(10)
    return _format_key(raw)


def create_license(days: int, note: str = "", hwid: str = ""):
    _init_db()
    key = _generate()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO licenses (license_key, hwid, created_at, expires_at, active, note) VALUES (?, ?, ?, ?, 1, ?)",
        (key, hwid, now.isoformat(), expires.isoformat(), note),
    )
    conn.commit()
    conn.close()
    print(f"[+] License created: {key}")
    print(f"    Expires: {expires.isoformat()} ({days} days)")
    print(f"    Customer: {note}")
    if hwid:
        print(f"    Pre-bound HWID: {hwid}")
    return key


def sign_lic_file(key: str, days: int, note: str = "", hwid: str = ""):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = _load_private_key()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=days)

    lic_data = {
        "license_key": key,
        "hwid": hwid,
        "customer": note,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }

    payload = json.dumps(lic_data, separators=(",", ":"), sort_keys=True)
    signature = private_key.sign(payload.encode(), padding.PKCS1v15(), hashes.SHA256())
    lic_data["signature"] = base64.b64encode(signature).decode()

    lic_path = Path(__file__).parent / f"{key}.lic"
    lic_path.write_text(json.dumps(lic_data, indent=2), encoding="utf-8")
    print(f"[+] Signed .lic file: {lic_path}")
    print(f"    Expires: {expires.isoformat()} ({days} days)")
    print(f"    Customer: {note}")
    if hwid:
        print(f"    Pre-bound HWID: {hwid}")
    print(f"    Send this file to the customer.")
    return lic_path


def list_licenses():
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT license_key, hwid, created_at, expires_at, active, last_checkin, note FROM licenses ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        print("No licenses found.")
        return
    print(f"{'LICENSE KEY':<25} {'HWID':<16} {'ACTIVE':<7} {'EXPIRES':<25} {'LAST CHECKIN':<25} {'NOTE'}")
    print("-" * 120)
    for r in rows:
        active = "YES" if r[4] else "NO"
        hwid_short = (r[1] or "-")[:14]
        print(f"{r[0]:<25} {hwid_short:<16} {active:<7} {r[3][:19]:<25} {(r[5] or '-')[:19]:<25} {r[6] or ''}")


def deactivate(key: str):
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("UPDATE licenses SET active = 0 WHERE license_key = ?", (key.strip().upper(),))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    if affected:
        print(f"[-] Deactivated: {key}")
    else:
        print(f"[!] License not found: {key}")


def reactivate(key: str):
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("UPDATE licenses SET active = 1 WHERE license_key = ?", (key.strip().upper(),))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    if affected:
        print(f"[+] Reactivated: {key}")
    else:
        print(f"[!] License not found: {key}")


def update_note(key: str, note: str):
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("UPDATE licenses SET note = ? WHERE license_key = ?", (note, key.strip().upper()))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    if affected:
        print(f"[+] Note updated for: {key}")
        print(f"    Note: {note}")
    else:
        print(f"[!] License not found: {key}")


def delete_license(key: str):
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("DELETE FROM licenses WHERE license_key = ?", (key.strip().upper(),))
    conn.commit()
    affected = conn.total_changes
    conn.close()
    if affected:
        print(f"[-] Deleted: {key}")
    else:
        print(f"[!] License not found: {key}")


if __name__ == "__main__":
    _init_db()
    if "--list" in sys.argv:
        list_licenses()
    elif "--deactivate" in sys.argv:
        idx = sys.argv.index("--deactivate") + 1
        if idx < len(sys.argv):
            deactivate(sys.argv[idx])
        else:
            print("Usage: python gen_license.py --deactivate LICENSE-KEY")
    elif "--reactivate" in sys.argv:
        idx = sys.argv.index("--reactivate") + 1
        if idx < len(sys.argv):
            reactivate(sys.argv[idx])
        else:
            print("Usage: python gen_license.py --reactivate LICENSE-KEY")
    elif "--delete" in sys.argv:
        idx = sys.argv.index("--delete") + 1
        if idx < len(sys.argv):
            delete_license(sys.argv[idx])
        else:
            print("Usage: python gen_license.py --delete LICENSE-KEY")
    elif "--edit-note" in sys.argv:
        idx = sys.argv.index("--edit-note") + 1
        if idx + 1 < len(sys.argv):
            update_note(sys.argv[idx], sys.argv[idx + 1])
        else:
            print("Usage: python gen_license.py --edit-note LICENSE-KEY 'New note'")
    elif "--lic" in sys.argv and "--days" in sys.argv:
        didx = sys.argv.index("--days") + 1
        days = int(sys.argv[didx]) if didx < len(sys.argv) else 30
        hwid = ""
        note = ""
        if "--hwid" in sys.argv:
            hidx = sys.argv.index("--hwid") + 1
            if hidx < len(sys.argv):
                hwid = sys.argv[hidx].strip()
        key = _generate()
        params = []
        skip = False
        for a in sys.argv[1:]:
            if skip:
                skip = False
                continue
            if a == "--lic" or a == "--days" or a == "--hwid":
                skip = a in ("--days", "--hwid")
            elif not a.startswith("--"):
                params.append(a)
        note = " ".join(params)
        create_license(days, note, hwid)
        sign_lic_file(key, days, note, hwid)
    elif "--days" in sys.argv:
        idx = sys.argv.index("--days") + 1
        days = int(sys.argv[idx]) if idx < len(sys.argv) else 30
        hwid = ""
        note = ""
        if "--hwid" in sys.argv:
            hidx = sys.argv.index("--hwid") + 1
            if hidx < len(sys.argv):
                hwid = sys.argv[hidx].strip()
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        if args:
            params = []
            skip = False
            for a in sys.argv[1:]:
                if skip:
                    skip = False
                    continue
                if a == "--days":
                    skip = True
                elif a == "--hwid":
                    skip = True
                elif not a.startswith("--"):
                    params.append(a)
            note = " ".join(params)
        create_license(days, note, hwid)
    else:
        print("Usage:")
        print("  python gen_license.py --days 30 'CustomerName — notes'")
        print("  python gen_license.py --days 365 --hwid ABC123 'CustomerName'")
        print("  python gen_license.py --lic --days 30 --hwid ABC123 'Customer'")
        print("  python gen_license.py --list")
        print("  python gen_license.py --deactivate LICENSE-KEY")
        print("  python gen_license.py --reactivate LICENSE-KEY")
        print("  python gen_license.py --delete LICENSE-KEY")
        print("  python gen_license.py --edit-note LICENSE-KEY 'New note'")
