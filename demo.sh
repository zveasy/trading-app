# demo.sh  (root of repo)
#!/usr/bin/env bash
set -euo pipefail

echo "🔄  Rebuilding & starting stack..."
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d --build

echo "⏳  Waiting for receiver health-check..."
until docker compose -f infra/docker-compose.yml \
        ps | grep receiver | grep -q '(healthy)'; do
  sleep 1
done

echo "🚀  Sending 15 demo orders (3 × 5-row YAML)…"
for _ in {1..3}; do
  python -m scripts.demo_sender data/demo_orders.yaml --delay 0.2
done

echo "📊  Grafana dashboard → http://localhost:3000"
echo "✅  Demo finished."
