# AIIS — Agentic Issue Investigation System

A production-quality POC demonstrating a modern **Agentic AI Engineering Platform** that automatically triages GitHub issues, delegates investigations to specialized AI agents, retrieves domain knowledge via RAG, invokes external tools through MCP, and provides enterprise-grade observability with Elasticsearch and Kibana.

---

## Architecture

```text
GitHub Issue Created
        │
        ▼
GitHub Webhook (FastAPI)
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                           │
│                                                                 │
│  start → triage → delegate → update_github → complete          │
│             │          │                                        │
│             │          └──────────── A2A Protocol ──────────┐  │
│             │                                               │  │
│         Supervisor                              ┌───────────┘  │
│         Agent                                   │              │
│         (Claude Haiku                    ┌──────▼──────────┐   │
│          + keyword                       │ Pre-Purchase    │   │
│          fallback)                       │ Agent           │   │
│             │                            │                 │   │
│             │ MCP Tools                  │ • RAG Search    │   │
│             │                            │ • MCP Tools     │   │
│             ▼                            │ • ReAct Loop    │   │
│        ┌─────────┐                       └─────────────────┘   │
│        │ GitHub  │                              OR              │
│        │ Labels  │                       ┌──────────────────┐  │
│        │ Assign  │                       │ Post-Purchase    │  │
│        └─────────┘                       │ Agent            │  │
│                                          │                  │  │
│                                          │ • RAG Search     │  │
│                                          │ • MCP Tools      │  │
│                                          │ • ReAct Loop     │  │
│                                          └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
GitHub Comment (Investigation Report)
        │
        ▼
Elasticsearch Events → Kibana Dashboards
```

---

## Key Architectural Patterns

| Pattern | Implementation |
| ------- | -------------- |
| **Supervisor Orchestration** | LangGraph `StateGraph` with conditional routing |
| **A2A Protocol** | In-memory transport mimicking distributed message bus |
| **MCP Tool Calling** | 13 tools: GitHub, Debugging, Knowledge |
| **RAG** | ChromaDB + Sentence Transformers, per-domain collections |
| **ReAct Loop** | Domain agents iterate: Observe → Reason → Retrieve → Call → Evaluate |
| **Distributed Tracing** | `TraceContext` propagated through all layers |
| **Observability** | Structured JSON logs + Elasticsearch events |

---

## Project Structure

```text
aiis/
├── src/
│   ├── a2a/                      # Agent-to-Agent protocol
│   │   ├── messages.py           # Pydantic message contracts
│   │   ├── transport.py          # In-memory async transport
│   │   ├── registry.py           # Agent discovery registry
│   │   ├── client.py             # A2A client (supervisor → agents)
│   │   └── server.py             # A2A server (agent registration)
│   │
│   ├── agents/
│   │   ├── state.py              # LangGraph shared WorkflowState
│   │   ├── supervisor/
│   │   │   └── agent.py          # Issue Triage Agent (Claude Haiku)
│   │   └── domain/
│   │       ├── base_agent.py     # ReAct investigation loop
│   │       ├── pre_purchase_agent.py
│   │       └── post_purchase_agent.py
│   │
│   ├── mcp_server/
│   │   ├── server.py             # MCP server with tool registry
│   │   └── tools/
│   │       ├── github_tools.py   # GitHub REST API tools
│   │       ├── debugging_tools.py # Kibana, Dynatrace, FlexSearch (mock)
│   │       └── knowledge_tools.py # RAG-backed knowledge tools
│   │
│   ├── rag/
│   │   ├── indexer.py            # Markdown → ChromaDB ingestion
│   │   └── retriever.py          # Semantic search with fallback
│   │
│   ├── observability/
│   │   ├── events.py             # ObservabilityEvent schema (19 event types)
│   │   ├── tracer.py             # TraceContext with ContextVar propagation
│   │   ├── elasticsearch_client.py
│   │   └── logger.py             # JSON structured logging
│   │
│   ├── workflow/
│   │   └── graph.py              # LangGraph StateGraph definition
│   │
│   ├── api/
│   │   └── webhook.py            # FastAPI: /webhook/github, /investigate
│   └── github_client.py          # GitHub REST client
│
├── knowledge-base/
│   ├── pre-purchase/
│   │   ├── troubleshooting-guides/
│   │   ├── runbooks/
│   │   ├── architecture/
│   │   └── previous-issues/
│   └── post-purchase/
│       ├── troubleshooting-guides/
│       ├── runbooks/
│       ├── architecture/
│       └── previous-issues/
│
├── tests/
│   ├── test_a2a.py
│   ├── test_supervisor.py
│   ├── test_mcp_tools.py
│   └── test_workflow.py
│
├── kibana/
│   ├── setup.sh                  # Dashboard import script
│   └── dashboards/
│       └── aiis-dashboards.ndjson
│
├── scripts/
│   ├── simulate_issue.py         # Local demo runner
│   └── index_kb.py               # Knowledge base indexer
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Quick Start

### 1. Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker + Docker Compose (for Elasticsearch/Kibana)

### 2. Install dependencies

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY at minimum
```

