# trading-app Helm Chart

This chart deploys the trading application along with a ConfigMap for environment variables and exposes metrics for Prometheus.

## Installing

```bash
helm repo add myrepo https://example.com/helm-charts
helm install trading-app myrepo/trading-app
```

## Values

| Key | Description | Default |
|-----|-------------|---------|
| `env.IB_HOST` | IB Gateway host | `127.0.0.1` |
| `env.IB_PORT` | IB Gateway port | `7497` |
| `env.SYMBOLS` | Symbols list | `AAPL,MSFT,GOOG` |
| `env.KILL_SWITCH` | Kill switch flag | `false` |
| `service.metricsPort` | Metrics port | `9100` |
| `hpa.targetValue` | HPA target ticks per second | `5` |

After installation the service exposes metrics at `:9100/metrics` and the readiness probe hits `/ready` on port `8000`.
