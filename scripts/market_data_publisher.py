#!/usr/bin/env python3
"""Publish IB market data ticks over ZeroMQ.

Connects to Interactive Brokers via `ib_insync`, converts tick
updates into `MarketTick` protobuf messages and publishes them on a
ZeroMQ ``PUB`` socket. Prometheus metrics ``ticks_total`` and
``tick_latency_ms`` track volume and publishing latency.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import signal
import time
from typing import Iterable, List, Tuple

import zmq
from ib_insync import IB, Stock, Option
from prometheus_client import Counter, Histogram, start_http_server

from shared_proto.market_data_pb2 import MarketTick
from utils.utils import setup_logger

# ── Prometheus metrics ──────────────────────────────────────────────
ticks_total = Counter("ticks_total", "Total market data ticks published")
tick_latency_ms = Histogram(
    "tick_latency_ms", "Latency between tick receipt and publish (ms)"
)


# ── Signal handling ─────────────────────────────────────────────────
_SHUTDOWN = False


def _request_shutdown(_sig: int, _frm) -> None:
    global _SHUTDOWN
    _SHUTDOWN = True


# ── CLI parsing ─────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("IB market data publisher")
    p.add_argument(
        "--symbols",
        default="",
        help="comma-separated list of stock tickers (e.g. AAPL,MSFT)",
    )
    p.add_argument(
        "--options",
        default="",
        help=(
            "comma-separated equity options in OCC format. Examples: "
            "AAPL_20250117C150, MSFT-20241220P320, or components as "
            "SYMBOL:YYYYMMDD:RIGHT:STRIKE"
        ),
    )
    p.add_argument("--opt-exchange", default="SMART", help="Option exchange (default SMART)")
    p.add_argument("--opt-currency", default="USD", help="Option currency (default USD)")
    p.add_argument("--zmq-addr", default="tcp://*:6001", help="ZeroMQ PUB bind address")
    p.add_argument("--log-level", default="INFO", help="logging level (default INFO)")
    return p.parse_args()


# ── Tick handler ────────────────────────────────────────────────────


def _handle_tick(sock: zmq.Socket, ticker) -> None:
    start = time.perf_counter()
    msg = MarketTick(
        symbol=(getattr(ticker.contract, "localSymbol", None) or ticker.contract.symbol),
        ts_unix_ns=time.time_ns(),
        bid_price=float(ticker.bid or 0.0),
        ask_price=float(ticker.ask or 0.0),
        last_price=float(getattr(ticker, "last", 0.0) or 0.0),
        bid_size=int(ticker.bidSize or 0),
        ask_size=int(ticker.askSize or 0),
        last_size=int(ticker.lastSize or 0),
        venue=getattr(ticker, "marketCenter", "SMART") or "SMART",
    )
    sock.send_multipart([b"market_ticks", msg.SerializeToString()])
    ticks_total.inc()
    tick_latency_ms.observe((time.perf_counter() - start) * 1000)


def _parse_occ_token(tok: str) -> Tuple[str, str, str, float]:
    """
    Parse a single OCC-style option token into components.
    Accepted forms:
      - SYMBOL_YYYYMMDDC123
      - SYMBOL-YYYYMMDDP123.5
      - SYMBOL:YYYYMMDD:RIGHT:STRIKE
    Returns: (symbol, yyyymmdd, right, strike)
    """
    tok = tok.strip()
    if not tok:
        raise ValueError("empty option token")

    # SYMBOL:YYYYMMDD:RIGHT:STRIKE
    if ":" in tok:
        sym, yyyymmdd, right, strike = tok.split(":", 3)
        return sym.upper(), yyyymmdd, right.upper(), float(strike)

    # Normalize separators to underscore for easier regex
    norm = tok.replace("-", "_")
    m = re.match(r"^([A-Za-z0-9]+)_([0-9]{8})([CPcp])([0-9]+(?:\.[0-9]+)?)$", norm)
    if not m:
        raise ValueError(f"invalid OCC token: {tok}")
    sym, yyyymmdd, right, strike = m.groups()
    return sym.upper(), yyyymmdd, right.upper(), float(strike)


# ── Main entry ──────────────────────────────────────────────────────


def main() -> None:
    args = _parse_args()
    level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger = setup_logger("MarketDataPublisher", level=level)

    start_http_server(int(os.getenv("METRICS_PORT", "9100")))

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.PUB)
    sock.bind(args.zmq_addr)
    logger.info("ZeroMQ PUB bound to %s", args.zmq_addr)

    ib = IB()
    ib_host = os.getenv("IB_HOST", "127.0.0.1")
    ib_port = int(os.getenv("IB_PORT", "7497"))
    client_id = int(os.getenv("IB_CLIENT_ID", "50"))
    ib.connect(ib_host, ib_port, clientId=client_id)
    logger.info("Connected to IB %s:%s (clientId=%s)", ib_host, ib_port, client_id)

    # Stocks
    symbols: Iterable[str] = [
        s.strip().upper() for s in (args.symbols or "").split(",") if s.strip()
    ]
    tickers = []
    for sym in symbols:
        contract = Stock(sym, "SMART", "USD")
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract, "", False, False)
        ticker.updateEvent += lambda t, _sock=sock: _handle_tick(_sock, t)
        tickers.append(ticker)
    if symbols:
        logger.info("Subscribed to stocks: %s", ", ".join(symbols))

    # Equity Options
    option_tokens: List[str] = [s for s in (args.options or "").split(",") if s.strip()]
    opt_contracts = []
    for tok in option_tokens:
        try:
            sym, yyyymmdd, right, strike = _parse_occ_token(tok)
        except Exception as e:
            logger.error("Skipping invalid option spec %r: %s", tok, e)
            continue
        opt = Option(
            sym,
            lastTradeDateOrContractMonth=yyyymmdd,
            strike=float(strike),
            right=right,
            exchange=args.opt_exchange,
            currency=args.opt_currency,
        )
        ib.qualifyContracts(opt)
        t = ib.reqMktData(opt, "", False, False)
        t.updateEvent += lambda _t, _sock=sock: _handle_tick(_sock, _t)
        tickers.append(t)
        opt_contracts.append(opt)
    if option_tokens:
        logger.info(
            "Subscribed to options: %s",
            ", ".join([getattr(c, "localSymbol", f"{c.symbol} {c.lastTradeDateOrContractMonth}{c.right}{c.strike}") for c in opt_contracts]),
        )

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    try:
        while not _SHUTDOWN:
            ib.sleep(0.2)
    finally:
        for t in tickers:
            ib.cancelMktData(t.contract)
        ib.disconnect()
        sock.close()
        ctx.term()
        logger.info("✅ Shutdown complete.")


if __name__ == "__main__":
    main()
