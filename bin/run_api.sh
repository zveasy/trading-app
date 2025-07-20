#!/usr/bin/env bash

set -euo pipefail

uvicorn api.health:app --host 0.0.0.0 --port 8000
