#!/usr/bin/env bash
# Import AIIS Kibana dashboards and configure index pattern
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
ES_URL="${ES_URL:-http://localhost:9200}"

echo "Waiting for Kibana to be ready..."
until curl -sf "${KIBANA_URL}/api/status" > /dev/null 2>&1; do
  sleep 3
done
echo "Kibana is ready."

# Create index pattern
echo "Creating index pattern: aiis-events-*"
curl -sf -X POST "${KIBANA_URL}/api/saved_objects/index-pattern/aiis-events-pattern" \
  -H "kbn-xsrf: true" \
  -H "Content-Type: application/json" \
  -d '{
    "attributes": {
      "title": "aiis-events-*",
      "timeFieldName": "timestamp"
    }
  }' || echo "(index pattern may already exist)"

# Import dashboards
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/dashboards/aiis-dashboards.ndjson" ]; then
  echo "Importing dashboards..."
  curl -sf -X POST "${KIBANA_URL}/api/saved_objects/_import?overwrite=true" \
    -H "kbn-xsrf: true" \
    --form "file=@${SCRIPT_DIR}/dashboards/aiis-dashboards.ndjson"
  echo ""
fi

echo ""
echo "Kibana setup complete!"
echo "Access Kibana at: ${KIBANA_URL}"
echo ""
echo "Available dashboards:"
echo "  - AIIS Workflow Overview"
echo "  - AIIS Agent Performance"
echo "  - AIIS MCP Tool Usage"
echo "  - AIIS A2A Communication"
echo "  - AIIS RAG Retrieval"
echo "  - AIIS Errors & Retries"
echo ""
echo "Explore events with:"
echo "  GET ${ES_URL}/aiis-events-*/_search"
