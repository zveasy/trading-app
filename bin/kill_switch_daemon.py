#!/usr/bin/env python3
"""CLI entry for the kill switch daemon."""

from __future__ import annotations

import os

from kill_switch import monitor
from scripts.core import TradingApp
from scripts.metrics_server import start as start_metrics


def main() -> None:
    start_metrics(int(os.getenv("METRICS_PORT", "9100")))
    app = TradingApp()
    monitor(app)


if __name__ == "__main__":
    main()

