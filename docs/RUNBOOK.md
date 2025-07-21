# Incidents RUNBOOK

## 1. High-level architecture diagram

```text
Sender/Clients --> ZMQ Receiver --> IB Gateway --> Market
                     |                ^
                     v                |
                Metrics/Logs <--------+
```

## 2. Common incidents & resolutions

### “Stuck ‘Connecting…’ to IB” – steps
- Verify TWS or IB Gateway is running and reachable
- Check network connectivity to the IB host/port
- Restart the receiver service if connection is stale

### Kill-switch activation
- Inspect Redis key `kill_switch` to confirm status
- Clear the key or set to `0` to resume trading
- Document the event in the daily log

### Latency spike > 500 ms
- Review Prometheus metrics for `order_latency_ms`
- Check system load and network conditions
- If persistent, fail over to backup connection

## 3. Upgrade procedure & rollback
- Tag current release and push to remote
- Deploy new container images via Helm
- Monitor health checks and metrics
- To rollback: redeploy previous image tag

## 4. Compliance logs – where to pull daily blotter
- Blotter CSV generated at `/var/log/trading/blotter-<date>.csv`
- Use `scripts/upload_blotter.py` to archive to compliance storage

## 5. Contact rotation table

| Day       | Primary | Secondary |
|-----------|---------|-----------|
| Monday    | Alice   | Bob       |
| Tuesday   | Bob     | Carol     |
| Wednesday | Carol   | Dave      |
| Thursday  | Dave    | Eve       |
| Friday    | Eve     | Alice     |

