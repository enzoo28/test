"""
license_login.py — Login window for customers to enter their license key.
Runs before Deepchart launches. Exits with code 0 on valid activation.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from license_manager import LicenseManager, LicenseError

CONFIG_FILE = Path(__file__).parent / "bridge_config.json"

def _get_server_url() -> str:
    try:
        import json
        cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return (cfg.get("license") or {}).get("server_url", "")
    except Exception:
        return os.environ.get("LICENSE_SERVER_URL", "")


class LicenseLoginWindow:
    def __init__(self):
        self.server_url = _get_server_url()
        self.lm = LicenseManager(self.server_url) if self.server_url else None
        self.result = False

        self.root = tk.Tk()
        self.root.title("Deepchart — License Activation")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        w, h = 480, 340
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        self._build_ui()

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=30)
        frame.pack(fill="both", expand=True)

        title = tk.Label(frame, text="Deepchart", font=("Segoe UI", 22, "bold"),
                         fg="#cdd6f4", bg="#1e1e2e")
        title.pack(pady=(0, 4))

        subtitle = tk.Label(frame, text="Enter your license key to activate",
                            font=("Segoe UI", 11), fg="#a6adc8", bg="#1e1e2e")
        subtitle.pack(pady=(0, 20))

        hwid_frame = tk.Frame(frame, bg="#1e1e2e")
        hwid_frame.pack(fill="x", pady=(0, 16))

        hwid_label = tk.Label(hwid_frame, text="Hardware ID:",
                              font=("Segoe UI", 9), fg="#a6adc8", bg="#1e1e2e")
        hwid_label.pack(side="left")

        hwid_val = self.lm.get_hwid_display() if self.lm else "N/A"
        hwid_display = tk.Label(hwid_frame, text=hwid_val,
                                font=("Consolas", 9), fg="#f5c2e7", bg="#1e1e2e")
        hwid_display.pack(side="right")

        key_label = tk.Label(frame, text="License Key", font=("Segoe UI", 10),
                             fg="#cdd6f4", bg="#1e1e2e", anchor="w")
        key_label.pack(fill="x")

        self.key_var = tk.StringVar()
        self.key_entry = tk.Entry(frame, textvariable=self.key_var,
                                  font=("Consolas", 14), bg="#313244", fg="#cdd6f4",
                                  insertbackground="#cdd6f4", relief="flat", bd=8)
        self.key_entry.pack(fill="x", pady=(4, 20))
        self.key_entry.focus()

        self.status_var = tk.StringVar()
        self.status_label = tk.Label(frame, textvariable=self.status_var,
                                     font=("Segoe UI", 10), fg="#a6adc8", bg="#1e1e2e")
        self.status_label.pack(pady=(0, 12))

        btn_frame = tk.Frame(frame, bg="#1e1e2e")
        btn_frame.pack(fill="x")

        self.activate_btn = tk.Button(btn_frame, text="Activate",
                                      font=("Segoe UI", 11, "bold"),
                                      bg="#89b4fa", fg="#1e1e2e", relief="flat",
                                      activebackground="#74c7ec", activeforeground="#1e1e2e",
                                      padx=20, pady=6, cursor="hand2",
                                      command=self._activate)
        self.activate_btn.pack(side="right")

        quit_btn = tk.Button(btn_frame, text="Quit",
                             font=("Segoe UI", 11), bg="#45475a", fg="#cdd6f4",
                             relief="flat", padx=20, pady=6, cursor="hand2",
                             command=self._quit)
        quit_btn.pack(side="right", padx=(0, 8))

        self.root.bind("<Return>", lambda e: self._activate())
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    def _activate(self):
        key = self.key_var.get().strip()
        if not key:
            self.status_var.set("Enter a license key")
            return
        if not self.lm:
            self.status_var.set("No license server configured")
            return

        self.activate_btn.config(state="disabled")
        self.status_var.set("Contacting server...")
        self.root.update()

        try:
            result = self.lm.activate(key)
            if result.get("success"):
                self.status_var.set("Activated! Launching...")
                self.root.update()
                self.root.after(500, self._success)
            else:
                self.status_var.set(f"Failed: {result.get('message', 'Unknown error')}")
                self.activate_btn.config(state="normal")
        except LicenseError as e:
            self.status_var.set(str(e))
            self.activate_btn.config(state="normal")
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            self.activate_btn.config(state="normal")

    def _success(self):
        self.result = True
        self.root.destroy()

    def _quit(self):
        self.root.destroy()

    def run(self) -> bool:
        self.root.mainloop()
        return self.result


def main():
    if _get_server_url():
        app = LicenseLoginWindow()
        success = app.run()
        sys.exit(0 if success else 1)
    else:
        print("[LICENSE] No license server configured — skipping login")
        sys.exit(0)


if __name__ == "__main__":
    main()
