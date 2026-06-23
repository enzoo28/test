"""
license_check.py — Offline license check for start_servers.ps1.
Looks for .lic files in the folder, activates from them, then validates locally.
Exits with code 0 if valid, 1 if invalid/missing.
"""
import sys
from license_manager import LicenseManager, LicenseError


def main():
    lm = LicenseManager()

    # Try to activate from any .lic files found
    lic_files = lm.find_license_files()
    if lic_files:
        for f in lic_files:
            print(f"[LICENSE] Found license file: {f.name}")
            try:
                result = lm.activate_from_file(f)
                print(f"[LICENSE] Activated! Expires: {result.get('expires_at', 'unknown')}")
                f.unlink()
                break
            except LicenseError as e:
                print(f"[LICENSE] Activation failed: {e}")
                sys.exit(1)

    if not lm.is_activated:
        print("[LICENSE] NOT ACTIVATED")
        print(f"[LICENSE] Your HWID: {lm.get_hwid_display()}")
        print("[LICENSE] Send your HWID to your reseller to get a .lic file")
        print("[LICENSE] Place the .lic file in this folder and re-run")
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
