from scripts.helpers import wait_order_active

class FakeApp:
    def __init__(self):
        self.order_statuses = {}

def test_wait_order_active_hits_timeout():
    app = FakeApp()
    assert wait_order_active(app, 42, timeout=0.05) is False

def test_wait_order_active_succeeds():
    app = FakeApp()
    app.order_statuses[99] = {"status": "Submitted"}
    assert wait_order_active(app, 99, timeout=0.01) is True
