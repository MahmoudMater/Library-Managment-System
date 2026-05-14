#!/usr/bin/env bash
set -euo pipefail

# Generates lots of 4xx validation/auth errors (and 404s) so you can see:
# - Error rate panels in Grafana (Prometheus)
# - Recent WARNING/ERROR logs panel in Grafana (Loki)
#
# This project logs 4xx responses as WARNING in the request middleware,
# so they show up in the Loki panel that filters WARNING/ERROR.
#
# Usage:
#   ./scripts/observability/generate_errors.sh
#
# Optional env:
#   API_BASE_URL=http://localhost:8000
#   TOTAL_401=2000
#   TOTAL_422=500
#   TOTAL_404=2000
#   TOTAL_403=500
#   CONCURRENCY=50

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TOTAL_401="${TOTAL_401:-200}"
TOTAL_422="${TOTAL_422:-50}"
TOTAL_404="${TOTAL_404:-200}"
TOTAL_403="${TOTAL_403:-50}"
CONCURRENCY="${CONCURRENCY:-30}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COOKIES_MEMBER="${ROOT_DIR}/.tmp_cookies_member.txt"

rm -f "${COOKIES_MEMBER}"

echo "API_BASE_URL=${API_BASE_URL}"
echo "CONCURRENCY=${CONCURRENCY}"

echo "1) Generate 401 (no auth cookie) ..."
seq 1 "${TOTAL_401}" | xargs -n1 -P "${CONCURRENCY}" bash -lc \
  "curl -sS -o /dev/null \"${API_BASE_URL}/books\" || true"
echo "401 generated=${TOTAL_401}"

echo "2) Generate 422 validation errors (bad email) ..."
seq 1 "${TOTAL_422}" | xargs -n1 -P "${CONCURRENCY}" bash -lc \
  "curl -sS -o /dev/null -H \"Content-Type: application/json\" -d '{\"full_name\":\"X\",\"email\":\"admin2@dev.local\",\"password\":\"pw\"}' \"${API_BASE_URL}/auth/register\" || true"
echo "422 generated=${TOTAL_422}"

echo "3) Generate 404s ..."
seq 1 "${TOTAL_404}" | xargs -n1 -P "${CONCURRENCY}" bash -lc \
  "curl -sS -o /dev/null \"${API_BASE_URL}/this-route-does-not-exist\" || true"
echo "404 generated=${TOTAL_404}"

echo "4) Generate 403 (member tries admin-only endpoint) ..."
# Register + login a member to get cookies
email="member-obs-$(date +%s)@example.com"
curl -sS -c "${COOKIES_MEMBER}" -b "${COOKIES_MEMBER}" \
  -H "Content-Type: application/json" \
  -d "{\"full_name\":\"Obs Member\",\"email\":\"${email}\",\"password\":\"memberpassword\"}" \
  "${API_BASE_URL}/auth/register" >/dev/null || true

curl -sS -c "${COOKIES_MEMBER}" -b "${COOKIES_MEMBER}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${email}\",\"password\":\"memberpassword\"}" \
  "${API_BASE_URL}/auth/login" >/dev/null || true

export API_BASE_URL COOKIES_MEMBER
seq 1 "${TOTAL_403}" | xargs -n1 -P "${CONCURRENCY}" bash -lc \
  "curl -sS -o /dev/null -b \"${COOKIES_MEMBER}\" \"${API_BASE_URL}/users\" || true"
echo "403 generated=${TOTAL_403}"

echo "Done. In Grafana (http://localhost:3001) check:"
echo "- FastAPI overview → HTTP requests/sec + 5xx rate (may remain low) + logs panel (should show WARNING entries)."

