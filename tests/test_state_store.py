from scripts.state_store import StateStore
import tempfile, os

def test_load_and_upsert(tmp_path):
    db = tmp_path / "state.db"
    store = StateStore(db)
    assert store.load() == {}
    store.upsert(10001, "AAPL", 42)
    store.upsert(10002, "MSFT", 99)
    assert store.load() == {(10001,"AAPL"):42, (10002,"MSFT"):99}

def test_replace_existing(tmp_path):
    db = tmp_path / "state.db"
    store = StateStore(db)
    store.upsert(10001, "AAPL", 42)
    store.upsert(10001, "AAPL", 43)
    assert store.load() == {(10001,"AAPL"):43}
