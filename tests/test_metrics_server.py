import importlib


def test_start_idempotent(monkeypatch):
    calls = []

    def fake_start(port):
        calls.append(port)
        if len(calls) > 1:
            raise OSError("already started")

    monkeypatch.setattr("scripts.metrics_server.start_http_server", fake_start)
    ms = importlib.import_module("scripts.metrics_server")
    ms.start(9999)
    ms.start(9999)
    assert calls == [9999, 9999]
