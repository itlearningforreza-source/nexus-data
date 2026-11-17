#!/usr/bin/env bash
# Start the Nexus Data backend in the background (detached) for local dev.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fuser -k 8011/tcp 2>/dev/null || true
sleep 1
cd "$DIR"
rm -f nexus.db nexus.db-wal nexus.db-shm
setsid bash -c 'exec python3 -u -m uvicorn main:app --host 0.0.0.0 --port 8011 > /tmp/nexus_uv.log 2>&1' < /dev/null &
disown
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8011/health >/dev/null 2>&1; then
    echo "Nexus Data backend ready on http://127.0.0.1:8011"
    exit 0
  fi
  sleep 1
done
echo "Backend failed to start; see /tmp/nexus_uv.log" >&2
exit 1