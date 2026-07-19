#!/usr/bin/env bash
# Set up AIIS Kibana dashboards.
#
# Creates the data view, all visualizations, and two dashboards via the
# Kibana REST API using the Python script at scripts/create_kibana_dashboards.py.
#
# Usage:
#   bash kibana/setup.sh
#   KIBANA_URL=http://myhost:5601 bash kibana/setup.sh
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
ES_URL="${ES_URL:-http://localhost:9200}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Waiting for Kibana to be ready..."
until curl -sf "${KIBANA_URL}/api/status" > /dev/null 2>&1; do
  sleep 3
done
echo "Kibana is ready."

echo ""
echo "Creating AIIS dashboards..."
KIBANA_URL="${KIBANA_URL}" uv run --directory "${REPO_ROOT}" \
  python scripts/create_kibana_dashboards.py

echo ""
echo "Kibana setup complete!"
echo "Access Kibana at: ${KIBANA_URL}"
echo ""
echo "Available dashboards:"
echo "  AIIS — Issue Status : ${KIBANA_URL}/app/dashboards#/view/aiis-issue-status-dashboard"
echo "  AIIS — Trace & Debug: ${KIBANA_URL}/app/dashboards#/view/aiis-trace-debug-dashboard"
echo ""
echo "Each dashboard includes full payload sections at the bottom —"
echo "expand any row to see complete request/response content."
echo ""
echo "Explore raw events:"
echo "  GET ${ES_URL}/aiis-events-*/_search"
