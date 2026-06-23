#!/usr/bin/env python3
import base64
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
from datetime import datetime, timezone
from pathlib import Path

_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvkY6CgJm48Pa4gYdBvPm
k/HC5mF4fTvPa2wjTRsSRxhwETp0OefuY6LYYSEZF1fXRsPciaeu77Xqq56baZQK
mkphnWfJREvyYCAi2tuefraksl9bqZ35Nnfrx0FgERd/8UzvD5/vzprQEeYc0zWK
+hhjoHHuxh+WNia44mXevmfnab4ZzwzeLRxKaiKIKP82Ag0tT+H6K0tmlJuQBgOP
XiWSks/m/bZSpjaGkdt0LUaEb13VhfD0XdmyH2YXBtt5MJ6n2M4o3Isr1aYWORUN
3YEzrQn4bPzP9V9FdQgdzCAk6V3EUbtPKA2IVOI4dzBbZnHpQnT7DNxVM5yYnDJ9
5QIDAQAB
-----END PUBLIC KEY-----"""

if getattr(sys, 'frozen', False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).parent

LICENSE_CACHE = _BASE / ".license"
LIC_FILES_GLOB = "*.lic"


def _get_hwid() -> str:
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
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


def _hwid_display(hwid: str) -> str:
    return "-".join(hwid[i:i+4] for i in range(0, len(hwid), 4))


class LicenseError(Exception):
    pass


class LicenseManager:
    def __init__(self):
        self.hwid = _get_hwid()
        self._public_key = None

    def _load_public_key(self):
        if self._public_key is None:
            try:
                from cryptography.hazmat.primitives import serialization
                self._public_key = serialization.load_pem_public_key(_PUBLIC_KEY_PEM.encode())
            except ImportError:
                raise LicenseError("cryptography library required")

    @property
    def is_activated(self) -> bool:
        return LICENSE_CACHE.exists()

    def _load_cache(self) -> dict:
        if not LICENSE_CACHE.exists():
            return {}
        try:
            return json.loads(LICENSE_CACHE.read_text())
        except Exception:
            return {}

    def _save_cache(self, data: dict):
        LICENSE_CACHE.write_text(json.dumps(data, indent=2))

    def get_hwid_display(self) -> str:
        return _hwid_display(self.hwid)

    def find_lic_files(self) -> list:
        return sorted(_BASE.glob(LIC_FILES_GLOB))

    def activate_from_file(self, lic_path: Path):
        try:
            data = json.loads(lic_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise LicenseError(f"Cannot read license file: {e}")

        signature_b64 = data.pop("signature", "")
        if not signature_b64:
            raise LicenseError("No signature in license file")

        self._load_public_key()
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        try:
            signature = base64.b64decode(signature_b64)
            self._public_key.verify(signature, payload.encode(), padding.PKCS1v15(), hashes.SHA256())
        except Exception:
            raise LicenseError("License signature invalid")

        expires_str = data.get("expires_at", "")
        if expires_str:
            expires = datetime.fromisoformat(expires_str)
            if expires < datetime.now(timezone.utc):
                raise LicenseError("License has expired")

        lic_hwid = data.get("hwid", "").strip()
        if lic_hwid and lic_hwid.upper() != self.hwid:
            raise LicenseError(f"Bound to another machine (HWID: {lic_hwid})")

        self._save_cache({
            "license_key": data.get("license_key", ""),
            "hwid": self.hwid,
            "expires_at": expires_str,
            "customer": data.get("customer", ""),
            "activated_at": datetime.now(timezone.utc).isoformat(),
        })
        return data

    def validate(self):
        local = self._load_cache()
        if not local:
            return False, 0, "Not activated"
        expires_str = local.get("expires_at", "")
        if expires_str:
            try:
                expires = datetime.fromisoformat(expires_str)
                remaining = (expires - datetime.now(timezone.utc)).days
                if expires < datetime.now(timezone.utc):
                    return False, 0, "License expired"
                return True, max(0, remaining), "Valid"
            except Exception:
                pass
        return False, 0, "Invalid license data"

    def deactivate(self):
        if LICENSE_CACHE.exists():
            LICENSE_CACHE.unlink()


class ActivationWindow:
    def __init__(self, lm: LicenseManager):
        self.lm = lm
        self.result = None
        self.root = tk.Tk()
        self.root.title("Deepchart — License Activation")
        self.root.geometry("520x320")
        self.root.resizable(False, False)
        self._build()

    def _build(self):
        tk.Label(self.root, text="Deepchart License Activation",
                 font=("Segoe UI", 14, "bold")).pack(pady=(15, 5))
        hwid = self.lm.get_hwid_display()
        tk.Label(self.root, text=f"Your HWID: {hwid}",
                 font=("Segoe UI", 10)).pack(pady=(0, 5))
        tk.Label(self.root, text="Send this HWID to your reseller to get a .lic file.",
                 font=("Segoe UI", 9), fg="gray").pack()

        frame = tk.Frame(self.root)
        frame.pack(pady=15)
        self._path_var = tk.StringVar()
        tk.Entry(frame, textvariable=self._path_var, width=50,
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(frame, text="Browse", command=self._browse,
                  font=("Segoe UI", 10)).pack(side=tk.LEFT)

        self._status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self._status_var,
                 font=("Segoe UI", 10), fg="green").pack(pady=(0, 10))

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Activate", command=self._activate,
                  font=("Segoe UI", 11, "bold"), bg="#4CAF50", fg="white",
                  padx=20, pady=5).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Exit", command=self.root.destroy,
                  font=("Segoe UI", 11), padx=20, pady=5).pack(side=tk.LEFT, padx=10)

    def _browse(self):
        path = tkinter.filedialog.askopenfilename(
            title="Select license file",
            filetypes=[("License files", "*.lic"), ("All files", "*.*")],
            initialdir=str(_BASE))
        if path:
            self._path_var.set(path)

    def _activate(self):
        path = self._path_var.get().strip()
        if not path:
            self._status_var.set("Select a .lic file first")
            return
        p = Path(path)
        if not p.exists():
            self._status_var.set("File not found")
            return
        try:
            result = self.lm.activate_from_file(p)
            days = (datetime.fromisoformat(result["expires_at"]) - datetime.now(timezone.utc)).days
            self._status_var.set(f"Activated! {days} days remaining")
            tk.messagebox.showinfo("Success", f"License activated!\n{result.get('customer', '')}\nExpires: {result['expires_at'][:10]}")
            try:
                p.unlink()
            except Exception:
                pass
            self.result = "ok"
            self.root.after(500, self.root.destroy)
        except LicenseError as e:
            self._status_var.set(f"Failed: {e}")
            tk.messagebox.showerror("Activation Failed", str(e))
        except Exception as e:
            self._status_var.set(f"Error: {e}")

    def show(self):
        self.root.mainloop()
        return self.result


def main():
    lm = LicenseManager()

    valid, days, msg = lm.validate()
    if valid:
        print(f"[LICENSE] Valid — {days} days remaining")
    else:
        print(f"[LICENSE] {msg}")
        gui = ActivationWindow(lm)
        gui.show()
        valid, days, msg = lm.validate()
        if not valid:
            print(f"[LICENSE] {msg}")
            sys.exit(1)

    ps1 = _BASE / "start_servers.ps1"
    if not ps1.exists():
        print("[!] start_servers.ps1 not found")
        input("Press Enter to exit...")
        sys.exit(1)

    try:
        rc = subprocess.call(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(ps1)])
        sys.exit(rc)
    except Exception as e:
        print(f"[!] Launch failed: {e}")
        input("Press Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
