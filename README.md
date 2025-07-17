# trading-app
# Setup Instructions

1. Clone the repo
2. Make the script executable:

   chmod +x gridlock_scaffold.sh

3. Run it:

   ./gridlock_scaffold.sh

## Environment Variables

Key settings such as the IB account, host and port are loaded from `.env` if not
provided on the command line.  The most common variables are:

- `IB_ACCOUNT` – default account ID used for orders
- `IB_HOST` / `IB_PORT` – address of TWS or IB Gateway
- `ZMQ_ADDR` – bind address for the receiver (default `tcp://*:5555`)
- `STATE_DB` – path to the persistent SQLite file
- `METRICS_PORT` – port for the Prometheus exporter (default `9100`)
- `JSON_LOGS` – set to `1` to enable JSON formatted logs

# GRIDLOCK Logs

This folder contains structured development logs using the **GRIDLOCK System** — a 14-day rinse-and-repeat cycle designed to help developers ship features with clarity, momentum, and resilience against unknowns.

Each feature or module lives in its own timestamped folder (e.g., `2025-04-09_user-referral-system`) and includes:

- `gutcheck.md`: Day 1 feature breakdown and risk assessment
- Optional files:
  - `sprint_a_plan.md`
  - `lessons_learned.md`
  - `demo_day_notes.md`
  - `test_results.md`

---

## GRIDLOCK 14-Day Cycle Overview

| Phase                 | Days        | Purpose                             |
|-----------------------|-------------|-------------------------------------|
| **Gut Check**         | Day 1       | Define problem, risks, expectations |
| **Sprint Planning**   | Day 2       | Task breakdown & ownership          |
| **Sprint A**          | Days 3–7    | Core build + mid-sprint demo        |
| **Sprint B**          | Days 8–12   | Edge cases, testing, polish         |
| **Ship Window**       | Day 13      | Deploy or merge final build         |
| **Retro & Reset**     | Day 14      | Reflect, document, reset cycle      |

---

## How to Scaffold a New Feature Log

Run the setup script to scaffold a new GRIDLOCK folder.

### 1. Make the script executable (first time only)

```bash
chmod +x gridlock_scaffold.sh


# 1. Start your IB Gateway / TWS (port 7497 paper / 7496 live)

# 2. In trading-app (Python) – activate venv and receiver
cd trading-app
source .venv/bin/activate
PYTHONPATH=. python -m tests.cancel_replace_receiver
# → “Python ZMQ receiver listening on tcp://*:5555 …”

# 3. In QuantEngine (C++)
cd QuantEngine
./test_cancel_replace_zmq              # sends proto ID 10001 twice
# First send ➜ new order, second send ➜ cancel/replace

## Installing shared-proto package
After generating the protobuf stubs you can install the package locally:

```bash
pip install .
```

Then use the generated message definitions in your code:

```python
from shared_proto.market_data_pb2 import MarketTick
```

