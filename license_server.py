"""
license_server.py — License validation server (run on YOUR server).
FastAPI + SQLite. One-file deployment.

Usage:
  pip install fastapi uvicorn
  python license_server.py
  # Runs on http://0.0.0.0:9876
"""

import sqlite3
import secrets
import hashlib
import hmac
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("Missing dependencies. Run: pip install fastapi uvicorn")
    raise

DB_PATH = Path(__file__).parent / "licenses.db"
SECRET_KEY = "change-this-to-a-random-secret"  # CHANGE ME


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    yield


app = FastAPI(title="License Server", version="1.0", lifespan=lifespan)


def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            license_key TEXT PRIMARY KEY,
            hwid TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            last_checkin TEXT,
            note TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


def _hash_license_key(raw: str) -> str:
    return hashlib.sha256((raw + SECRET_KEY).encode()).hexdigest()[:16].upper()


def _format_key(raw: str) -> str:
    """XXXXX-XXXXX-XXXXX-XXXXX format."""
    return "-".join(raw[i:i+5] for i in range(0, len(raw), 5))


def generate_license_key() -> str:
    raw = secrets.token_hex(10).upper()
    return _format_key(raw)


class ValidateRequest(BaseModel):
    license_key: str
    hwid: str


class ValidateResponse(BaseModel):
    valid: bool
    expires_at: str = ""
    days_remaining: int = 0
    message: str = ""


class RegisterRequest(BaseModel):
    license_key: str
    hwid: str


class RegisterResponse(BaseModel):
    success: bool
    message: str = ""
    expires_at: str = ""


@app.get("/")
def root():
    return {"service": "Deepchart License Server", "status": "running"}


@app.post("/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest):
    key = req.license_key.strip().upper()
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        "SELECT hwid, expires_at, active FROM licenses WHERE license_key = ?", (key,)
    ).fetchone()
    conn.close()

    if not row:
        return ValidateResponse(valid=False, message="License key not found")

    db_hwid, expires_at, active = row
    if not active:
        return ValidateResponse(valid=False, message="License deactivated")

    expires = datetime.fromisoformat(expires_at)
    if expires < datetime.now(timezone.utc):
        return ValidateResponse(valid=False, message="License expired")

    if db_hwid and db_hwid != req.hwid:
        return ValidateResponse(valid=False, message="License bound to another machine")

    # Update last checkin
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "UPDATE licenses SET last_checkin = ? WHERE license_key = ?",
        (datetime.now(timezone.utc).isoformat(), key),
    )
    conn.commit()
    conn.close()

    remaining = (expires - datetime.now(timezone.utc)).days
    return ValidateResponse(
        valid=True, expires_at=expires_at, days_remaining=remaining
    )


@app.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest):
    key = req.license_key.strip().upper()
    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute(
        "SELECT hwid, expires_at, active FROM licenses WHERE license_key = ?", (key,)
    ).fetchone()

    if not row:
        conn.close()
        return RegisterResponse(success=False, message="License key not found")

    db_hwid, expires_at, active = row
    if not active:
        conn.close()
        return RegisterResponse(success=False, message="License deactivated")

    expires = datetime.fromisoformat(expires_at)
    if expires < datetime.now(timezone.utc):
        conn.close()
        return RegisterResponse(success=False, message="License expired")

    if db_hwid and db_hwid != req.hwid:
        conn.close()
        return RegisterResponse(success=False, message="Already bound to another machine")

    conn.execute(
        "UPDATE licenses SET hwid = ?, last_checkin = ? WHERE license_key = ?",
        (req.hwid, datetime.now(timezone.utc).isoformat(), key),
    )
    conn.commit()
    conn.close()
    return RegisterResponse(success=True, message="Activated", expires_at=expires_at)


if __name__ == "__main__":
    print(f"[*] License server starting on 0.0.0.0:9876")
    print(f"[*] Database: {DB_PATH}")
    print(f"[*] API docs at http://localhost:9876/docs")
    uvicorn.run(app, host="0.0.0.0", port=9876)
