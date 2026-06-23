"""
license_manager.py — Offline RSA-signed license verification.
Public key is baked in. No server required.
Can be compiled to .pyd with Cython for tamper resistance.
"""
import base64
import hashlib
import hmac
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

# ── RSA Public Key (baked in at compile time) ──────────────────────────
_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvkY6CgJm48Pa4gYdBvPm
k/HC5mF4fTvPa2wjTRsSRxhwETp0OefuY6LYYSEZF1fXRsPciaeu77Xqq56baZQK
mkphnWfJREvyYCAi2tuefraksl9bqZ35Nnfrx0FgERd/8UzvD5/vzprQEeYc0zWK
+hhjoHHuxh+WNia44mXevmfnab4ZzwzeLRxKaiKIKP82Ag0tT+H6K0tmlJuQBgOP
XiWSks/m/bZSpjaGkdt0LUaEb13VhfD0XdmyH2YXBtt5MJ6n2M4o3Isr1aYWORUN
3YEzrQn4bPzP9V9FdQgdzCAk6V3EUbtPKA2IVOI4dzBbZnHpQnT7DNxVM5yYnDJ9
5QIDAQAB
-----END PUBLIC KEY-----"""

# ── HMAC key for .license file integrity (tamper protection) ────────────
_LICENSE_HMAC_KEY = b"dc-lic-hmac-key-9f8a2b7e4c1d"  # 32 bytes

LICENSE_FILE = Path(__file__).parent / ".license"
LIC_FILES_GLOB = "*.lic"


def get_hwid() -> str:
    parts = []
    try:
        out = subprocess.check_output(
            "wmic baseboard get serialnumber", shell=True, stderr=subprocess.DEVNULL
        ).decode().strip().split("\n")[-1].strip()
        if out and "default" not in out.lower():
            parts.append(out)
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            "wmic diskdrive get serialnumber", shell=True, stderr=subprocess.DEVNULL
        ).decode().strip().split("\n")[-1].strip()
        if out:
            parts.append(out)
    except Exception:
        pass
    try:
        mac = uuid.getnode()
        if mac:
            parts.append(f"{mac:012x}")
    except Exception:
        pass
    if not parts:
        parts.append(platform.node())
        parts.append(sys.prefix)
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


class LicenseError(Exception):
    pass


class LicenseManager:
    def __init__(self):
        self.hwid = get_hwid()
        self._public_key = None

    def _load_public_key(self):
        if self._public_key is None:
            if not _HAS_CRYPTO:
                raise LicenseError("cryptography library required: pip install cryptography")
            self._public_key = serialization.load_pem_public_key(_PUBLIC_KEY_PEM.encode())

    @property
    def is_activated(self) -> bool:
        return LICENSE_FILE.exists()

    @staticmethod
    def _hmac_fields(data: dict) -> str:
        to_sign = {k: data[k] for k in ("license_key", "hwid", "expires_at", "activated_at", "last_checked") if k in data}
        payload = json.dumps(to_sign, separators=(",", ":"), sort_keys=True)
        return hmac.new(_LICENSE_HMAC_KEY, payload.encode(), hashlib.sha256).hexdigest()

    def _load_local(self) -> dict:
        if not LICENSE_FILE.exists():
            return {}
        try:
            data = json.loads(LICENSE_FILE.read_text())
            sig = data.pop("_hmac", "")
            if sig:
                expected = self._hmac_fields(data)
                if not hmac.compare_digest(expected, sig):
                    return {}  # Tampered
            return data
        except Exception:
            return {}

    def _save_local(self, data: dict):
        data["_hmac"] = self._hmac_fields(data)
        LICENSE_FILE.write_text(json.dumps(data, indent=2))

    def get_hwid_display(self) -> str:
        h = self.hwid
        return "-".join(h[i:i+4] for i in range(0, len(h), 4))

    def find_license_files(self) -> list:
        folder = Path(__file__).parent
        return sorted(folder.glob(LIC_FILES_GLOB))

    def activate_from_file(self, lic_path: str | Path) -> dict:
        lic_path = Path(lic_path)
        try:
            data = json.loads(lic_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise LicenseError(f"Cannot read license file: {e}")

        signature_b64 = data.pop("signature", "")
        if not signature_b64:
            raise LicenseError("No signature in license file")

        self._load_public_key()
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        try:
            signature = base64.b64decode(signature_b64)
            self._public_key.verify(signature, payload.encode(), padding.PKCS1v15(), hashes.SHA256())
        except Exception:
            raise LicenseError("License signature invalid — file has been tampered with")

        # Check expiry
        expires_str = data.get("expires_at", "")
        if expires_str:
            expires = datetime.fromisoformat(expires_str)
            if expires < datetime.now(timezone.utc):
                raise LicenseError("License has expired")

        # Check HWID if bound
        lic_hwid = data.get("hwid", "").strip()
        if lic_hwid and lic_hwid.upper() != self.hwid:
            raise LicenseError(f"License is bound to another machine (HWID: {lic_hwid})")

        now = datetime.now(timezone.utc)
        # Save to .license
        self._save_local({
            "license_key": data.get("license_key", ""),
            "hwid": self.hwid,
            "expires_at": expires_str,
            "customer": data.get("customer", ""),
            "activated_at": now.isoformat(),
            "last_checked": now.isoformat(),
        })

        return data

    def validate(self) -> tuple:
        local = self._load_local()
        if not local:
            return False, 0, "Not activated"

        now = datetime.now(timezone.utc)
        expires_str = local.get("expires_at", "")
        if not expires_str:
            return False, 0, "Invalid license data"

        try:
            expires = datetime.fromisoformat(expires_str)
        except Exception:
            return False, 0, "Invalid expiry date"

        # Detect clock rollback
        last_checked_str = local.get("last_checked", "")
        if last_checked_str:
            try:
                last_checked = datetime.fromisoformat(last_checked_str)
                if now < last_checked:
                    return False, 0, "System clock was rolled back — license invalidated"
            except Exception:
                pass

        # Track time to prevent replay of old .license files
        local["last_checked"] = now.isoformat()
        self._save_local(local)

        if expires < now:
            return False, 0, "License expired"

        remaining = (expires - now).days
        return True, max(0, remaining), "Valid"

    def deactivate_local(self):
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()


if __name__ == "__main__":
    lm = LicenseManager()
    action = sys.argv[1] if len(sys.argv) > 1 else "status"

    if action == "hwid":
        print(f"HWID: {lm.get_hwid_display()}")
    elif action == "status":
        valid, days, msg = lm.validate()
        if valid:
            print(f"[LICENSE] Valid — {days} days remaining ({msg})")
        else:
            print(f"[LICENSE] {msg}")
        print(f"    HWID: {lm.get_hwid_display()}")
    elif action == "activate":
        lic_files = lm.find_license_files()
        if not lic_files:
            print("[LICENSE] No .lic files found in this folder")
            print("[LICENSE] Place a .lic file in the folder or contact your reseller")
            sys.exit(1)
        for f in lic_files:
            print(f"[LICENSE] Found: {f.name}")
            try:
                result = lm.activate_from_file(f)
                print(f"[LICENSE] Activated! Expires: {result.get('expires_at', 'unknown')}")
                print(f"[LICENSE] Customer: {result.get('customer', '')}")
                # Remove the .lic file after successful activation
                f.unlink()
                sys.exit(0)
            except LicenseError as e:
                print(f"[LICENSE] Failed: {e}")
                sys.exit(1)
    elif action == "deactivate":
        lm.deactivate_local()
        print("[LICENSE] Local license removed")
    else:
        print("Usage: python license_manager.py [hwid|status|activate|deactivate]")
