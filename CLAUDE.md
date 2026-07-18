# AIIS Project Instructions

## Documentation Currency Rule

**Any change to this project MUST be reflected in the `docs/` folder before the task is considered complete.**

This rule applies to all changes, including:

- New features, modules, or agents → add or update the relevant doc in `docs/modules/` or `docs/architecture/`
- New or modified API endpoints → update `docs/modules/webhook-api.md`
- New or modified MCP tools → update `docs/architecture/mcp-server.md`
- Changes to the LangGraph workflow (nodes, edges, state fields) → update `docs/architecture/langgraph-workflow.md`
- Changes to the A2A protocol (messages, transport, registry) → update `docs/architecture/a2a-protocol.md`
- Changes to the RAG system (indexer, retriever, knowledge base structure) → update `docs/architecture/rag-system.md`
- Changes to the observability layer (new event types, ES mappings) → update `docs/architecture/observability.md`
- New environment variables or configuration changes → update `docs/guides/configuration.md` and `.env.example`
- Changes to build, run, or test commands → update `docs/guides/build-and-run.md`
- Dependency changes (pyproject.toml) → update the relevant docs that reference those dependencies
- Any change that affects the architecture diagram → update `docs/architecture/overview.md` and `README.md`

### Documentation File Map

| Changed file / area | Docs to update |
| ------------------- | -------------- |
| `src/api/webhook.py` | `docs/modules/webhook-api.md`, `README.md` |
| `src/agents/supervisor/agent.py` | `docs/modules/supervisor-agent.md` |
| `src/agents/domain/` | `docs/modules/domain-agents.md` |
| `src/agents/state.py` | `docs/architecture/langgraph-workflow.md` |
| `src/workflow/graph.py` | `docs/architecture/langgraph-workflow.md`, `README.md` |
| `src/a2a/` | `docs/architecture/a2a-protocol.md` |
| `src/mcp_server/` | `docs/architecture/mcp-server.md`, `README.md` |
| `src/rag/` | `docs/architecture/rag-system.md` |
| `src/observability/` | `docs/architecture/observability.md` |
| `knowledge-base/` | `docs/architecture/rag-system.md` |
| `docker-compose.yml`, `Dockerfile` | `docs/guides/build-and-run.md` |
| `pyproject.toml` | `docs/guides/build-and-run.md` |
| `.env.example` | `docs/guides/configuration.md`, `README.md` |
| `.mcp.json` | `docs/guides/build-and-run.md`, `README.md` |
| `tests/browser/` | `docs/guides/build-and-run.md`, `README.md` |
| New module added | `docs/index.md`, `README.md` |

### Diagram Rule

All diagrams in any `.md` file (including `README.md` and all `docs/` files) must use **Mermaid syntax** (`\`\`\`mermaid`). Never use ASCII art, plain-text box-and-arrow diagrams, or Unicode drawing characters.
