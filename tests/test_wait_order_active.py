"""
Unit-test for helpers.wait_order_active()

Uses a *FakeApp* that mimics the TradingApp interface by exposing
`order_statuses` and a method to inject fake status updates.
"""

import time
import threading
from scripts.helpers import wait_order_active


class FakeApp:
    def __init__(self):
        self.order_statuses = {}

    # helper to simulate IB callback
    def push_status(self, oid: int, status: str, delay: float = 0.0):
        def _update():
            if delay:
                time.sleep(delay)
            self.order_statuses[oid] = {"status": status}

        threading.Thread(target=_update, daemon=True).start()


def test_wait_order_active_success():
    app = FakeApp()
    oid = 42

    # push status after 0.3 s – should succeed
    app.push_status(oid, "Submitted", delay=0.3)

    assert wait_order_active(app, oid, timeout=1.0) is True


def test_wait_order_active_timeout():
    app = FakeApp()
    oid = 43

    # never push -> should fail
    assert wait_order_active(app, oid, timeout=0.5) is False


def test_custom_ok_states():
    app = FakeApp()
    oid = 44

    # push custom terminal state that is *not* in default list
    app.push_status(oid, "Filled", delay=0.1)

    # Should succeed only if we override ok_states
    assert wait_order_active(app, oid, ok_states=["Filled"], timeout=1.0) is True
    assert wait_order_active(app, oid, timeout=0.5) is False
