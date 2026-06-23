#!/usr/bin/env python3
"""
Rithmic Data Bridge — connects to Rithmic Protocol API and streams tick data.
Runs as a standalone process (requires Python 3.10+ with async_rithmic).

Usage:
    set RITHMIC_USER=your_username
    set RITHMIC_PASSWORD=your_password
    python rithmic_bridge.py
"""

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------
RITHMIC_USER     = os.environ.get("RITHMIC_USER", "")
RITHMIC_PASSWORD = os.environ.get("RITHMIC_PASSWORD", "")
RITHMIC_SYSTEM   = os.environ.get("RITHMIC_SYSTEM", "Rithmic Paper Chicago")
RITHMIC_APP_NAME = os.environ.get("RITHMIC_APP_NAME", "DeepChartBridge")
RITHMIC_APP_VER  = os.environ.get("RITHMIC_APP_VER", "1.0")
RITHMIC_URL      = os.environ.get("RITHMIC_URL", "rituz00100.rithmic.com:443")

WS_HOST          = os.environ.get("RITHMIC_WS_HOST", "127.0.0.1")
WS_PORT          = int(os.environ.get("RITHMIC_WS_PORT", "8765"))
LOG_DIR          = os.environ.get("RITHMIC_LOG_DIR", "logs")

DEFAULT_SYMBOLS = [
    ("ES", "CME"), ("NQ", "CME"), ("YM", "CBOT"), ("RTY", "CME"),
    ("CL", "NYMEX"), ("GC", "COMEX"), ("SI", "COMEX"), ("HG", "COMEX"),
    ("ZB", "CBOT"), ("ZN", "CBOT"), ("ZF", "CBOT"), ("ZT", "CBOT"),
    ("6E", "CME"), ("6J", "CME"), ("6B", "CME"), ("6A", "CME"),
    ("EUR/USD", "IDEALPRO"), ("GBP/USD", "IDEALPRO"), ("USD/JPY", "IDEALPRO"),
]

SUBSCRIBE_SYMBOLS = os.environ.get("RITHMIC_SYMBOLS", "")
if SUBSCRIBE_SYMBOLS:
    SUBSCRIBE_SYMBOLS = [s.strip().split(":") for s in SUBSCRIBE_SYMBOLS.split(",") if ":" in s]
else:
    SUBSCRIBE_SYMBOLS = DEFAULT_SYMBOLS

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"rithmic_bridge_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("rithmic")

# ---------------------------------------------------------------------------
# WebSocket server for streaming ticks to connected clients
# ---------------------------------------------------------------------------
class TickBroadcaster:
    def __init__(self):
        self.clients = set()

    async def broadcast(self, data: dict):
        msg = json.dumps(data, default=str)
        dead = set()
        for ws in self.clients:
            try:
                await ws.send(msg)
            except Exception:
                dead.add(ws)
        self.clients -= dead

    async def handler(self, websocket):
        self.clients.add(websocket)
        try:
            async for _ in websocket:
                pass
        except Exception:
            pass
        finally:
            self.clients.discard(websocket)

# ---------------------------------------------------------------------------
# Rithmic client wrapper
# ---------------------------------------------------------------------------
class RithmicDataBridge:
    def __init__(self, broadcaster: TickBroadcaster):
        self.broadcaster = broadcaster
        self.client = None
        self.running = True
        self.tick_queue = asyncio.Queue()

    async def start(self):
        import ssl
        from async_rithmic import RithmicClient

        if not RITHMIC_USER or not RITHMIC_PASSWORD:
            log.error("RITHMIC_USER and RITHMIC_PASSWORD must be set")
            return

        self.client = RithmicClient(
            user=RITHMIC_USER,
            password=RITHMIC_PASSWORD,
            system_name=RITHMIC_SYSTEM,
            app_name=RITHMIC_APP_NAME,
            app_version=RITHMIC_APP_VER,
            url=RITHMIC_URL,
        )

        # Override SSL to be permissive (hosts file redirects to localhost)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.client.ssl_context = ctx

        self.client.on_connected += lambda plant: log.info(f"[{plant}] Connected")
        self.client.on_disconnected += lambda plant: log.warning(f"[{plant}] Disconnected")
        self.client.on_tick += self._on_tick

        try:
            log.info(f"Connecting to Rithmic: {RITHMIC_URL} (user={RITHMIC_USER}, system={RITHMIC_SYSTEM})")
            await self.client.connect()
            log.info("Connected to Rithmic")

            for symbol, exchange in SUBSCRIBE_SYMBOLS:
                try:
                    await self.client.subscribe_to_market_data(symbol, exchange, data_type=3)
                    log.info(f"Subscribed to {symbol}/{exchange}")
                except Exception as e:
                    log.warning(f"Failed to subscribe to {symbol}/{exchange}: {e}")

            while self.running:
                await asyncio.sleep(1)

        except ssl.SSLCertVerificationError as e:
            log.error(f"SSL error: {e}")
        except Exception as e:
            log.exception(f"Connection error: {e}")
        finally:
            await self._cleanup()

    async def _cleanup(self):
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass

    def _on_tick(self, data: dict):
        data["_source"] = "rithmic"
        data["_received_at"] = datetime.now(timezone.utc).isoformat()
        log.debug(f"Tick: {json.dumps(data, default=str)}")
        self.tick_queue.put_nowait(data)

    async def process_tick_queue(self):
        while self.running:
            data = await self.tick_queue.get()
            await self.broadcaster.broadcast(data)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    broadcaster = TickBroadcaster()
    bridge = RithmicDataBridge(broadcaster)

    import websockets
    ws_server = await websockets.serve(
        broadcaster.handler, WS_HOST, WS_PORT,
        ping_interval=30, ping_timeout=10,
    )
    log.info(f"Rithmic Bridge target URL: {RITHMIC_URL}")
    log.info(f"System: {RITHMIC_SYSTEM}  Symbols: {len(SUBSCRIBE_SYMBOLS)}")
    log.info(f"Ticker data streamed to connected WebSocket clients on ws://{WS_HOST}:{WS_PORT}")

    shutdown_event = asyncio.Event()

    async def shutdown():
        bridge.running = False
        shutdown_event.set()
        ws_server.close()
        await ws_server.wait_closed()

    tasks = [
        asyncio.create_task(bridge.start()),
        asyncio.create_task(bridge.process_tick_queue()),
    ]

    try:
        await asyncio.gather(*tasks)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown")
