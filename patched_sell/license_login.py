"""
license_login.py — Login window for customers to activate their license.
Runs before Deepchart launches. Exits with code 0 on valid activation.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license_manager import LicenseManager, LicenseError


def main():
    lm = LicenseManager()

    # Auto-activate from .lic files
    lic_files = lm.find_license_files()
    if lic_files:
        for f in lic_files:
            try:
                result = lm.activate_from_file(f)
                print(f"[LICENSE] Activated from {f.name}!")
                print(f"[LICENSE] Expires: {result.get('expires_at', 'unknown')}")
                f.unlink()
                sys.exit(0)
            except LicenseError as e:
                print(f"[LICENSE] Failed: {e}")
                sys.exit(1)

    # No .lic file found — show info
    print("=" * 50)
    print("  Deepchart — License Required")
    print("=" * 50)
    print(f"  HWID: {lm.get_hwid_display()}")
    print()
    print("  Send this HWID to your reseller to get a .lic file.")
    print("  Place the .lic file in this folder and run again.")
    print("=" * 50)
    sys.exit(1)


if __name__ == "__main__":
    main()