### 4. Start infrastructure

```bash
docker-compose up elasticsearch kibana -d
# Wait ~30 seconds for Elasticsearch to be healthy
```

### 5. Run a local simulation (no GitHub needed)

```bash
python scripts/simulate_issue.py --domain pre-purchase
python scripts/simulate_issue.py --domain post-purchase --sample 1
```

### 6. Start the API server

```bash
uvicorn src.api.webhook:app --reload --port 8000
```

### 7. Trigger an investigation via HTTP

```bash
curl -X POST http://localhost:8000/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "issue_id": 101,
    "title": "Search returns empty results on category pages",
    "description": "After last nights Solr reindex, PLP shows no products. Affecting ~30% of users."
  }'
```

---

## GitHub Webhook Setup

1. Go to your repo → Settings → Webhooks → Add webhook
2. Payload URL: `https://your-server/webhook/github`
3. Content type: `application/json`
4. Secret: set `GITHUB_WEBHOOK_SECRET` in `.env`
5. Events: select **Issues** only

---

## Docker Compose (Full Stack)

```bash
# Start everything: app + Elasticsearch + Kibana
docker-compose up -d

# View logs
docker-compose logs -f aiis

# Import Kibana dashboards
bash kibana/setup.sh
```

Access:

- **API**: <http://localhost:8000>
- **Kibana**: <http://localhost:5601>
- **Elasticsearch**: <http://localhost:9200>

---

## Kibana Dashboards

After running `bash kibana/setup.sh`, navigate to Kibana → Dashboards:

| Dashboard | Description |
| --------- | ----------- |
| **AIIS Workflow Overview** | Total issues, running/completed/failed, avg investigation time |
| **AIIS Agent Performance** | Per-agent executions, duration, success rate, confidence |
| **AIIS MCP Tool Usage** | Tool call counts, latency, failures |
| **AIIS A2A Communication** | Request/response metrics, latency |
| **AIIS RAG Retrieval** | Searches, retrieval latency, top referenced docs |
| **AIIS Errors & Retries** | Error trends by agent and tool |

**Explore raw events:**

```bash
curl http://localhost:9200/aiis-events-*/_search?pretty | jq '.hits.hits[]._source | {event_type, agent, status, duration_ms, message}'
```

**Reconstruct timeline for a workflow:**

```bash
curl "http://localhost:9200/aiis-events-*/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"term": {"workflow_id": "YOUR-WORKFLOW-ID"}},
    "sort": [{"timestamp": "asc"}],
    "_source": ["timestamp", "event_type", "agent", "status", "message"]
  }'
```

---

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific suite
pytest tests/test_a2a.py -v
pytest tests/test_workflow.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

---

## A2A Message Contract

**Investigation Request** (Supervisor → Domain Agent):

```json
{
  "message_type": "InvestigationRequest",
  "trace_id": "3f8a2...",
  "workflow_id": "c7d1e...",
  "issue_id": 101,
  "title": "Search returns empty results",
  "description": "...",
  "assigned_domain": "pre-purchase",
  "timestamp": "2025-07-18T10:30:04Z"
}
```

**Investigation Result** (Domain Agent → Supervisor):

```json
{
  "message_type": "InvestigationResult",
  "trace_id": "3f8a2...",
  "workflow_id": "c7d1e...",
  "issue_id": 101,
  "status": "completed",
  "confidence": 0.91,
  "summary": "...",
  "root_cause": "...",
  "recommended_actions": ["..."],
  "evidence": [...],
  "iterations": 3,
  "duration_ms": 1240
}
```

---

## MCP Tools

