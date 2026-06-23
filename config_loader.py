"""
config_loader.py — Reads bridge_config.json and applies it as environment variables.
Called before any other module reads config.py, so the env vars are already set.

Config file is optional. When absent, all settings come from env vars (backwards compat).
"""

import os
import json
import sys

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_config.json")

def load():
    if not os.path.exists(CONFIG_FILE):
        return False

    with open(CONFIG_FILE, "r") as f:
        cfg = json.load(f)

    source = cfg.get("data_source", "cqg").lower()

    # ── Data Source ──
    if source == "rithmic":
        os.environ.setdefault("RITHMIC_MODE", "1")
        r = cfg.get("rithmic", {})
        for key, env in [("user", "RITHMIC_USER"), ("password", "RITHMIC_PASSWORD"),
                         ("system", "RITHMIC_SYSTEM"), ("url", "RITHMIC_URL")]:
            if r.get(key):
                os.environ[env] = r[key]
        os.environ.setdefault("RITHMIC_SYSTEM", "Rithmic Paper Trading Chicago")
        os.environ.setdefault("RITHMIC_URL", "rituz00100.rithmic.com:443")
    elif source == "cqg":
        os.environ.pop("RITHMIC_MODE", None)
        c = cfg.get("cqg", {})
        if c.get("user"):     os.environ["CQG_DEMO_USER"] = c["user"]
        if c.get("password"): os.environ["CQG_DEMO_PASS"] = c["password"]

    # ── License ──
    lic = cfg.get("license", {})
    if lic.get("server_url"):
        os.environ["LICENSE_SERVER_URL"] = lic["server_url"]

    # ── Bridge overrides ──
    b = cfg.get("bridge", {})
    if b.get("port"): os.environ["BRIDGE_PROXY_PORT"] = str(b["port"])
    if b.get("bind_host"): os.environ["BRIDGE_PROXY_BIND_HOST"] = b["bind_host"]

    # ── CQG server override (for advanced users) ──
    cqg_override = cfg.get("cqg_server_override", {})
    if cqg_override.get("host"): os.environ["REAL_CQG_HOST"] = cqg_override["host"]
    if cqg_override.get("port"): os.environ["REAL_CQG_PORT"] = str(cqg_override["port"])
    if cqg_override.get("sni"):  os.environ["SNI_HOST"] = cqg_override["sni"]

    return True


if __name__ == "__main__":
    loaded = load()
    if loaded:
        print(f"[CONFIG] Loaded {CONFIG_FILE}")
        for k, v in sorted(os.environ.items()):
            if any(x in k.lower() for x in ("rithmic", "cqg", "license", "bridge_proxy", "real_cqg", "sni")):
                print(f"  {k}={v}")
    else:
        print(f"[CONFIG] No {CONFIG_FILE} found — using env vars")
