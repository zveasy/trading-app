#!/usr/bin/env python3
"""
scripts.demo_sender
───────────────────
Batch-publishes CancelReplaceRequest protobufs read from a YAML file to
tcp://127.0.0.1:5555.

Usage:
    python -m scripts.demo_sender data/demo_orders.yaml --delay 1.0 [--loop]

Options:
    --delay FLOAT   Seconds to wait between rows  (default = 1.0)
    --loop          Repeat the file forever (for stress testing)
"""

from __future__ import annotations
import argparse, time, yaml, zmq, pathlib, itertools
from tests import cr_pb2

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("yaml_file", help="YAML file with proto rows")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between sends")
    p.add_argument("--loop", action="store_true", help="loop forever")
    return p.parse_args()

def load_rows(path: pathlib.Path):
    with path.open() as fh:
        raw = yaml.safe_load(fh)
    for row in raw:
        yield {
            "proto": int(row["proto"]),
            "qty":   int(row["qty"]),
            "px":    float(row["px"]),
            "sym":   row.get("sym", "AAPL"),
        }

def build_proto(row) -> bytes:
    msg = cr_pb2.CancelReplaceRequest()
    msg.order_id          = row["proto"]
    msg.params.new_qty    = row["qty"]
    msg.params.new_price  = row["px"]
    return msg.SerializeToString()

def main():
    args = parse_args()
    path = pathlib.Path(args.yaml_file).resolve()
    rows = list(load_rows(path))
    total = len(rows)

    ctx  = zmq.Context()
    sock = ctx.socket(zmq.PUSH)
    sock.connect("tcp://127.0.0.1:5555")
    print(f"Connected to tcp://127.0.0.1:5555. Sending {total} messages …")

    iterator = itertools.cycle(rows) if args.loop else rows

    count = 0
    for row in iterator:
        sock.send(build_proto(row))
        count += 1
        print(f"📤 Sent proto={row['proto']:>5} qty={row['qty']:>4} px={row['px']}")
        time.sleep(args.delay)

        if not args.loop and count == total:
            break

    print("✅  All messages sent." if not args.loop else "🔁 Loop finished (interrupted).")

if __name__ == "__main__":
    main()
