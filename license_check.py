"""
license_check.py — Called by start_servers.ps1 to verify license.
Exits with code 0 if valid, 1 if invalid/missing.
"""
import os
import sys
from license_manager import LicenseManager, LicenseError

def main():
    server_url = os.environ.get("LICENSE_SERVER_URL", "").strip()
    if not server_url:
        print("[LICENSE] No license server configured — skipping check")
        sys.exit(0)

    lm = LicenseManager(server_url)

    if not lm.is_activated:
        print("[LICENSE] NOT ACTIVATED")
        print(f"[LICENSE] Your HWID: {lm.get_hwid_display()}")
        print(f"[LICENSE] To activate: python license_manager.py activate YOUR-LICENSE-KEY")
        sys.exit(1)

    valid, days, msg = lm.validate()
    if valid:
        print(f"[LICENSE] Valid — {days} days remaining ({msg})")
        sys.exit(0)
    else:
        print(f"[LICENSE] INVALID: {msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
