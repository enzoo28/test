"""
rithmic_translator.py — CQG ↔ Rithmic Protocol Translation Engine.

Terminates CQG WebSocket protocol from Deepchart locally and
backs it with Rithmic Protocol API connections via async_rithmic.
"""

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger("rithmic-xlate")

# CQG protobuf imports (loaded once)
_PROTOBUF_AVAILABLE = False
_ClientMsg = _ServerMsg = _InformationReport = None
_ContractMetadata = _SymbolResolutionReport = None
_MarketDataSubscriptionStatus = _RealTimeMarketData = _Quote = None
_LogonResult = None
_TimeAndSalesReport = _TimeBarReport = None

def _load_protobufs(cqg_test_path: str):
    global _PROTOBUF_AVAILABLE, _ClientMsg, _ServerMsg, _InformationReport
    global _ContractMetadata, _SymbolResolutionReport
    global _MarketDataSubscriptionStatus, _RealTimeMarketData, _Quote
    global _LogonResult
    global _TimeAndSalesReport, _TimeBarReport
    import sys, os
    sys.path.insert(0, os.path.abspath(cqg_test_path))
    try:
        from WebAPI.webapi_2_pb2 import (
            ClientMsg as _C, ServerMsg as _S, InformationReport as _IR
        )
        from WebAPI.metadata_2_pb2 import (
            ContractMetadata as _CM, SymbolResolutionReport as _SRR
        )
        from WebAPI.market_data_2_pb2 import (
            MarketDataSubscriptionStatus as _MDS,
            RealTimeMarketData as _RTMD, Quote as _Q
        )
        from WebAPI.user_session_2_pb2 import LogonResult as _LR
        from WebAPI.historical_2_pb2 import (
            TimeAndSalesReport as _TSR, TimeBarReport as _TBR
        )
        _ClientMsg, _ServerMsg, _InformationReport = _C, _S, _IR
        _ContractMetadata, _SymbolResolutionReport = _CM, _SRR
        _MarketDataSubscriptionStatus, _RealTimeMarketData, _Quote = _MDS, _RTMD, _Q
        _LogonResult = _LR
        _TimeAndSalesReport, _TimeBarReport = _TSR, _TBR
        _PROTOBUF_AVAILABLE = True
        log.info("[PB] CQG protobufs loaded")
    except Exception as e:
        log.error(f"[PB] Failed to load CQG protobufs: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# Contract ID Registry — maps CQG contract_id ↔ Rithmic (symbol, exchange)
# ═══════════════════════════════════════════════════════════════════════════════

class ContractRegistry:
    def __init__(self):
        self._next_id = 1
        self._sym_to_id = {}   # (symbol, exchange) → contract_id
        self._id_to_sym = {}   # contract_id → (symbol, exchange)
        self._id_to_meta = {}  # contract_id → metadata dict

    def resolve(self, symbol: str, exchange: str, meta: dict = None) -> int:
        key = (symbol.upper(), exchange.upper())
        if key in self._sym_to_id:
            return self._sym_to_id[key]
        cid = self._next_id
        self._next_id += 1
        self._sym_to_id[key] = cid
        self._id_to_sym[cid] = key
        if meta:
            self._id_to_meta[cid] = meta
        return cid

    def get_symbol(self, contract_id: int):
        return self._id_to_sym.get(contract_id)

    def get_meta(self, contract_id: int):
        return self._id_to_meta.get(contract_id, {})


# ═══════════════════════════════════════════════════════════════════════════════
# RithmicTranslator
# ═══════════════════════════════════════════════════════════════════════════════

class RithmicTranslator:
    def __init__(self, cqg_test_path: str):
        _load_protobufs(cqg_test_path)
        self.registry = ContractRegistry()
        self.rithmic = None  # RithmicClient instance
        self.connected = False
        self._tick_task = None
        self._response_queue = asyncio.Queue()

        # Config (env overrides)
        import os
        self.rithmic_user = os.environ.get("RITHMIC_USER", "")
        self.rithmic_pass = os.environ.get("RITHMIC_PASSWORD", "")
        self.rithmic_system = os.environ.get("RITHMIC_SYSTEM", "Rithmic Paper Trading Chicago")
        self.rithmic_url = os.environ.get("RITHMIC_URL", "rituz00100.rithmic.com:443")
        self.app_name = os.environ.get("RITHMIC_APP_NAME", "DeepChartBridge")
        self.app_ver = os.environ.get("RITHMIC_APP_VER", "1.0")

    def set_credentials(self, user: str, password: str, system: str = None, url: str = None):
        """Override credentials from a CQG logon message."""
        if user:
            self.rithmic_user = user
        if password:
            self.rithmic_pass = password
        if system:
            self.rithmic_system = system
        if url:
            self.rithmic_url = url
        log.info(f"[RTHM] Credentials set: user={self.rithmic_user} system={self.rithmic_system} url={self.rithmic_url}")

    async def connect_rithmic(self):
        """Connect to Rithmic Protocol API."""
        import ssl
        from async_rithmic import RithmicClient

        if not self.rithmic_user or not self.rithmic_pass:
            log.error("[RTHM] RITHMIC_USER and RITHMIC_PASSWORD not set")
            return False

        self.rithmic = RithmicClient(
            user=self.rithmic_user,
            password=self.rithmic_pass,
            system_name=self.rithmic_system,
            app_name=self.app_name,
            app_version=self.app_ver,
            url=self.rithmic_url,
        )

        # Override SSL to be permissive (hosts file redirects to localhost)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.rithmic.ssl_context = ctx

        self.rithmic.on_connected += lambda p: log.info(f"[RTHM] {p} connected")
        self.rithmic.on_disconnected += lambda p: log.warning(f"[RTHM] {p} disconnected")
        self.rithmic.on_tick += self._on_tick

        # Verbose debug: dump all plants after connection
        async def _on_connect_debug(plant_name):
            plant = self.rithmic.plants.get(plant_name)
            if plant:
                log.debug(f"[RTHM] {plant_name} plant: connected={plant.is_connected}")
        self.rithmic.on_connected += _on_connect_debug

        try:
            log.info(f"[RTHM] Connecting to {self.rithmic_url} (user={self.rithmic_user}, system={self.rithmic_system})")
            await self.rithmic.connect()
            self.connected = True
            log.info("[RTHM] Connected to Rithmic")
            return True
        except ssl.SSLCertVerificationError as e:
            log.error(f"[RTHM] SSL cert verification failed: {e}")
            log.error("[RTHM] Try setting a permissive SSL context or check hosts file")
            return False
        except Exception as e:
            log.error(f"[RTHM] Connection failed: {e}")
            log.error("[RTHM] Check RITHMIC_URL, RITHMIC_SYSTEM, and credentials")
            return False

    async def disconnect_rithmic(self):
        if self.rithmic:
            try:
                await self.rithmic.disconnect()
            except Exception:
                pass
        self.connected = False

    def _on_tick(self, data: dict):
        """Called by async_rithmic when a tick arrives. Enqueue for CQG translation."""
        self._response_queue.put_nowait(("tick", data))

    async def process_tick(self, data: dict):
        """Translate a Rithmic tick to CQG ServerMsg with RealTimeMarketData."""
        if not _PROTOBUF_AVAILABLE:
            return None

        symbol = data.get("symbol", "")
        exchange = data.get("exchange", "")
        contract_id = self.registry.resolve(symbol, exchange)

        rtd = _RealTimeMarketData()
        rtd.contract_id = contract_id
        rtd.is_snapshot = data.get("is_snapshot", False)

        data_type = data.get("data_type", 1)
        quote = rtd.quotes.add()

        if data_type == 1:  # LAST_TRADE
            quote.type = 0  # TYPE_TRADE
            quote.scaled_price = int(data.get("price", 0) * 10000)
            quote.scaled_volume = int(data.get("volume", 0))
            ssboe = data.get("ssboe", 0)
            usecs = data.get("usecs", 0)
            quote.quote_utc_time = ssboe * 1000000 + usecs
            if "sales_condition" in data:
                quote.sales_condition = data["sales_condition"]
        elif data_type == 2:  # BBO
            quote.type = 1  # TYPE_BESTBID
            quote.scaled_price = int(data.get("bid_price", 0) * 10000)
            quote.scaled_volume = int(data.get("bid_volume", 0))

            ask = rtd.quotes.add()
            ask.type = 2  # TYPE_BESTASK
            ask.scaled_price = int(data.get("ask_price", 0) * 10000)
            ask.scaled_volume = int(data.get("ask_volume", 0))

        sm = _ServerMsg()
        sm.real_time_market_data.add().CopyFrom(rtd)
        return ("server_msg", sm)

    async def handle_message(self, msg_bytes: bytes) -> list:
        """
        Process a CQG ClientMsg protobuf and return a list of (type, payload).
        type is 'server_msg' for ServerMsg protobufs, or 'close' to disconnect.
        """
        if not _PROTOBUF_AVAILABLE:
            return [("close",)]

        msg = _ClientMsg()
        try:
            msg.ParseFromString(msg_bytes)
        except Exception as e:
            log.error(f"[CQG] Failed to parse ClientMsg: {e}")
            return [("close",)]

        responses = []

        if msg.HasField("logon"):
            responses.append(self._handle_logon(msg.logon))

        if msg.HasField("logoff"):
            log.info("[CQG] Client logoff")
            responses.append(("close",))

        if msg.HasField("ping"):
            pong = _ServerMsg()
            pong.pong.SetInParent()
            responses.append(("server_msg", pong))

        for req in msg.information_requests:
            resp = await self._handle_information_request(req)
            if resp:
                responses.append(resp)

        for req in msg.market_data_subscriptions:
            resp = await self._handle_market_data_subscription(req)
            if resp:
                responses.append(resp)

        for req in msg.time_and_sales_requests:
            resp = await self._handle_time_and_sales(req)
            if resp:
                responses.append(resp)

        for req in msg.time_bar_requests:
            resp = await self._handle_time_bar(req)
            if resp:
                responses.append(resp)

        return responses

    def _handle_logon(self, logon) -> tuple:
        """Return a successful LogonResult."""
        log.info(f"[CQG] Logon: user='{logon.user_name}' label='{logon.private_label}'")
        lr = _ServerMsg()
        lr.logon_result.result_code = 0
        lr.logon_result.base_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        lr.logon_result.server_time = int(datetime.now(timezone.utc).timestamp())
        lr.logon_result.protocol_version_major = 2
        lr.logon_result.protocol_version_minor = 0
        lr.logon_result.user_id = 1000
        return ("server_msg", lr)

    async def _handle_information_request(self, req) -> tuple:
        """Symbol resolution: CQG symbol → Rithmic search_symbols."""
        if not self.connected or not self.rithmic:
            return None

        # Check if this is a symbol resolution request
        if not req.HasField("symbol_resolution_request"):
            return None

        srr = req.symbol_resolution_request
        symbol = srr.symbol
        log.info(f"[CQG] Symbol resolution: '{symbol}'")

        try:
            results = await self.rithmic.search_symbols(
                search_text=symbol,
                pattern=1,  # CONTAINS
            )
        except Exception as e:
            log.warning(f"[RTHM] search_symbols failed: {e}")
            results = []

        # Build InformationReport
        ir = _ServerMsg()
        report = ir.information_reports.add()
        report.id = req.id
        report.status_code = 0
        report.is_report_complete = True

        if results:
            for r in results:
                if isinstance(r, list):
                    for item in r:
                        self._add_symbol_resolution(report, item, symbol)
                else:
                    self._add_symbol_resolution(report, r, symbol)

        if not report.HasField("symbol_resolution_report"):
            # No results — add a basic entry
            cid = self.registry.resolve(symbol, "CME", {"symbol": symbol, "exchange": "CME"})
            sr = _SymbolResolutionReport()
            sr.contract_metadata.contract_id = cid
            sr.contract_metadata.contract_symbol = symbol
            sr.contract_metadata.cqg_contract_symbol = symbol
            sr.contract_metadata.description = f"{symbol}"
            sr.contract_metadata.title = symbol
            sr.contract_metadata.tick_size = 0.25
            sr.contract_metadata.tick_value = 12.50
            sr.contract_metadata.currency = "USD"
            sr.contract_metadata.cfi_code = "F"
            sr.contract_metadata.correct_price_scale = 2.0
            sr.contract_metadata.display_price_scale = 2
            report.symbol_resolution_report.CopyFrom(sr)

        return ("server_msg", ir)

    def _add_symbol_resolution(self, report, rithmic_result, requested_symbol: str):
        """Add a resolved symbol to the CQG InformationReport."""
        if not _PROTOBUF_AVAILABLE:
            return

        symbol = getattr(rithmic_result, "trading_symbol",
                        getattr(rithmic_result, "symbol", requested_symbol))
        exchange = getattr(rithmic_result, "exchange", "CME")
        description = getattr(rithmic_result, "description", f"{symbol} {exchange}")
        tick_size = getattr(rithmic_result, "tick_size", 0.25)
        tick_value = getattr(rithmic_result, "tick_value", 12.50)

        cid = self.registry.resolve(symbol, exchange, {
            "symbol": symbol, "exchange": exchange,
            "tick_size": tick_size, "tick_value": tick_value,
        })

        sr = _SymbolResolutionReport()
        sr.contract_metadata.contract_id = cid
        sr.contract_metadata.contract_symbol = symbol
        sr.contract_metadata.cqg_contract_symbol = symbol
        sr.contract_metadata.description = description
        sr.contract_metadata.title = symbol
        sr.contract_metadata.tick_size = float(tick_size)
        sr.contract_metadata.tick_value = float(tick_value)
        sr.contract_metadata.currency = "USD"
        sr.contract_metadata.cfi_code = "F"
        sr.contract_metadata.correct_price_scale = 2.0
        sr.contract_metadata.display_price_scale = 2
        report.symbol_resolution_report.CopyFrom(sr)

    async def _handle_market_data_subscription(self, req) -> tuple:
        """Subscribe to real-time market data via Rithmic."""
        if not self.connected or not self.rithmic:
            return None

        meta = self.registry.get_meta(req.contract_id)
        symbol = meta.get("symbol")
        exchange = meta.get("exchange")
        if not symbol:
            sym_info = self.registry.get_symbol(req.contract_id)
            if sym_info:
                symbol, exchange = sym_info

        if not symbol:
            log.warning(f"[CQG] MktData sub for unknown contract_id={req.contract_id}")
            return None

        log.info(f"[CQG] MktData sub: contract_id={req.contract_id} {symbol}/{exchange} level={req.level}")

        try:
            level = req.level
            data_type = 1  # LAST_TRADE
            if level >= 2:
                data_type = 3  # LAST_TRADE + BBO
            await self.rithmic.subscribe_to_market_data(symbol, exchange, data_type=data_type)
            log.info(f"[RTHM] Subscribed to {symbol}/{exchange} (type={data_type})")
        except Exception as e:
            log.warning(f"[RTHM] Subscribe failed for {symbol}/{exchange}: {e}")

        status = _ServerMsg()
        s = status.market_data_subscription_statuses.add()
        s.contract_id = req.contract_id
        s.status_code = 0
        s.level = req.level
        return ("server_msg", status)

    async def _handle_time_and_sales(self, req) -> tuple:
        """Historical tick data — returns a basic completion for now."""
        log.info(f"[CQG] TimeAndSales request_id={req.request_id} contract_id={req.time_and_sales_parameters.contract_id}")
        tsr = _ServerMsg()
        r = tsr.time_and_sales_reports.add()
        r.request_id = req.request_id
        r.result_code = 0
        r.is_report_complete = True
        return ("server_msg", tsr)

    async def _handle_time_bar(self, req) -> tuple:
        """Historical bar data — returns a basic completion for now."""
        log.info(f"[CQG] TimeBar request_id={req.request_id}")
        tbr = _ServerMsg()
        r = tbr.time_bar_reports.add()
        r.request_id = req.request_id
        r.status_code = 0
        r.is_report_complete = True
        r.reached_start_of_data = True
        return ("server_msg", tbr)

    async def consume_tick_queue(self):
        """Background task: pull Rithmic ticks from queue and return them."""
        while True:
            msg_type, data = await self._response_queue.get()
            if msg_type == "tick":
                result = await self.process_tick(data)
                if result:
                    yield result
            elif msg_type == "server_msg":
                yield (msg_type, data)
