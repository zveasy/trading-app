#!/usr/bin/env python3
"""
state_store.py
──────────────
Tiny wrapper around an on-disk SQLite DB that persists the mapping
(proto_id, symbol) → ib_id so we survive process restarts.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Dict, Tuple, Union

DEFAULT_DB = "var/state.db"


class StateStore:
    """
    Example
    -------
    store = StateStore(DEFAULT_DB)
    store.upsert(10001, "AAPL", 42)
    assert store.load() == {(10001, "AAPL"): 42}
    """

    # ───────────────────────────────────────── init ───────────────────
    def __init__(self, db_path: Union[str, Path] = DEFAULT_DB):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # public API ──────────────────────────────────────────────────────
    def load_all(self) -> Dict[Tuple[int, str], int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT proto_id, symbol, ib_id FROM mapping"
            ).fetchall()
        return {(pid, sym): ib for pid, sym, ib in rows}

    def load(self) -> Dict[Tuple[int, str], int]:
        """Backward-compat alias used in tests."""
        return self.load_all()


    def upsert(self, proto_id: int, symbol: str, ib_id: int) -> None:
        """Insert or update a single record."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO mapping (proto_id, symbol, ib_id)
                VALUES (?, ?, ?)
                ON CONFLICT(proto_id, symbol)
                DO UPDATE SET ib_id = excluded.ib_id
                """,
                (proto_id, symbol, ib_id),
            )
            conn.commit()

    # ─────────────────────────────────────── internals ────────────────
    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mapping (
                    proto_id INTEGER NOT NULL,
                    symbol   TEXT    NOT NULL,
                    ib_id    INTEGER NOT NULL,
                    PRIMARY KEY (proto_id, symbol)
                )
                """
            )
            conn.commit()
