#!/usr/bin/env python3
"""
admin_gui.py — Admin GUI for license management.
Combines gen_license, license_manager, license_server in one window.
"""
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from tkinter import *
from tkinter import ttk, messagebox, scrolledtext

sys.path.insert(0, str(Path(__file__).parent))
from gen_license import (
    create_license, list_licenses, deactivate,
    reactivate, update_note, delete_license, sign_lic_file, _generate,
)

try:
    from license_manager import LicenseManager, LicenseError
    HAS_LM = True
except ImportError:
    HAS_LM = False

BG = "#1e1e2e"
FG = "#cdd6f4"
ACCENT = "#89b4fa"
ERROR = "#f38ba8"
SUCCESS = "#a6e3a1"
WARN = "#f9e2af"
SURFACE = "#313244"
TEXT_SEC = "#a6adc8"

root = Tk()
root.title("Deepchart License Admin")
root.configure(bg=BG)
root.minsize(800, 560)

style = ttk.Style()
style.theme_use("clam")
style.configure("TNotebook", background=BG, borderwidth=0)
style.configure("TNotebook.Tab", background=SURFACE, foreground=FG, padding=[12, 4])
style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", BG)])
style.configure("TFrame", background=BG)
style.configure("Treeview", background=SURFACE, foreground=FG, fieldbackground=SURFACE, rowheight=26)
style.map("Treeview", background=[("selected", ACCENT)])
style.configure("Treeview.Heading", background=SURFACE, foreground=FG, relief="flat")
style.configure("TLabel", background=BG, foreground=FG)
style.configure("TButton", background=SURFACE, foreground=FG, padding=[10, 4])
style.map("TButton", background=[("active", ACCENT)], foreground=[("active", BG)])

notebook = ttk.Notebook(root)
notebook.pack(fill=BOTH, expand=True, padx=8, pady=8)

# ── Helper widgets ────────────────────────────────────────────────────

def _make_entry(parent, label, default="", width=40, show=None):
    f = Frame(parent, bg=BG)
    f.pack(fill=X, pady=3)
    Label(f, text=label, width=28, anchor=W, bg=BG, fg=TEXT_SEC).pack(side=LEFT)
    e = Entry(f, bg=SURFACE, fg=FG, insertbackground=FG, relief=FLAT, bd=6,
              width=width, show=show, font=("Consolas", 10))
    e.pack(side=LEFT, padx=4)
    e.insert(0, default)
    return e

def _log(tab, msg, color=FG):
    tab.log_area.insert(END, msg + "\n")
    tab.log_area.see(END)
    tab.log_area.tag_config("ok", foreground=SUCCESS)
    tab.log_area.tag_config("err", foreground=ERROR)
    tab.log_area.tag_config("warn", foreground=WARN)
    tab.log_area.tag_config("info", foreground=TEXT_SEC)

# ── Tab 1: Generate ───────────────────────────────────────────────────

