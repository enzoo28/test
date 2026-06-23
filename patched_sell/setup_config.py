#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
import getpass

_HERE = Path(__file__).parent
CONFIG_FILE = _HERE / "bridge_config.json"
CACHE_FILE = _HERE / ".config_cache.json"

DEFAULTS = {
    "cqg": {"user": "demo87820", "password": "AMPDemo1"},
    "rithmic": {"system": "Rithmic Paper Trading Chicago", "url": ""},
}


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_cache(values):
    CACHE_FILE.write_text(json.dumps(values, indent=2))


def prompt(question, default=None, password=False):
    if default is not None:
        hint = " (hidden)" if password else f" [{default}]"
        full = f"{question}{hint}: "
    else:
        full = f"{question}: "
    while True:
        val = getpass.getpass(full) if password else input(full).strip()
        if val:
            return val
        if default is not None:
            return default


def select_option(question, options):
    print(f"\n{question}")
    for i, (key, desc) in enumerate(options, 1):
        print(f"  {i}. {key} — {desc}")
    while True:
        try:
            idx = int(input(f"Enter number (1-{len(options)}): ").strip()) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass
        print(f"Invalid choice. Enter 1-{len(options)}.")


def has_valid_config(config):
    ds = config.get("data_source")
    if ds == "cqg":
        return True
    if ds == "rithmic":
        r = config.get("rithmic", {})
        return bool(r.get("user")) and bool(r.get("password"))
    if ds == "dxfeed":
        return True
    return False


def build_cqg():
    print("\n--- CQG Configuration ---")
    print("CQG uses a free AMP demo account. No registration needed.")
    print(f"  User:     {DEFAULTS['cqg']['user']}")
    print(f"  Password: {DEFAULTS['cqg']['password']}")
    return {
        "data_source": "cqg",
        "rithmic": {"user": "", "password": "", "system": DEFAULTS["rithmic"]["system"], "url": ""},
        "cqg": dict(DEFAULTS["cqg"]),
    }


def build_rithmic(cache):
    print("\n--- Rithmic Configuration ---")
    print("Enter your Rithmic broker credentials provided by your broker (e.g. AMP, Rithmic, etc.).")
    user = prompt("Rithmic username (email from your broker)", default=cache.get("rithmic_user"))
    password = prompt("Rithmic password", password=True)
    system = prompt("System name (press Enter for paper trading)",
                    default=cache.get("rithmic_system") or DEFAULTS["rithmic"]["system"])
    url = prompt("Gateway URL (from your broker, optional)",
                 default=cache.get("rithmic_url") or "")
    cache.update(rithmic_user=user, rithmic_system=system, rithmic_url=url)
    save_cache(cache)
    return {
        "data_source": "rithmic",
        "rithmic": {"user": user, "password": password, "system": system, "url": url},
        "cqg": dict(DEFAULTS["cqg"]),
    }


def build_dxfeed():
    print("\n--- DXFeed Configuration ---")
    print("DXFeed is a paid data feed. You need your own DXFeed account.")
    print("After launching Deepchart, configure your DXFeed credentials in:")
    print("  Data Sources -> Add -> DXFeed")
    return {
        "data_source": "dxfeed",
        "dxfeed": {"_comment": "Configure credentials in Deepchart UI after launch"},
        "rithmic": {"user": "", "password": "", "system": DEFAULTS["rithmic"]["system"], "url": ""},
        "cqg": dict(DEFAULTS["cqg"]),
    }


def finalize(base):
    base["bridge"] = {"port": 443, "bind_host": "0.0.0.0"}
    base["cqg_server_override"] = {"host": "208.48.16.22", "port": 443, "sni": "demoapi.cqg.com"}
    base["license"] = {"_comment": "Offline license. Place a .lic file in the Deepchart folder to activate."}
    return base


def main():
    print("=" * 60)
    print("  DEEPCHART - Bridge Configuration Setup")
    print("=" * 60)
    print()
    print("This configures how Deepchart connects to market data feeds.")
    print("You can also edit bridge_config.json manually at any time.")
    print()

    cache = load_cache()

    if CONFIG_FILE.exists():
        try:
            existing = json.loads(CONFIG_FILE.read_text())
            if has_valid_config(existing):
                ans = input("Existing config found. Reconfigure? (y/N): ").strip().lower()
                if ans != "y":
                    print("Keeping existing config.")
                    return
        except Exception:
            pass

    mode = select_option("Select data source:", [
        ("cqg", "Free AMP demo - no credentials needed (default)"),
        ("rithmic", "Rithmic broker account - requires credentials"),
        ("dxfeed", "Paid DXFeed account - configure in Deepchart UI"),
    ])

    builders = {"cqg": build_cqg, "rithmic": build_rithmic, "dxfeed": build_dxfeed}
    base = builders[mode](cache)

    config = finalize(base)

    print("\n" + "=" * 60)
    print("  Configuration Summary")
    print("=" * 60)
    print(f"  Data Source: {config['data_source']}")
    if mode == "rithmic":
        r = config["rithmic"]
        print(f"    User:     {r['user']}")
        print(f"    System:   {r['system']}")
        print(f"    URL:      {r['url'] or '(none)'}")
    elif mode == "cqg":
        print(f"    User:     {DEFAULTS['cqg']['user']}")
        print(f"    Password: {DEFAULTS['cqg']['password']}")

    ans = input("\nSave this configuration? (Y/n): ").strip().lower()
    if ans == "n":
        print("Cancelled.")
        return

    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"\nSaved to {CONFIG_FILE}")
    print("Run deepchart_launcher.exe or start_servers.ps1 to start.")


if __name__ == "__main__":
    main()
