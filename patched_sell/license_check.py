"""
license_check.py — Development mode: always validates as OK.
"""
import sys


def main():
    print("[LICENSE] Development mode — license check bypassed")
    sys.exit(0)


if __name__ == "__main__":
    main()
