# Supervisor Agent

**File:** `src/agents/supervisor/agent.py`

---

## What Is the Supervisor Agent?

Think of the Supervisor Agent as the **receptionist** of the AIIS system. When a new GitHub issue arrives, the Supervisor reads it and decides: "Is this a pre-purchase problem (search, cart, pricing) or a post-purchase problem (orders, shipping, returns)?" It then hands the issue off to the right specialist team.

> **Key principle:** The Supervisor **never investigates** an issue itself. Its only jobs are to **classify** (triage) and **delegate** (hand off).

---

## Two-Phase Operation

The Supervisor works in exactly two phases:

| Phase | Method | What It Does |
|-------|--------|--------------|
| Phase 1 | `triage(state)` | Reads the issue, decides which domain owns it, applies GitHub labels and assignees |
| Phase 2 | `delegate(state)` | Sends the classified issue to the appropriate domain agent and waits for the result |

```mermaid
flowchart LR
    A[New GitHub Issue] --> B[Phase 1: triage]
    B --> C[Phase 2: delegate]
    C --> D[Domain Agent handles investigation]
```

---

## How the Supervisor Chooses an LLM

Before the Supervisor can classify anything, it needs to pick a language model (LLM) to reason with. The `_get_llm()` method tries options in order:

```mermaid
flowchart TD
    A[_get_llm called] --> B{ANTHROPIC_API_KEY\nenv var set?}
    B -- Yes --> C[Use Anthropic Claude\nclaude-haiku-4-5-20251001]
    B -- No --> D{OLLAMA_BASE_URL\nor OLLAMA_MODEL set?}
    D -- Yes --> E[Use Ollama\ndefault: llama3.1:8b]
    D -- No --> F[Return None\nfallback to keyword matching]
    C --> G[LLM Ready]
    E --> G
    F --> H[No LLM — use keywords only]
```

**Environment variables that control this:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | _(none)_ | Enables Anthropic Claude |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL for local Ollama server |
| `OLLAMA_MODEL` | `llama3.1:8b` | Which Ollama model to use |

---

## Classification: How the Supervisor Decides Which Domain Owns the Issue

Classification is the heart of the Supervisor. It happens in `triage()` through a two-level hierarchy.

### Level 1 — LLM-Based Classification (`_llm_classify`)

When an LLM is available, the Supervisor sends the issue title and description to the model with a special system prompt (`SUPERVISOR_SYSTEM_PROMPT`). This prompt instructs the LLM to respond with a structured JSON object.

**What the LLM returns:**

```json
{
  "domain": "pre_purchase",
  "reasoning": "The issue mentions the search results page returning wrong prices for filtered products.",
  "confidence": 0.92,
  "suggested_labels": ["pre-purchase", "search", "pricing"],
  "suggested_assignees": ["search-team-lead"]
}
```

| JSON Field | Type | Meaning |
|------------|------|---------|
| `domain` | string | Either `"pre_purchase"` or `"post_purchase"` |
| `reasoning` | string | The LLM's explanation for its decision |
| `confidence` | float (0–1) | How certain the LLM is (1.0 = 100% certain) |
| `suggested_labels` | list | GitHub labels to apply to the issue |
| `suggested_assignees` | list | GitHub usernames to assign to the issue |

### Level 2 — Keyword Fallback (`_keyword_classify`)

If no LLM is available, or if the LLM call fails, the Supervisor falls back to simple keyword matching. It scores the issue text against two keyword lists:

**Pre-Purchase Keywords** (things that happen *before* buying):

> `search`, `plp`, `pdp`, `price`, `pricing`, `promotion`, `cart`, `checkout`, `availability`, `product`, `catalog`, `facet`, `filter`, `add to cart`, `stock`, `inventory`, `browse`

**Post-Purchase Keywords** (things that happen *after* buying):

> `order`, `fulfillment`, `shipping`, `delivery`, `return`, `refund`, `notification`, `email`, `tracking`, `cancel`, `invoice`, `receipt`, `payment failed`, `dispatch`, `warehouse`

The domain whose keywords appear more often in the issue text wins. Confidence is determined by how many keyword matches were found.

---

## Classification Decision Flowchart

```mermaid
flowchart TD
    A[Issue title + description] --> B{LLM available?}

    B -- Yes --> C[Send to LLM with SUPERVISOR_SYSTEM_PROMPT]
    C --> D{LLM returns\nvalid JSON?}
    D -- Yes --> E[Extract domain, confidence,\nlabels, assignees from JSON]
    D -- No / Error --> F[Fall through to keyword matching]

    B -- No --> F

    F --> G[Count PRE_PURCHASE keyword hits]
    F --> H[Count POST_PURCHASE keyword hits]
    G --> I{Which count\nis higher?}
    H --> I
    I -- Pre-purchase\nhas more hits --> J[domain = pre_purchase\nconfidence = f keyword count]
    I -- Post-purchase\nhas more hits --> K[domain = post_purchase\nconfidence = f keyword count]
    I -- Tie or zero --> L[domain = pre_purchase\ndefault fallback\nlow confidence]

    E --> M[Classification result]
    J --> M
    K --> M
    L --> M
```

---

