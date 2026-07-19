# AIIS Documentation

Welcome to the documentation for the **Agentic Issue Investigation System (AIIS)** — a multi-agent AI system that automatically investigates GitHub issues, classifies them by domain, and produces structured root-cause analysis reports.

AIIS is built as a proof-of-concept using [LangGraph](https://langchain-ai.github.io/langgraph/) for multi-agent orchestration, the Agent-to-Agent (A2A) protocol for inter-agent communication, and the Model Context Protocol (MCP) for tool integration.

---

## What Does AIIS Do?

When a GitHub issue is opened, AIIS:

1. **Receives** the issue via webhook (or the `/investigate` API endpoint)
2. **Classifies** it as a pre-purchase or post-purchase problem using an LLM-powered supervisor agent
3. **Delegates** to a specialist domain agent via the A2A protocol
4. **Investigates** using Retrieval-Augmented Generation (RAG) over a knowledge base and MCP tool calls to GitHub and Elasticsearch
5. **Reports** a structured result with root cause, confidence score, and recommended actions — posted as a GitHub issue comment

---

## Quick Navigation

| Document | Audience | What You Will Learn |
|---|---|---|
| [Getting Started](guides/getting-started.md) | New users | Install prerequisites, configure, and run AIIS in 5 steps |
| [Build and Run](guides/build-and-run.md) | Developers | Daily development workflow, Docker, tests, and webhook setup |
| [Deployment](guides/deployment.md) | Operators | Deploy to Local, OpenStack, and AWS with build steps for each |
| [Configuration Reference](guides/configuration.md) | All operators | Every environment variable, LLM providers, per-agent model config |
| [Debugging](guides/debugging.md) | Everyone | Diagnose problems, read logs, query Elasticsearch traces |

### Architecture and Module References

| Document | What It Covers |
|---|---|
| [docs/architecture/](architecture/) | System design, data flow, and component relationships |
| [docs/modules/](modules/) | Per-module API and design references |

---

## Technology Stack

| Layer | Technology | Role |
|---|---|---|
| **API** | FastAPI + Uvicorn | HTTP server, webhook receiver, REST endpoints |
| **Orchestration** | LangGraph | Multi-agent state machine and workflow |
| **Agent Protocol** | A2A (Agent-to-Agent) | Structured inter-agent communication |
| **Tool Protocol** | MCP (Model Context Protocol) | Standardized tool definitions for agents |
| **LLM** | Anthropic Claude or Ollama | Language model for reasoning and classification |
| **RAG** | ChromaDB + Sentence Transformers | Vector search over knowledge base documents |
| **Event Bus** | Kafka (KRaft) | Mandatory event pipeline — all observability events published here |
| **Event Store** | Elasticsearch | Storage layer — Kafka consumer writes complete payloads here |
| **Analytics** | Kibana | Dashboard and visualization for investigation data |
| **Package Manager** | uv | Python dependency management and virtual environment |
| **Containers** | Docker Compose | Local orchestration of Kafka, Elasticsearch, and Kibana |

---

> **New to AIIS?** Start with the [Getting Started Guide](guides/getting-started.md). It covers everything from installing prerequisites to getting your first investigation result, step by step.
