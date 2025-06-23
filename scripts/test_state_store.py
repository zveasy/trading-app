import os
from scripts.state_store import StateStore

def test_upsert_and_reload(tmp_path):
    db_file = tmp_path / "state.db"
    store = StateStore(str(db_file))

    # First insert
    store.upsert(1, "AAPL", 42)
    assert store.load_all() == {(1, "AAPL"): 42}

    # Update same key
    store.upsert(1, "AAPL", 43)
    assert store.load_all() == {(1, "AAPL"): 43}

    # New symbol
    store.upsert(1, "MSFT", 99)
    m = store.load_all()
    assert m[(1, "AAPL")] == 43 and m[(1, "MSFT")] == 99

