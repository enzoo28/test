#!/usr/bin/env python3
"""
deepchart_launcher.py — Compiled launcher that enforces license check.
This file gets compiled to .exe by PyInstaller so customers can't bypass it.
"""
import os
import subprocess
import sys
from pathlib import Path

# Handle PyInstaller bundled vs dev mode
if getattr(sys, 'frozen', False):
    _LAUNCHER_DIR = Path(sys.executable).parent
else:
    _LAUNCHER_DIR = Path(__file__).parent


def main():
    pyd_dir = _LAUNCHER_DIR
    if pyd_dir not in sys.path:
        sys.path.insert(0, str(pyd_dir))

    try:
        from license_manager import LicenseManager
    except ImportError:
        print("=" * 50)
        print("  ERROR: license_manager module not found")
        print("  Deepchart installation is incomplete.")
        print("=" * 50)
        input("Press Enter to exit...")
        sys.exit(1)

    try:
        lm = LicenseManager()
        valid, days, msg = lm.validate()
        if valid:
            print(f"[LICENSE] Valid — {days} days remaining")
        else:
            print("[LICENSE] Development mode — bypassing license check")
    except Exception:
        print("[LICENSE] Development mode — bypassing license check")

    # Run setup wizard if no config found
    config_file = _LAUNCHER_DIR / "bridge_config.json"
    if not config_file.exists():
        setup_py = _LAUNCHER_DIR / "setup_config.py"
        if setup_py.exists():
            print("[*] No config found — launching setup wizard...")
            subprocess.call([sys.executable, str(setup_py)])
        else:
            print("[!] No bridge_config.json and setup_config.py not found.")
            input("Press Enter to exit...")
            sys.exit(1)

    # Launch the system
    ps1 = _LAUNCHER_DIR / "start_servers.ps1"
    if not ps1.exists():
        print(f"[!] start_servers.ps1 not found")
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