class GenTab(Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        f = Frame(self, bg=BG)
        f.pack(pady=20)
        Label(f, text="Generate License", font=("Segoe UI", 16, "bold"),
              bg=BG, fg=FG).pack()
        Label(f, text="Create a new license key and optional .lic file",
              font=("Segoe UI", 10), bg=BG, fg=TEXT_SEC).pack()

        pf = Frame(self, bg=BG)
        pf.pack(pady=16)
        self.days_e = _make_entry(pf, "Duration (days)", "30")
        self.hwid_e = _make_entry(pf, "HWID (leave empty to skip)", "")
        self.note_e = _make_entry(pf, "Customer name / notes", "", 50)

        bf = Frame(self, bg=BG)
        bf.pack(pady=8)
        Button(bf, text="Generate Key Only", bg=SURFACE, fg=FG,
               relief=FLAT, padx=16, pady=4, cursor="hand2",
               command=self._gen_key).pack(side=LEFT, padx=6)
        Button(bf, text="Generate Key + .lic File", bg=ACCENT, fg=BG,
               relief=FLAT, padx=16, pady=4, cursor="hand2",
               font=("Segoe UI", 10, "bold"), command=self._gen_lic).pack(side=LEFT, padx=6)

        self.log_area = scrolledtext.ScrolledText(self, bg=BG, fg=FG,
                       insertbackground=FG, relief=FLAT, height=7, font=("Consolas", 9))
        self.log_area.pack(fill=BOTH, padx=16, pady=8)

    def _gen_key(self):
        days = int(self.days_e.get().strip() or 30)
        hwid = self.hwid_e.get().strip()
        note = self.note_e.get().strip() or "Unnamed"
        key = create_license(days, note, hwid)
        _log(self, f"[OK] Key: {key}  |  Expires: +{days}d  |  {note}", "ok")

    def _gen_lic(self):
        days = int(self.days_e.get().strip() or 30)
        hwid = self.hwid_e.get().strip()
        note = self.note_e.get().strip() or "Unnamed"
        key = create_license(days, note, hwid)
        p = sign_lic_file(key, days, note, hwid)
        _log(self, f"[OK] Key: {key}", "ok")
        _log(self, f"[OK] .lic saved: {p}", "ok")
        _log(self, f"     Send {p.name} to customer", "info")

# ── Tab 2: License List ───────────────────────────────────────────────

class ListTab(Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)

        top = Frame(self, bg=BG)
        top.pack(fill=X, pady=8)
        Label(top, text="License Database", font=("Segoe UI", 14, "bold"),
              bg=BG, fg=FG).pack(side=LEFT, padx=16)
        Button(top, text="↻ Refresh", bg=SURFACE, fg=FG,
               relief=FLAT, padx=12, cursor="hand2",
               command=self._refresh).pack(side=RIGHT, padx=16)

        cols = ("key", "hwid", "active", "expires", "last_checkin", "note")
        self.tree = ttk.Treeview(self, columns=cols, show="headings",
                                  select="browse", height=16)
        self.tree.heading("key", text="License Key")
        self.tree.heading("hwid", text="HWID")
        self.tree.heading("active", text="Active")
        self.tree.heading("expires", text="Expires")
        self.tree.heading("last_checkin", text="Last Checkin")
        self.tree.heading("note", text="Note")
        self.tree.column("key", width=180)
        self.tree.column("hwid", width=130)
        self.tree.column("active", width=60)
        self.tree.column("expires", width=170)
        self.tree.column("last_checkin", width=170)
        self.tree.column("note", width=200)
        self.tree.pack(fill=BOTH, expand=True, padx=16, pady=4)

        bf = Frame(self, bg=BG)
        bf.pack(fill=X, padx=16, pady=6)
        Button(bf, text="Deactivate Selected", bg="#f38ba8", fg=BG,
               relief=FLAT, padx=12, cursor="hand2",
               command=self._deactivate).pack(side=LEFT, padx=4)
        Button(bf, text="Reactivate Selected", bg=SUCCESS, fg=BG,
               relief=FLAT, padx=12, cursor="hand2",
               command=self._reactivate).pack(side=LEFT, padx=4)
        Button(bf, text="Delete Selected", bg=ERROR, fg=BG,
               relief=FLAT, padx=12, cursor="hand2",
               command=self._delete).pack(side=LEFT, padx=4)
        Button(bf, text="Edit Note", bg=WARN, fg=BG,
               relief=FLAT, padx=12, cursor="hand2",
               command=self._edit_note).pack(side=LEFT, padx=4)

        self.log_area = scrolledtext.ScrolledText(self, bg=BG, fg=FG,
                       insertbackground=FG, relief=FLAT, height=4, font=("Consolas", 9))
        self.log_area.pack(fill=X, padx=16, pady=4)
        self._refresh()

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        import sqlite3
        db = Path(__file__).parent / "licenses.db"
        if not db.exists():
            _log(self, "[!] No licenses.db found", "warn")
            return
        conn = sqlite3.connect(str(db))
        rows = conn.execute(
            "SELECT license_key, hwid, created_at, expires_at, active, last_checkin, note "
            "FROM licenses ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        for r in rows:
            vals = (r[0], (r[1] or "-")[:14], "YES" if r[4] else "NO",
                    r[3][:19], (r[5] or "-")[:19], r[6] or "")
            self.tree.insert("", END, values=vals)
        _log(self, f"[OK] Loaded {len(rows)} licenses", "ok")

    def _selected_key(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[0]

    def _deactivate(self):
        key = self._selected_key()
        if key:
            deactivate(key)
            self._refresh()

    def _reactivate(self):
        key = self._selected_key()
        if key:
            reactivate(key)
            self._refresh()

    def _delete(self):
        key = self._selected_key()
        if key:
            delete_license(key)
            self._refresh()

    def _edit_note(self):
        key = self._selected_key()
        if not key:
            return
        win = Toplevel(root)
        win.title("Edit Note")
        win.configure(bg=BG)
        win.geometry("400x150")
        Label(win, text=f"License: {key}", bg=BG, fg=TEXT_SEC).pack(pady=8)
        e = Entry(win, bg=SURFACE, fg=FG, insertbackground=FG, relief=FLAT, bd=6, width=50, font=("Consolas", 10))
        e.pack(pady=8)
        def save():
            update_note(key, e.get().strip())
            win.destroy()
            self._refresh()
        Button(win, text="Save", bg=ACCENT, fg=BG, relief=FLAT, padx=16, command=save).pack()

# ── Tab 3: Server ──────────────────────────────────────────────────────

class ServerTab(Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        f = Frame(self, bg=BG)
        f.pack(pady=20)
        Label(f, text="License Server", font=("Segoe UI", 16, "bold"),
              bg=BG, fg=FG).pack()
        Label(f, text="Run the server for online phone-home validation (optional)",
              font=("Segoe UI", 10), bg=BG, fg=TEXT_SEC).pack()
        self.running = False
        self.process = None
        Button(self, text="▶ Start Server", bg=SUCCESS, fg=BG,
               relief=FLAT, padx=20, pady=6, cursor="hand2",
               font=("Segoe UI", 11, "bold"), command=self._toggle).pack(pady=16)
        self.status_lbl = Label(self, text="Status: Stopped", bg=BG, fg=ERROR,
                                font=("Segoe UI", 11))
        self.status_lbl.pack()
        self.log_area = scrolledtext.ScrolledText(self, bg=BG, fg=FG,
                       insertbackground=FG, relief=FLAT, height=18, font=("Consolas", 9))
        self.log_area.pack(fill=BOTH, expand=True, padx=16, pady=8)

    def _toggle(self):
        if self.running:
            if self.process:
                self.process.terminate()
            self.running = False
            self.status_lbl.config(text="Status: Stopped", fg=ERROR)
            return
        server_path = Path(__file__).parent / "license_server.py"
        if not server_path.exists():
            _log(self, "[!] license_server.py not found", "err")
            return
        self.running = True
        self.status_lbl.config(text="Status: Starting...", fg=WARN)
        def run():
            try:
                self.process = subprocess.Popen(
                    [sys.executable, str(server_path)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                self.after(0, lambda: self.status_lbl.config(text="Status: Running", fg=SUCCESS))
                for line in self.process.stdout:
                    self.after(0, lambda l=line: _log(self, l.strip(), "info"))
            except Exception as e:
                self.after(0, lambda: _log(self, f"[!] {e}", "err"))
            self.after(0, lambda: self.status_lbl.config(text="Status: Stopped", fg=ERROR))
            self.running = False
        threading.Thread(target=run, daemon=True).start()

# ── Tab 4: Local License ──────────────────────────────────────────────

class LocalTab(Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        f = Frame(self, bg=BG)
        f.pack(pady=30)
        Label(f, text="Local License Status", font=("Segoe UI", 16, "bold"),
              bg=BG, fg=FG).pack()
        self.info = Label(f, text="", bg=BG, fg=TEXT_SEC,
                          font=("Segoe UI", 12), justify=LEFT)
        self.info.pack(pady=16)
        self.btn = Button(self, text="↻ Check", bg=ACCENT, fg=BG,
                          relief=FLAT, padx=20, pady=4, cursor="hand2",
                          font=("Segoe UI", 10, "bold"), command=self._check)
        self.btn.pack()
        self.lic_btn = Button(self, text="📂 Activate from .lic File",
                              bg=SURFACE, fg=FG, relief=FLAT, padx=16,
                              pady=4, cursor="hand2", command=self._activate_lic)
        self.lic_btn.pack(pady=8)
        self._check()

    def _check(self):
        if not HAS_LM:
            self.info.config(text="license_manager module not found\nRun from the Deepchart folder", fg=ERROR)
            return
        lm = LicenseManager()
        hwid = lm.get_hwid_display()
        valid, days, msg = lm.validate()
        color = SUCCESS if valid else ERROR
        text = f"HWID: {hwid}\n\nStatus: {msg}"
        if valid:
            text += f"\nDays remaining: {days}"
        self.info.config(text=text, fg=color)

    def _activate_lic(self):
        if not HAS_LM:
            return
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Select .lic file",
                  filetypes=[("License files", "*.lic")],
                  initialdir=str(Path(__file__).parent))
        if not path:
            return
        lm = LicenseManager()
        try:
            result = lm.activate_from_file(path)
            Path(path).unlink(missing_ok=True)
            messagebox.showinfo("Success", f"Activated!\nExpires: {result.get('expires_at', '')}")
            self._check()
        except LicenseError as e:
            messagebox.showerror("Failed", str(e))

# ── Build tabs ────────────────────────────────────────────────────────

notebook.add(GenTab(notebook), text="  Generate  ")
notebook.add(ListTab(notebook), text="  License List  ")
notebook.add(ServerTab(notebook), text="  Server  ")
notebook.add(LocalTab(notebook), text="  Local License  ")

root.mainloop()
