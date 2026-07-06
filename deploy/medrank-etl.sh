#!/usr/bin/env bash
# Monthly ETL: sync the OpenAlex authors snapshot, rebuild the DB atomically.
# The web service keeps serving the old DB until the atomic swap lands.
set -euo pipefail
cd /srv/apps/researchers

echo "=== MedRank ETL $(date -Is) ==="
.venv/bin/python -c "from medrank.etl import sync; print(sync.sync_snapshot())"
.venv/bin/python -m medrank.etl.build
echo "=== ETL done $(date -Is) ==="
# No restart needed: the web app opens a fresh read-only connection per request,
# so the atomic DB swap is picked up automatically.
