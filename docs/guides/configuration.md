# Configuration Reference

This document is the complete reference for every environment variable AIIS supports. All variables are set in the `.env` file in the project root. AIIS reads this file automatically on startup.

---

## How Configuration Works

AIIS uses Python's `python-dotenv` library to load `.env` into environment variables at startup. The `.env` file is never committed to version control (it is in `.gitignore`) — each developer maintains their own.

To get started:

```bash
cp .env.example .env
# Edit .env with your values
```

Environment variables can also be set directly in your shell — shell values override `.env` values:

```bash
LOG_LEVEL=DEBUG uv run uvicorn src.api.webhook:app --reload
```

---

## Complete Variable Reference

### LLM Configuration

AIIS uses LLMs for two tasks:
- **Supervisor agent** — classifies which domain (pre/post-purchase) owns an issue
- **Domain agents** — synthesizes root-cause analysis and recommended actions from investigation evidence

Each task can use a different provider and model, enabling cost-optimised setups (e.g., cheap/fast model for routing, more capable model for synthesis).

---

#### `LLM_PROVIDER`

| Property | Value |
|---|---|
| **Default** | _(auto-detect from API keys)_ |
| **Required** | No |
| **Options** | `anthropic`, `openai`, `ollama` |
| **Example** | `ollama` |

The global default LLM provider for all agents. When not set, AIIS auto-detects: if `ANTHROPIC_API_KEY` is present it uses Anthropic; if `OPENAI_API_KEY` is present it uses OpenAI; otherwise it falls back to Ollama.

Per-agent overrides (`SUPERVISOR_LLM_PROVIDER`, `DOMAIN_AGENT_LLM_PROVIDER`) take precedence over this value.

---

#### `SUPERVISOR_LLM_PROVIDER` / `SUPERVISOR_LLM_MODEL`

| Property | Value |
|---|---|
| **Default** | Falls back to `LLM_PROVIDER` / provider default |
| **Required** | No |
| **Example** | `SUPERVISOR_LLM_PROVIDER=anthropic`, `SUPERVISOR_LLM_MODEL=claude-haiku-4-5-20251001` |

Provider and model used exclusively by the Supervisor agent for issue triage and domain routing. The supervisor task is straightforward classification — a smaller, faster model is usually sufficient.

---

#### `DOMAIN_AGENT_LLM_PROVIDER` / `DOMAIN_AGENT_LLM_MODEL`

| Property | Value |
|---|---|
| **Default** | Falls back to `LLM_PROVIDER` / provider default |
| **Required** | No |
| **Example** | `DOMAIN_AGENT_LLM_PROVIDER=openai`, `DOMAIN_AGENT_LLM_MODEL=gpt-4o` |

Provider and model used by domain investigation agents (pre-purchase, post-purchase) for synthesizing root-cause analysis reports. This task benefits from stronger reasoning — using a more capable model here improves investigation quality.

---

#### `ANTHROPIC_API_KEY`

| Property | Value |
|---|---|
| **Default** | _(empty)_ |
| **Required** | When any agent uses `provider=anthropic` |
| **Example** | `sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxx` |

