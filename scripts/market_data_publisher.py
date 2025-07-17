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
import signal
import time
from typing import Iterable

import zmq
from ib_insync import IB, Stock
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
        required=True,
        help="comma-separated list of tickers (e.g. AAPL,MSFT)",
    )
    p.add_argument("--zmq-addr", default="tcp://*:6001", help="ZeroMQ PUB bind address")
    p.add_argument("--log-level", default="INFO", help="logging level (default INFO)")
    return p.parse_args()


# ── Tick handler ────────────────────────────────────────────────────


def _handle_tick(sock: zmq.Socket, ticker) -> None:
    start = time.perf_counter()
    msg = MarketTick(
        symbol=ticker.contract.symbol,
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

    symbols: Iterable[str] = [
        s.strip().upper() for s in args.symbols.split(",") if s.strip()
    ]
    tickers = []
    for sym in symbols:
        contract = Stock(sym, "SMART", "USD")
        ib.qualifyContracts(contract)
        ticker = ib.reqMktData(contract, "", False, False)
        ticker.updateEvent += lambda t, _sock=sock: _handle_tick(_sock, t)
        tickers.append(ticker)
    logger.info("Subscribed to: %s", ", ".join(symbols))

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
