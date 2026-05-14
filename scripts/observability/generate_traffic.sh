#!/usr/bin/env bash
set -euo pipefail

# Generates healthy traffic to populate Prometheus/Grafana metrics.
# Requires the stack running via docker compose (backend, postgres, redis, prometheus, grafana, loki, promtail).
#
# Usage:
#   ./scripts/observability/generate_traffic.sh
#
# Optional env:
#   API_BASE_URL=http://localhost:8000
#   ADMIN_EMAIL=admin@book.com
#   ADMIN_PASSWORD=admin@password
#   TOTAL_REQUESTS=10000        # set to 1000000 for "million requests"
#   CONCURRENCY=50              # number of parallel workers
#   TARGET_PATH=/books          # endpoint to hammer (auth required for most)
#   SLEEP_BETWEEN_BATCHES=0     # seconds

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@book.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin@password}"
TOTAL_REQUESTS="${TOTAL_REQUESTS:-10000}"
CONCURRENCY="${CONCURRENCY:-50}"
TARGET_PATH="${TARGET_PATH:-/books}"
SLEEP_BETWEEN_BATCHES="${SLEEP_BETWEEN_BATCHES:-0}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COOKIES="${ROOT_DIR}/.tmp_cookies_admin.txt"

mkdir -p "${ROOT_DIR}"
rm -f "${COOKIES}"

echo "API_BASE_URL=${API_BASE_URL}"
echo "TOTAL_REQUESTS=${TOTAL_REQUESTS}"
echo "CONCURRENCY=${CONCURRENCY}"
echo "TARGET_PATH=${TARGET_PATH}"

echo "1) Login as admin (cookies)..."
curl -sS -c "${COOKIES}" -b "${COOKIES}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
  "${API_BASE_URL}/auth/login" >/dev/null

echo "2) Create a few books (idempotent-ish via unique ISBN)..."
ts="$(date +%s)"
for i in 1 2 3; do
  isbn="OBS-${ts}-${i}"
  curl -sS -c "${COOKIES}" -b "${COOKIES}" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"Obs Book ${i}\",\"author\":\"System\",\"isbn\":\"${isbn}\",\"total_copies\":3,\"available_copies\":3}" \
    "${API_BASE_URL}/books" >/dev/null || true
done

echo "3) Hit /books list multiple times to show cache HIT/MISS..."
for i in {1..10}; do
  curl -sS -D - -o /dev/null -b "${COOKIES}" "${API_BASE_URL}/books" \
    | awk 'tolower($0) ~ /^x-cache:/ {print "X-Cache:", $2}' || true
  sleep 0.2
done

echo "4) High traffic run (parallel curl)..."
echo "   This will generate TOTAL_REQUESTS requests to ${TARGET_PATH}."
export API_BASE_URL COOKIES TARGET_PATH

_worker() {
  curl -sS -o /dev/null -b "${COOKIES}" "${API_BASE_URL}${TARGET_PATH}" || true
}
export -f _worker

# Use xargs parallelism (portable; no extra deps).
seq 1 "${TOTAL_REQUESTS}" \
  | xargs -n1 -P "${CONCURRENCY}" bash -lc '_worker' >/dev/null

if [[ "${SLEEP_BETWEEN_BATCHES}" != "0" ]]; then
  sleep "${SLEEP_BETWEEN_BATCHES}" || true
fi

echo "5) Hit /health and /metrics (sanity)..."
curl -sS -o /dev/null "${API_BASE_URL}/health" || true
curl -sS -o /dev/null "${API_BASE_URL}/metrics" || true

echo "Done. Open Grafana at http://localhost:3001 and refresh the 'FastAPI overview' dashboard."