Anthropic API key. Get yours at [console.anthropic.com](https://console.anthropic.com).

---

#### `ANTHROPIC_MODEL`

| Property | Value |
|---|---|
| **Default** | `claude-haiku-4-5-20251001` |
| **Required** | No |
| **Example** | `claude-sonnet-5`, `claude-opus-4-8` |

Default Anthropic model when `provider=anthropic` and no per-agent model override is set. Haiku is the recommended default — fast and cost-efficient for triage; use Sonnet or Opus for higher investigation quality.

---

#### `OPENAI_API_KEY`

| Property | Value |
|---|---|
| **Default** | _(empty)_ |
| **Required** | When any agent uses `provider=openai` |
| **Example** | `sk-proj-xxxx...` |

OpenAI API key. Also used as the `api_key` for any OpenAI-compatible endpoint (vLLM, Azure OpenAI, LM Studio).

---

#### `OPENAI_BASE_URL`

| Property | Value |
|---|---|
| **Default** | _(OpenAI cloud)_ |
| **Required** | No |
| **Example** | `http://192.168.1.50:8000/v1` |

Override the OpenAI API base URL to point at any OpenAI-compatible server:

| Environment | Value |
|---|---|
| OpenAI cloud | _(leave blank)_ |
| vLLM on OpenStack VM | `http://<vm-ip>:8000/v1` |
| Azure OpenAI | `https://<resource>.openai.azure.com` |
| LM Studio (local) | `http://localhost:1234/v1` |

---

#### `OPENAI_MODEL`

| Property | Value |
|---|---|
| **Default** | `gpt-4o-mini` |
| **Required** | No |
| **Example** | `gpt-4o`, `meta-llama/Llama-3.1-8B-Instruct` |

Default model when `provider=openai`. For vLLM endpoints, set this to the model ID served by vLLM (e.g., `meta-llama/Llama-3.1-8B-Instruct`).

---

#### `OLLAMA_BASE_URL`

| Property | Value |
|---|---|
| **Default** | `http://localhost:11434` |
| **Required** | No |
| **Example** | `http://192.168.1.100:11434` |

Ollama server endpoint. Change this when Ollama runs on a GPU VM rather than localhost.

---

#### `OLLAMA_MODEL`

| Property | Value |
|---|---|
| **Default** | `llama3.1:8b` |
| **Required** | No |
| **Example** | `llama3.2:3b`, `qwen2.5:14b`, `mistral:7b` |

Default Ollama model. Must be pulled first: `ollama pull llama3.1:8b`.

---

### GitHub Integration

These variables enable AIIS to receive GitHub webhooks and post investigation results as issue comments.

---

#### `GITHUB_TOKEN`

| Property | Value |
|---|---|
| **Default** | _(empty)_ |
| **Required** | Yes, for webhook and comment features |
| **Example** | `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |

A GitHub Personal Access Token (PAT) with the following permissions:

- `repo` → `issues` → Read and write (to post investigation comments)
- `repo` → Read (to read issue details)

Create one at **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**.

---

#### `GITHUB_REPO`

| Property | Value |
|---|---|
| **Default** | _(empty)_ |
| **Required** | Yes, for webhook features |
| **Example** | `myorg/myrepo`, `alice/ecommerce-platform` |

The GitHub repository that AIIS monitors and comments on. Format is `owner/repo`.

AIIS uses this to:
- Fetch issue details via the GitHub API during investigations
- Post investigation results as comments on the triggering issue

---

#### `GITHUB_WEBHOOK_SECRET`

| Property | Value |
|---|---|
| **Default** | _(empty)_ |
| **Required** | Strongly recommended |
| **Example** | `my-long-random-secret-string-abc123xyz` |

A shared secret used to verify that webhook payloads genuinely come from GitHub. GitHub signs each payload with this secret using HMAC-SHA256, and AIIS verifies the signature before processing the payload.

If this is empty, AIIS skips signature verification and accepts any payload — fine for local development, but a security risk in production.

**How to generate a good secret:**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Set the same value in both `.env` and the GitHub webhook configuration.

---

### Elasticsearch

---

#### `ELASTICSEARCH_URL`

| Property | Value |
|---|---|
| **Default** | `http://localhost:9200` |
| **Required** | No |
| **Example** | `http://my-es-server:9200`, `https://my-cloud.es.io:9243` |

The HTTP endpoint for Elasticsearch. AIIS writes one event document per investigation step (routing, tool calls, results) to a daily index named `aiis-events-YYYY.MM.DD`.

**Non-fatal:** If Elasticsearch is unreachable, AIIS logs a warning at startup and continues operating. Events are silently dropped. Investigation results are still returned to the caller.

---

### ChromaDB / RAG

ChromaDB stores the vector embeddings of your knowledge base documents. Agents search these embeddings to retrieve relevant context during investigations.

---

#### `CHROMA_PERSIST_DIR`

| Property | Value |
|---|---|
| **Default** | `./data/chroma` |
| **Required** | No |
| **Example** | `/var/lib/aiis/chroma`, `./my-chroma-data` |

The directory where ChromaDB stores its vector index on disk. This directory is created automatically if it does not exist.

To reset the knowledge base index (for example, after changing `EMBED_MODEL`):

```bash
rm -rf data/chroma
uv run python scripts/index_kb.py
```

---

#### `EMBED_MODEL`

| Property | Value |
|---|---|
| **Default** | `all-MiniLM-L6-v2` |
| **Required** | No |
| **Example** | `all-mpnet-base-v2`, `paraphrase-multilingual-MiniLM-L12-v2` |

The [Sentence Transformers](https://www.sbert.net/docs/pretrained_models.html) model used to convert text into embedding vectors for storage in ChromaDB and for query-time retrieval.

The default `all-MiniLM-L6-v2` is a good trade-off: fast, small (22M parameters), and accurate enough for most knowledge bases.

**Important:** If you change this value, you must delete `CHROMA_PERSIST_DIR` and re-run the indexer. Embeddings from different models are incompatible.

---

#### `KNOWLEDGE_BASE_DIR`

| Property | Value |
|---|---|
| **Default** | `./knowledge-base` |
| **Required** | No |
| **Example** | `./docs/runbooks`, `/shared/team-knowledge` |

Path to the directory containing your Markdown knowledge base files. All `.md` files in this directory (and subdirectories) are indexed by the RAG system.

Add your own documents here to improve investigation quality:
- Architecture decision records
- Runbooks and incident post-mortems
- Service dependency maps
- Known issue patterns
- Deployment guides

---

### Agent Tuning

These variables control the balance between investigation thoroughness and speed.

---

#### `MAX_INVESTIGATION_ITERATIONS`

| Property | Value |
|---|---|
| **Default** | `4` |
| **Required** | No |
| **Range** | `1` – `10` (recommended) |
| **Example** | `2`, `6` |

The maximum number of RAG-search + MCP-tool cycles a domain agent runs per investigation. After this many iterations, the agent finalizes its result regardless of confidence.

Each iteration consists of:
1. Searching the knowledge base with the current hypothesis
2. Calling one or more MCP tools (GitHub API, Elasticsearch, etc.)
3. Updating the confidence score and root-cause hypothesis

**Higher values** → more thorough investigation, longer runtime
**Lower values** → faster response, may miss edge cases

---

#### `CONFIDENCE_THRESHOLD`

| Property | Value |
|---|---|
| **Default** | `0.75` |
| **Required** | No |
| **Range** | `0.0` – `1.0` |
| **Example** | `0.5`, `0.9` |

The minimum confidence score at which an agent stops iterating early. If the agent reaches this confidence before hitting `MAX_INVESTIGATION_ITERATIONS`, it stops and returns the result immediately.

Think of it as "how sure does the agent need to be before it stops searching?"

**0.5** → Agent stops when it has a plausible explanation (fast, less thorough)
**0.75** → Default — good balance for most scenarios
**0.9** → Agent must be very confident before stopping (slow, very thorough)

---

### Logging

---

#### `LOG_LEVEL`

| Property | Value |
|---|---|
| **Default** | `INFO` |
| **Required** | No |
| **Options** | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| **Example** | `DEBUG` |

Controls the verbosity of AIIS log output. See the [Debugging Guide](debugging.md) for details on what each level reveals.

---

## Complete Variable Table

| Variable | Default | Required | Description | Example |
|---|---|---|---|---|
| `LLM_PROVIDER` | _(auto)_ | No | Global default provider: `anthropic`, `openai`, `ollama` | `openai` |
| `SUPERVISOR_LLM_PROVIDER` | `LLM_PROVIDER` | No | Provider override for supervisor agent | `anthropic` |
| `SUPERVISOR_LLM_MODEL` | provider default | No | Model override for supervisor agent | `claude-haiku-4-5-20251001` |
| `DOMAIN_AGENT_LLM_PROVIDER` | `LLM_PROVIDER` | No | Provider override for domain agents | `openai` |
| `DOMAIN_AGENT_LLM_MODEL` | provider default | No | Model override for domain agents | `gpt-4o` |
| `ANTHROPIC_API_KEY` | _(empty)_ | When provider=anthropic | Anthropic API key | `sk-ant-api03-...` |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5-20251001` | No | Default Anthropic model | `claude-sonnet-5` |
| `OPENAI_API_KEY` | _(empty)_ | When provider=openai | OpenAI or compatible API key | `sk-proj-...` |
| `OPENAI_BASE_URL` | _(OpenAI cloud)_ | No | Custom endpoint for vLLM / Azure / OpenStack | `http://vm-ip:8000/v1` |
| `OPENAI_MODEL` | `gpt-4o-mini` | No | Default OpenAI / vLLM model | `meta-llama/Llama-3.1-8B` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | No | Ollama server URL | `http://gpu-vm:11434` |
| `OLLAMA_MODEL` | `llama3.1:8b` | No | Ollama model name | `qwen2.5:14b` |
| `GITHUB_TOKEN` | _(empty)_ | For GitHub | PAT with issues:write | `ghp_xxxx...` |
| `GITHUB_REPO` | _(empty)_ | For GitHub | Target repo | `myorg/myrepo` |
| `GITHUB_WEBHOOK_SECRET` | _(empty)_ | Recommended | HMAC secret for payload verification | `my-random-secret` |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | No | Elasticsearch endpoint | `http://es-server:9200` |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | No | ChromaDB storage path | `/var/lib/aiis/chroma` |
| `EMBED_MODEL` | `all-MiniLM-L6-v2` | No | Sentence transformer model | `all-mpnet-base-v2` |
| `KNOWLEDGE_BASE_DIR` | `./knowledge-base` | No | Path to knowledge base Markdown files | `./docs/runbooks` |
| `MAX_INVESTIGATION_ITERATIONS` | `4` | No | Max RAG+tool cycles per investigation | `6` |
| `CONFIDENCE_THRESHOLD` | `0.75` | No | Confidence to stop iterating early | `0.9` |
| `LOG_LEVEL` | `INFO` | No | Python log level | `DEBUG` |

---

## Choosing an LLM Setup

AIIS supports three providers. Each agent role (supervisor, domain agents) can use a different provider, enabling cost-optimised setups.

| Dimension | Anthropic Claude | OpenAI / vLLM | Ollama |
|---|---|---|---|
| **Cost** | Paid (~$0.25–15 / 1M tokens) | Paid cloud or free self-hosted | Free — runs on your hardware |
| **Latency** | 2–8 s per cycle | 1–10 s (cloud); 5–30 s (self-hosted) | 5–30 s (depends on hardware) |
| **Output quality** | Excellent | Excellent (GPT-4o) to Good (mini) | Good — sufficient for most |
| **Privacy** | Text sent to Anthropic | Text sent to OpenAI or stays local | Fully local |
| **OpenStack / on-prem** | No (cloud only) | Yes — vLLM serves OpenAI-compatible API | Yes — run on GPU VM |
| **Best for** | Cloud prod, highest quality | Cloud prod or OpenStack with vLLM | Local dev, air-gapped |

### Common `.env` Configurations

**Local development (Ollama):**

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

**Cloud production (Anthropic for supervisor, OpenAI for deeper analysis):**

```bash
SUPERVISOR_LLM_PROVIDER=anthropic
SUPERVISOR_LLM_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...

DOMAIN_AGENT_LLM_PROVIDER=openai
DOMAIN_AGENT_LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-proj-...
```

**OpenStack with vLLM on a GPU VM:**

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=not-required-but-must-be-set   # vLLM accepts any string
OPENAI_BASE_URL=http://192.168.100.50:8000/v1  # your vLLM VM
OPENAI_MODEL=meta-llama/Llama-3.1-8B-Instruct
```

**Hybrid — fast cloud routing, local analysis:**

```bash
SUPERVISOR_LLM_PROVIDER=anthropic
SUPERVISOR_LLM_MODEL=claude-haiku-4-5-20251001
ANTHROPIC_API_KEY=sk-ant-...

DOMAIN_AGENT_LLM_PROVIDER=ollama
DOMAIN_AGENT_LLM_MODEL=qwen2.5:14b
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Tuning Investigation Quality

The two agent tuning variables give you direct control over the quality-versus-speed trade-off.

```mermaid
quadrantChart
    title Investigation Quality vs Speed
    x-axis Fast --> Slow
    y-axis Low Quality --> High Quality
    quadrant-1 High Quality, Slow
    quadrant-2 High Quality, Fast
    quadrant-3 Low Quality, Fast
    quadrant-4 Low Quality, Slow
    CONFIDENCE_THRESHOLD=0.5 MAX_ITER=2: [0.15, 0.25]
    Default 0.75 / 4 iterations: [0.45, 0.55]
    CONFIDENCE_THRESHOLD=0.9 MAX_ITER=4: [0.65, 0.75]
    CONFIDENCE_THRESHOLD=0.9 MAX_ITER=8: [0.85, 0.85]
```

### Tuning Recommendations

**For fastest response time** — Reduce both settings:

```bash
MAX_INVESTIGATION_ITERATIONS=2
CONFIDENCE_THRESHOLD=0.5
```

The agent will stop as soon as it has a plausible answer. Good for high-volume, low-stakes scenarios.

---

**For most thorough investigation** — Increase both settings:

```bash
MAX_INVESTIGATION_ITERATIONS=6
CONFIDENCE_THRESHOLD=0.9
```

The agent runs more cycles and only stops when it is very confident. Good for critical production issues where thoroughness matters more than speed.

---

**For improving RAG quality** — Improve the knowledge base:

The single biggest lever for improving investigation quality is **the quality of your knowledge base documents**. The LLM and RAG settings are secondary.

High-quality knowledge base documents:
- Describe specific failure modes and their root causes
- Include past incident post-mortems with timeline and resolution
- Explain service dependencies and common failure patterns
- Reference specific service names, queue names, and job names that appear in issue descriptions

Low-quality documents (vague architecture overviews) produce generic, low-confidence results regardless of LLM or iteration settings.

---

## Configuration Validation

AIIS validates its configuration on startup and logs warnings for any issues it detects:

| Condition | Behaviour |
|---|---|
| No LLM configured (no API key, Ollama unreachable) | Falls back to keyword classification; warns at startup |
| `CONFIDENCE_THRESHOLD` outside 0.0–1.0 | Uses default (0.75); logs warning |
| `MAX_INVESTIGATION_ITERATIONS` < 1 | Uses minimum (1); logs warning |
| `KNOWLEDGE_BASE_DIR` does not exist | Uses empty knowledge base; warns at startup |
| `ELASTICSEARCH_URL` unreachable | Disables event logging; non-fatal warning |
| `GITHUB_TOKEN` missing | Disables GitHub commenting; non-fatal warning |

---

## Example `.env` Files

### Minimal — Local Development with Ollama

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
LOG_LEVEL=DEBUG
```

### Full Setup — Anthropic + GitHub + Elasticsearch

```bash
# LLM
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# GitHub
GITHUB_TOKEN=ghp_your-pat-here
GITHUB_REPO=myorg/myrepo
GITHUB_WEBHOOK_SECRET=a64-char-random-hex-string-here

# Storage (defaults are fine for local)
ELASTICSEARCH_URL=http://localhost:9200
CHROMA_PERSIST_DIR=./data/chroma
KNOWLEDGE_BASE_DIR=./knowledge-base

# Tuning
MAX_INVESTIGATION_ITERATIONS=4
CONFIDENCE_THRESHOLD=0.75

# Logging
LOG_LEVEL=INFO
```

### Privacy-Focused — Fully Local, No External Services

```bash
# Free, local LLM
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Local storage only
CHROMA_PERSIST_DIR=./data/chroma
KNOWLEDGE_BASE_DIR=./knowledge-base

# Disable external integrations
GITHUB_TOKEN=
GITHUB_REPO=
GITHUB_WEBHOOK_SECRET=
ELASTICSEARCH_URL=http://localhost:9200

LOG_LEVEL=INFO
```
