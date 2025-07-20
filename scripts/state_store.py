#!/usr/bin/env python3
"""
state_store.py
──────────────
Persistent storage for two slightly different pieces of state:

1.  A simple mapping ``(proto_id, symbol) -> ib_id`` used by the
    cancel/replace receiver.
2.  Periodic snapshots of positions, open orders and PnL which are
    written to a DuckDB database so that a running :class:`TradingApp`
    instance can restore its state after a restart.

The original SQLite mapping logic is kept for backwards compatibility –
tests still rely on ``upsert``/``load``.  New snapshot functionality
uses DuckDB via ``duckdb`` and ``pandas``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Union
import asyncio

import duckdb
import pandas as pd

DEFAULT_DB = Path("./data/state.duckdb")


@dataclass
class SnapshotStruct:
    """Container for the most recent snapshot rows."""

    positions: pd.DataFrame
    orders: pd.DataFrame
    pnl: pd.DataFrame


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
        # If an old SQLite DB exists, drop it so DuckDB doesn't attempt to
        # auto-install the sqlite_scanner extension (blocked in CI).
        if self.path.exists():
            try:
                duckdb.connect(self.path).close()
            except Exception:
                self.path.unlink()
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

    # internal helpers -------------------------------------------------
    def _table_exists(self, conn: duckdb.DuckDBPyConnection, name: str) -> bool:
        q = (
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_name = ?"
        )
        return conn.execute(q, [name]).fetchone()[0] > 0

    def _write_df(
        self, conn: duckdb.DuckDBPyConnection, df: pd.DataFrame, table: str
    ) -> None:
        """Append ``df`` to ``table`` using DuckDB COPY or ``to_duckdb``."""
        if df.empty:
            return

        # Newer pandas versions provide ``DataFrame.to_duckdb``.  Fallback to
        # registering a temporary relation and inserting from it when running
        # on older versions.
        if hasattr(df, "to_duckdb"):
            df.to_duckdb(table, connection=conn, if_exists="append")
            return

        conn.register("tmp_df", df)
        if self._table_exists(conn, table):
            conn.execute(f"INSERT INTO {table} SELECT * FROM tmp_df")
        else:
            conn.execute(f"CREATE TABLE {table} AS SELECT * FROM tmp_df")
        conn.unregister("tmp_df")

    def _snapshot_once(self, trading_app) -> SnapshotStruct:
        trading_app.request_positions()
        trading_app.request_portfolio()

        ts = pd.Timestamp.utcnow()

        positions = getattr(trading_app, "positions", [])
        if isinstance(positions, dict):
            df_pos = pd.DataFrame.from_dict(positions, orient="index")
        else:
            df_pos = pd.DataFrame(positions)
        if not df_pos.empty:
            df_pos.insert(0, "snapshot_ts", ts)
            df_pos = df_pos[["snapshot_ts", "account", "symbol", "position", "avg_cost"]]

        orders = getattr(trading_app, "order_statuses", {})
        df_orders = pd.DataFrame.from_dict(orders, orient="index")
        if not df_orders.empty:
            df_orders.insert(0, "order_id", df_orders.index)
            df_orders.insert(0, "snapshot_ts", ts)
            df_orders = df_orders[["snapshot_ts", "order_id", "status", "filled", "remaining", "avgFillPrice"]]

        pnl = getattr(trading_app, "portfolio", [])
        if isinstance(pnl, dict):
            df_pnl = pd.DataFrame([pnl])
        else:
            df_pnl = pd.DataFrame(pnl)
        if not df_pnl.empty:
            df_pnl.insert(0, "snapshot_ts", ts)
            df_pnl = df_pnl[
                [
                    "snapshot_ts",
                    "symbol",
                    "position",
                    "market_price",
                    "market_value",
                    "average_cost",
                    "unrealized_pnl",
                    "realized_pnl",
                ]
            ]

        with self._conn() as conn:
            self._write_df(conn, df_pos, "positions")
            self._write_df(conn, df_orders, "orders")
            self._write_df(conn, df_pnl, "pnl")
            conn.commit()

        return SnapshotStruct(df_pos, df_orders, df_pnl)

    # ───────────────────────────────────────── snapshots ──────────────────
    async def periodic_snapshot(self, trading_app, interval_s: int = 300):
        """Every ``interval_s`` seconds write TradingApp state to DuckDB."""
        while True:
            self._snapshot_once(trading_app)
            await asyncio.sleep(interval_s)

    def load_last_snapshot(self) -> SnapshotStruct:
        """Load the most recent snapshot from the DB."""
        with self._conn() as conn:
            ts_row = conn.execute(
                "SELECT max(snapshot_ts) FROM positions"
            ).fetchone()
            if not ts_row or ts_row[0] is None:
                empty = pd.DataFrame()
                return SnapshotStruct(empty, empty, empty)
            ts = ts_row[0]
            pos = conn.execute(
                "SELECT * FROM positions WHERE snapshot_ts = ?", [ts]
            ).fetchdf()
            orders = conn.execute(
                "SELECT * FROM orders WHERE snapshot_ts = ?", [ts]
            ).fetchdf()
            pnl = conn.execute(
                "SELECT * FROM pnl WHERE snapshot_ts = ?", [ts]
            ).fetchdf()
        return SnapshotStruct(pos, orders, pnl)

    # ─────────────────────────────────────── internals ────────────────
    def _conn(self) -> duckdb.DuckDBPyConnection:
        # ``duckdb.connect`` expects a string path; ``Path`` objects
        # previously triggered ``TypeError`` during tests.  Convert to ``str``
        # to support ``pathlib.Path`` inputs.
        return duckdb.connect(str(self.path))

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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    snapshot_ts TIMESTAMP,
                    account TEXT,
                    symbol TEXT,
                    position DOUBLE,
                    avg_cost DOUBLE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    snapshot_ts TIMESTAMP,
                    order_id INTEGER,
                    status TEXT,
                    filled DOUBLE,
                    remaining DOUBLE,
                    avg_fill_price DOUBLE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pnl (
                    snapshot_ts TIMESTAMP,
                    symbol TEXT,
                    position DOUBLE,
                    market_price DOUBLE,
                    market_value DOUBLE,
                    average_cost DOUBLE,
                    unrealized_pnl DOUBLE,
                    realized_pnl DOUBLE
                )
                """
            )
            conn.commit()