| Category | Tool | Description |
| -------- | ---- | ----------- |
| **GitHub** | `assign_issue` | Assign issue to team members |
| **GitHub** | `add_labels` | Add labels to issue |
| **GitHub** | `add_comment` | Post investigation report |
| **GitHub** | `search_issues` | Find similar past issues |
| **Debugging** | `get_kibana_logs` | Fetch service error logs |
| **Debugging** | `get_dynatrace_traces` | Distributed trace analysis |
| **Debugging** | `execute_flexible_search` | SAP Commerce data queries |
| **Debugging** | `configuration_lookup` | Service configuration values |
| **Debugging** | `feature_flag_lookup` | Feature flag status |
| **Debugging** | `service_health` | Service health check |
| **Knowledge** | `search_knowledge_base` | RAG semantic search |
| **Knowledge** | `retrieve_runbook` | Get operational runbook |
| **Knowledge** | `retrieve_architecture_docs` | Component architecture docs |

---

## Observability Events

Every operation emits a structured event to Elasticsearch:

```json
{
  "timestamp": "2025-07-18T10:30:05Z",
  "trace_id": "3f8a2...",
  "span_id": "8b1c9...",
  "parent_span_id": "2e4f7...",
  "workflow_id": "c7d1e...",
  "issue_id": 101,
  "agent": "pre-purchase-agent",
  "event_type": "MCP_TOOL_CALL",
  "status": "SUCCESS",
  "duration_ms": 210,
  "message": "Calling MCP tool: get_kibana_logs",
  "metadata": {"tool": "get_kibana_logs", "service": "search-service"}
}
```

Event types: `WORKFLOW_STARTED`, `SUPERVISOR_DECISION`, `A2A_REQUEST`, `A2A_RESPONSE`, `MCP_TOOL_CALL`, `MCP_TOOL_COMPLETED`, `RAG_SEARCH`, `RAG_DOCUMENTS_RETRIEVED`, `INVESTIGATION_STARTED`, `INVESTIGATION_ITERATION`, `INVESTIGATION_FINISHED`, `GITHUB_UPDATED`, `WORKFLOW_COMPLETED`, and more.

---

## Extending the System

### Add a new domain agent

```python
# src/agents/domain/payments_agent.py
from src.a2a.messages import Domain
from src.a2a.server import A2AServer
from .base_agent import BaseDomainAgent

class PaymentsAgent(BaseDomainAgent):
    domain = Domain.PAYMENTS  # Add to Domain enum
    agent_id = "payments-agent"

    @property
    def service_areas(self) -> list[str]:
        return ["payment-processing", "fraud-detection", "billing"]

    @property
    def primary_services(self) -> list[str]:
        return ["payment-service", "fraud-service"]
```

### Add a new MCP tool

```python
# src/mcp_server/tools/custom_tools.py
async def my_new_tool(param: str) -> dict:
    return {"result": "..."}

# In src/mcp_server/server.py, call register_tool() with the tool definition
```

### Replace transport layer

Swap `InMemoryTransport` in `src/a2a/transport.py` with an HTTP, Kafka, or NATS implementation. The `A2AClient` and `A2AServer` interfaces remain unchanged.

### Replace vector database

Swap ChromaDB in `src/rag/` with FAISS, Pinecone, or Weaviate. Implement the same `search()` interface in `RAGRetriever`.

---

## Configuration Reference

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `ANTHROPIC_API_KEY` | — | Anthropic Claude API key (optional if using Ollama) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint (used when no Anthropic key) |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama model for local inference |
| `GITHUB_TOKEN` | — | GitHub API access (issues:write) |
| `GITHUB_REPO` | — | Target repo (`owner/repo`) |
| `GITHUB_WEBHOOK_SECRET` | — | HMAC secret for webhook verification |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch endpoint |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB storage path |
| `KNOWLEDGE_BASE_DIR` | `./knowledge-base` | Markdown documents root |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | Sentence Transformers model |
| `MAX_INVESTIGATION_ITERATIONS` | `4` | Max ReAct iterations per agent |
| `CONFIDENCE_THRESHOLD` | `0.75` | Stop investigation above this |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Technology Stack

| Layer | Technology |
| ----- | ---------- |
| Agent Framework | LangGraph + LangChain |
| LLM | Anthropic Claude or Ollama (llama3.1:8b) |
| API | FastAPI + Uvicorn |
| Vector DB | ChromaDB |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) |
| Observability | Elasticsearch 8.x + Kibana |
| GitHub Integration | GitHub REST API v3 |
| Package Manager | uv |
| Containerization | Docker Compose |
| Data Validation | Pydantic v2 |
