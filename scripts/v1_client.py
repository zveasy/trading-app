from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid

import zmq

try:  # optional protobuf ACK parsing
    from shared_proto import ack_pb2 as ackpb  # type: ignore
except Exception:
    ackpb = None  # type: ignore


def send_simple_order(
    zmq_addr: str,
    ack_sub_addr: str,
    symbol: str,
    action: str,
    qty: int,
    order_type: str = "MKT",
    limit_price: float = 0.0,
    correlation_id: str | None = None,
    timeout_s: float = 5.0,
    max_retries: int = 3,
    backoff_s: float = 0.5,
    idempotency_key: str | None = None,
) -> int:
    ctx = zmq.Context.instance()

    push = ctx.socket(zmq.PUSH)
    push.connect(zmq_addr)

    sub = ctx.socket(zmq.SUB)
    sub.connect(ack_sub_addr)
    sub.setsockopt(zmq.SUBSCRIBE, b"order_acks")
    # also listen for protobuf ACKs if enabled on server
    sub.setsockopt(zmq.SUBSCRIBE, b"order_acks_pb")

    corr = correlation_id or str(uuid.uuid4())
    env = {
        "version": "v1",
        "correlation_id": corr,
        "msg_type": "SimpleOrder",
        "payload": {
            "symbol": symbol,
            "action": action,
            "qty": qty,
            "order_type": order_type,
            "limit_price": limit_price,
            "idempotency_key": idempotency_key or "",
        },
    }

    attempt = 0
    deadline = time.time() + timeout_s
    last_send_ts = 0.0
    poll = zmq.Poller()
    poll.register(sub, zmq.POLLIN)

    while True:
        now = time.time()
        if now - last_send_ts > 0 or attempt == 0:
            push.send_json(env)
            attempt += 1
            last_send_ts = now

        remaining_ms = max(0, int((deadline - time.time()) * 1000))
        if remaining_ms == 0:
            print("Timed out waiting for ACK")
            return 2

        socks = dict(poll.poll(remaining_ms))
        if sub in socks and socks[sub] == zmq.POLLIN:
            topic, data = sub.recv_multipart()
            if topic == b"order_acks_pb" and ackpb is not None:
                try:
                    m = ackpb.Ack()
                    m.ParseFromString(data)
                    if m.correlation_id == corr:
                        print("ACK (pb):", {
                            "version": m.version,
                            "correlation_id": m.correlation_id,
                            "status": m.status,
                            "reason": m.reason,
                            "order_id": m.order_id,
                        })
                        return 0 if m.status == "ACCEPTED" else 3
                except Exception:
                    pass
            else:
                try:
                    ack = json.loads(data.decode("utf-8"))
                    if ack.get("correlation_id") == corr:
                        print("ACK:", json.dumps(ack, indent=2))
                        return 0 if ack.get("status") == "ACCEPTED" else 3
                except Exception:
                    pass

        # Retry/backoff if no ack yet and attempts remain
        if attempt < max_retries and time.time() + backoff_s < deadline:
            time.sleep(backoff_s)
            backoff_s = min(backoff_s * 2, 2.0)
            continue
        # Otherwise keep waiting until deadline without re-sending
        # If deadline elapses, outer loop will return 2


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Send v1 SimpleOrder and await ACK")
    p.add_argument("symbol")
    p.add_argument("action", choices=["BUY", "SELL"]) 
    p.add_argument("qty", type=int)
    p.add_argument("--zmq-addr", default=os.getenv("V1_ZMQ_ADDR", os.getenv("ZMQ_ADDR", "tcp://127.0.0.1:5556")))
    p.add_argument("--ack-sub-addr", default=os.getenv("V1_ACK_PUB_ADDR", "tcp://127.0.0.1:6003"))
    p.add_argument("--order-type", default="MKT")
    p.add_argument("--limit-price", type=float, default=0.0)
    p.add_argument("--timeout", type=float, default=5.0)
    p.add_argument("--max-retries", type=int, default=3)
    p.add_argument("--backoff", type=float, default=0.5)
    p.add_argument("--idempotency-key", default=str(uuid.uuid4()))
    args = p.parse_args()

    rc = send_simple_order(
        zmq_addr=args.zmq_addr,
        ack_sub_addr=args.ack_sub_addr,
        symbol=args.symbol,
        action=args.action,
        qty=args.qty,
        order_type=args.order_type,
        limit_price=args.limit_price,
        timeout_s=args.timeout,
        max_retries=args.max_retries,
        backoff_s=args.backoff,
        idempotency_key=args.idempotency_key,
    )
    sys.exit(rc)
