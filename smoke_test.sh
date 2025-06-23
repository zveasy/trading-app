#!/bin/bash

set -e

echo "==> [1/5] Bringing down any running stack..."
docker compose -f infra/docker-compose.yml down -v

echo "==> [2/5] Starting the stack fresh..."
docker compose -f infra/docker-compose.yml up -d

echo "Waiting for receiver metrics endpoint to become available..."
until curl -sf http://localhost:9100/metrics >/dev/null; do
  echo "  ...waiting for metrics endpoint..."
  sleep 2
done
echo "Receiver metrics endpoint is up!"

echo "==> [3/5] Sending demo orders (valid batch)..."
python3 -m scripts.demo_sender data/demo_orders.yaml --delay 0.2

echo "==> [4/5] Checking receiver_msgs_total..."
curl -s http://localhost:9100/metrics | grep receiver_msgs_total

echo "==> [5/5] Checking error counter (receiver_errors_total)..."
curl -s http://localhost:9100/metrics | grep receiver_errors_total

echo "Smoke test: Valid orders sent and metrics checked!"
echo "Now: Open Grafana at http://localhost:3000 and watch the metrics curve update."

echo ""
echo "=== (Optional) Malformed order test ==="
echo "If you want to test error handling, manually edit 'data/demo_orders.yaml' to add a malformed row and re-run the sender, or run:"
echo 'python3 -m scripts.demo_sender data/malformed_orders.yaml --delay 0.2'
echo "Then re-check receiver_errors_total above."
