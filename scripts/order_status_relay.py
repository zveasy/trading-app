#!/usr/bin/env python3
"""Relay IB order updates over ZeroMQ."""
from __future__ import annotations

import argparse
import logging
import os
import signal
import time
from typing import Dict

import zmq
from ib_insync import IB, Ticker, Trade
from prometheus_client import Counter, start_http_server

from shared_proto.order_update_pb2 import OrderUpdate
from utils.utils import setup_logger


order_updates_total = Counter(
    "order_updates_total", "Total order status updates", ["status"]
)

_SHUTDOWN = False


def _request_shutdown(_sig: int, _frm) -> None:
    global _SHUTDOWN
    _SHUTDOWN = True


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("IB Order Status Relay")
    p.add_argument(
        "--zmq-addr",
        default=os.getenv("ZMQ_ADDR", "tcp://*:6002"),
        help="ZeroMQ PUB bind address",
    )
    p.add_argument(
        "--ib-host", default=os.getenv("IB_HOST", "127.0.0.1"), help="TWS / IBGW host"
    )
    p.add_argument(
        "--ib-port",
        type=int,
        default=int(os.getenv("IB_PORT", "7497")),
        help="TWS / IBGW port",
    )
    p.add_argument(
        "--client-id",
        type=int,
        default=int(os.getenv("IB_CLIENT_ID", "60")),
        help="IB client id",
    )
    p.add_argument("--log-level", default="INFO", help="Logging level (default INFO)")
    return p.parse_args()


def start(ib: IB, zmq_addr: str) -> tuple[zmq.Context, zmq.Socket]:
    """Attach event handlers to ``ib`` and publish updates on ``zmq_addr``."""
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.PUB)
    sock.bind(zmq_addr)

    last_tickers: Dict[int, Ticker] = {}

    def on_tickers(tickers):
        for t in tickers:
            if t.contract:
                last_tickers[t.contract.conId] = t

    def on_status(trade: Trade):
        status = trade.orderStatus.status or ""
        msg = OrderUpdate(
            ts_unix_ns=time.time_ns(),
            symbol=getattr(trade.contract, "symbol", ""),
            side=getattr(trade.order, "action", ""),
            fill_px=float(getattr(trade.orderStatus, "avgFillPrice", 0.0) or 0.0),
            fill_qty=int(getattr(trade.orderStatus, "filled", 0) or 0),
            status=status,
            order_id=int(getattr(trade.order, "orderId", 0) or 0),
        )
        sock.send_multipart([b"order_updates", msg.SerializeToString()])
        order_updates_total.labels(status=status).inc()

    ib.pendingTickersEvent += on_tickers
    ib.orderStatusEvent += on_status
    return ctx, sock


def main() -> None:
    args = _parse_args()
    level = getattr(logging, args.log_level.upper(), logging.INFO)
    logger = setup_logger("OrderStatusRelay", level=level)

    start_http_server(int(os.getenv("METRICS_PORT", "9100")))

    ib = IB()
    ib.connect(args.ib_host, args.ib_port, clientId=args.client_id)
    logger.info(
        "Connected to IB %s:%s (clientId=%s)",
        args.ib_host,
        args.ib_port,
        args.client_id,
    )

    ctx, sock = start(ib, args.zmq_addr)
    logger.info("ZeroMQ PUB bound to %s", args.zmq_addr)

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    try:
        while not _SHUTDOWN:
            ib.sleep(0.2)
    finally:
        ib.disconnect()
        sock.close()
        ctx.term()
        logger.info("✅ Shutdown complete.")


if __name__ == "__main__":
    main()
