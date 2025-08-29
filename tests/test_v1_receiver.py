import json
import os
import threading
import time
import zmq


def test_v1_simple_order_ack(monkeypatch):
    # Use dedicated ports for the test
    in_addr = os.environ.get("TEST_V1_IN_ADDR", "tcp://127.0.0.1:5566")
    ack_addr = os.environ.get("TEST_V1_ACK_ADDR", "tcp://127.0.0.1:6009")

    # Set env for receiver
    os.environ["V1_ZMQ_ADDR"] = in_addr
    os.environ["V1_ACK_PUB_ADDR"] = ack_addr
    os.environ["ALLOWED_SYMBOLS"] = "AAPL,MSFT"

    # Fake TradingApp
    class FakeApp:
        def __init__(self, *a, **k):
            pass
        def send_order(self, contract, order):
            return 12345

    import scripts.v1_receiver as v1
    monkeypatch.setattr(v1, "TradingApp", FakeApp)

    # Start receiver in background thread
    th = threading.Thread(target=v1.main, daemon=True)
    th.start()
    time.sleep(0.3)

    ctx = zmq.Context.instance()
    push = ctx.socket(zmq.PUSH)
    push.connect(in_addr)

    sub = ctx.socket(zmq.SUB)
    sub.connect(ack_addr)
    sub.setsockopt(zmq.SUBSCRIBE, b"order_acks")

    env = {
        "version": "v1",
        "correlation_id": "test-1",
        "msg_type": "SimpleOrder",
        "payload": {
            "symbol": "AAPL",
            "action": "BUY",
            "qty": 1,
            "order_type": "MKT",
        },
    }
    push.send_json(env)

    sub.setsockopt(zmq.RCVTIMEO, 3000)
    topic, data = sub.recv_multipart()
    ack = json.loads(data.decode("utf-8"))

    assert ack["correlation_id"] == "test-1"
    assert ack["status"] == "ACCEPTED"
    assert ack.get("order_id") == 12345