## Phase 1: `triage()` — Step by Step

```mermaid
sequenceDiagram
    participant GW as GitHub Webhook
    participant SV as Supervisor Agent
    participant ES as Elasticsearch
    participant CL as LLM / Keywords
    participant GH as GitHub MCP Tools

    GW->>SV: issue arrives in state
    SV->>ES: emit SUPERVISOR_DECISION STARTED event
    SV->>CL: _llm_classify(title, description)
    alt LLM succeeds
        CL-->>SV: JSON with domain, confidence, labels, assignees
    else LLM unavailable or fails
        SV->>CL: _keyword_classify(title, description)
        CL-->>SV: domain, confidence from keyword scores
    end
    SV->>SV: set state.assigned_domain
    SV->>SV: set state.routing_reason
    SV->>SV: set state.applied_labels
    SV->>SV: set state.assignees
    SV->>GH: add_labels(issue_id, labels)
    SV->>GH: assign_issue(issue_id, assignees)
    SV->>ES: emit SUPERVISOR_DECISION SUCCESS event with duration
```

**State fields updated by `triage()`:**

| Field | What Gets Set |
|-------|--------------|
| `state.assigned_domain` | `Domain.PRE_PURCHASE` or `Domain.POST_PURCHASE` |
| `state.routing_reason` | Human-readable explanation of the classification |
| `state.applied_labels` | List of GitHub labels that were applied |
| `state.assignees` | List of GitHub usernames that were assigned |

---

## Phase 2: `delegate()` — Step by Step

Once triage is complete, `delegate()` hands the classified issue to the correct domain agent using the **Agent-to-Agent (A2A)** protocol.

```mermaid
sequenceDiagram
    participant SV as Supervisor Agent
    participant ES as Elasticsearch
    participant A2A as A2A Client
    participant DA as Domain Agent\n(Pre or Post Purchase)

    SV->>SV: build InvestigationRequest from state
    SV->>ES: emit A2A_REQUEST SENT event
    SV->>A2A: send_investigation_request(request)
    A2A->>DA: forward investigation request
    DA->>DA: run ReAct investigation loop
    DA-->>A2A: return investigation result
    A2A-->>SV: return investigation result
    SV->>SV: store result in state.investigation_result
    SV->>ES: emit A2A_RESPONSE RECEIVED event
```

**What `InvestigationRequest` contains:**

```python
InvestigationRequest(
    issue_id=state.issue_id,
    title=state.title,
    description=state.description,
    domain=state.assigned_domain,
    labels=state.applied_labels
)
```

---

## Full Supervisor Flow (Combined View)

```mermaid
sequenceDiagram
    participant GW as GitHub Webhook
    participant SV as Supervisor Agent
    participant ES as Elasticsearch
    participant LLM as LLM / Keyword Classifier
    participant GH as GitHub MCP
    participant A2A as A2A Client
    participant DA as Domain Agent

    GW->>SV: New issue event hits system
    Note over SV: ── PHASE 1: TRIAGE ──
    SV->>ES: SUPERVISOR_DECISION STARTED
    SV->>LLM: classify(title, description)
    LLM-->>SV: domain + reasoning + labels + assignees
    SV->>GH: add_labels()
    SV->>GH: assign_issue()
    SV->>ES: SUPERVISOR_DECISION SUCCESS
    Note over SV: ── PHASE 2: DELEGATE ──
    SV->>ES: A2A_REQUEST SENT
    SV->>A2A: send_investigation_request()
    A2A->>DA: forward to correct domain agent
    DA-->>A2A: investigation result
    A2A-->>SV: investigation result
    SV->>SV: state.investigation_result = result
    SV->>ES: A2A_RESPONSE RECEIVED
```

---

## Observability: Elasticsearch Events

Every significant action emits a structured event to Elasticsearch so the system can be monitored:

| Event Name | When Emitted |
|------------|--------------|
| `SUPERVISOR_DECISION STARTED` | At the beginning of `triage()` |
| `SUPERVISOR_DECISION SUCCESS` | At the end of `triage()`, includes duration |
| `A2A_REQUEST SENT` | When `delegate()` sends to a domain agent |
| `A2A_RESPONSE RECEIVED` | When `delegate()` gets the result back |

---

## Configuration Reference

| Environment Variable | Default | Effect |
|---------------------|---------|--------|
| `ANTHROPIC_API_KEY` | _(unset)_ | Enables Anthropic Claude as the classifier LLM |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL for Ollama local LLM server |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama model name to use |
| `GITHUB_WEBHOOK_SECRET` | _(unset)_ | Used upstream for webhook validation |

---

## Beginner's Summary

1. A GitHub issue comes in.
2. The Supervisor tries to use an LLM (Claude or Ollama) to read and classify the issue.
3. If no LLM is available, it counts keywords from two lists (pre-purchase vs post-purchase).
4. It applies labels and assigns people on GitHub.
5. It sends the classified issue to the correct specialist agent (Pre-Purchase or Post-Purchase).
6. It records every step in Elasticsearch for monitoring.
7. It waits for the specialist agent to finish and stores the result.

The Supervisor never digs into logs, traces, or runbooks. That is the domain agent's job.
