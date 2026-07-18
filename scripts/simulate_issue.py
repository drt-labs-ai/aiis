#!/usr/bin/env python3
"""
Simulate a GitHub issue investigation without a real webhook.
Useful for local testing and demos.

Usage:
    python scripts/simulate_issue.py
    python scripts/simulate_issue.py --domain post-purchase
    python scripts/simulate_issue.py --issue-id 999 --title "Order stuck in processing"
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from src.observability.logger import configure_logging

configure_logging(os.getenv("LOG_LEVEL", "INFO"))


SAMPLE_ISSUES = {
    "pre-purchase": [
        {
            "issue_id": 101,
            "title": "Search returns no results for category 'Electronics'",
            "description": (
                "When users search for 'Electronics' or any sub-category, the PLP returns "
                "an empty results page. This started happening after the Solr reindex ran "
                "last night. Checked the Solr admin console and the index appears healthy "
                "but facets are not returning counts. Affects approximately 30% of users."
            ),
        },
        {
            "issue_id": 102,
            "title": "Cart prices not updating when applying promotion codes",
            "description": (
                "Customers are reporting that when they enter a valid promotion code at checkout, "
                "the cart total does not change. The code is accepted (no error shown) but the "
                "discount is not applied. Issue seems related to the new promotion engine "
                "deployment from 2 days ago. Priority: HIGH."
            ),
        },
    ],
    "post-purchase": [
        {
            "issue_id": 201,
            "title": "Orders stuck in 'Processing' status for 2+ hours",
            "description": (
                "Multiple customer orders placed this morning are stuck in 'Processing' state "
                "and have not moved to 'Confirmed'. The fulfillment service appears to be timing "
                "out when calling the warehouse API. Approximately 45 orders affected. "
                "Customers are calling support. Need urgent investigation."
            ),
        },
        {
            "issue_id": 202,
            "title": "Return confirmation emails not being sent",
            "description": (
                "Customers who submitted return requests in the last 4 hours have not received "
                "their return confirmation emails. The returns service shows the requests as "
                "'accepted' in the database, but the notification service queue appears backed up. "
                "RabbitMQ shows 8,000+ pending messages."
            ),
        },
    ],
}


async def run_simulation(issue_id: int, title: str, description: str):
    from src.agents.domain import create_pre_purchase_agent, create_post_purchase_agent
    from src.agents.state import WorkflowState
    from src.observability.elasticsearch_client import ensure_index_template
    from src.rag.indexer import index_knowledge_base
    from src.workflow.graph import get_workflow
    import uuid

    print(f"\n{'='*70}")
    print(f"AIIS - Agentic Issue Investigation System")
    print(f"{'='*70}")
    print(f"Issue #{issue_id}: {title}")
    print(f"{'='*70}\n")

    # Initialize agents
    print("Initializing domain agents...")
    create_pre_purchase_agent()
    create_post_purchase_agent()

    # Setup ES (non-fatal if unavailable)
    await ensure_index_template()

    # Index knowledge base
    print("Indexing knowledge base...")
    try:
        counts = index_knowledge_base(os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge-base"))
        for domain, count in counts.items():
            print(f"  {domain}: {count} chunks")
    except Exception as exc:
        print(f"  Warning: KB indexing failed ({exc}). Using fallback RAG.")

    # Build and run workflow
    print("\nStarting investigation workflow...\n")
    workflow = get_workflow()
    state = WorkflowState(
        issue_id=issue_id,
        title=title,
        description=description,
        workflow_id=str(uuid.uuid4()),
    )

    raw = await workflow.ainvoke(state)
    final_state = WorkflowState.model_validate(raw) if isinstance(raw, dict) else raw

    print(f"\n{'='*70}")
    print("INVESTIGATION COMPLETE")
    print(f"{'='*70}")
    print(f"Domain:     {final_state.assigned_domain}")
    print(f"Reason:     {final_state.routing_reason}")

    if final_state.investigation_result:
        r = final_state.investigation_result
        print(f"Confidence: {r.confidence:.0%}")
        print(f"Iterations: {r.iterations}")
        print(f"Duration:   {r.duration_ms}ms")
        print(f"\nSummary:\n{r.summary[:600]}")
        print(f"\nRoot Cause:\n{r.root_cause}")
        print(f"\nRecommended Actions:")
        for action in r.recommended_actions:
            print(f"  • {action}")

    print(f"\nGitHub Updated: {final_state.github_comment_posted}")
    print(f"Workflow ID:    {final_state.workflow_id}")
    print(f"Trace ID:       {final_state.trace_id}")
    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description="Simulate AIIS issue investigation")
    parser.add_argument("--issue-id", type=int, default=101)
    parser.add_argument("--title", type=str, default="")
    parser.add_argument("--description", type=str, default="")
    parser.add_argument("--domain", choices=["pre-purchase", "post-purchase"], default="pre-purchase")
    parser.add_argument("--sample", type=int, default=0, help="Use sample issue (0 or 1)")
    args = parser.parse_args()

    if args.title:
        issue_id = args.issue_id
        title = args.title
        description = args.description or title
    else:
        samples = SAMPLE_ISSUES.get(args.domain, SAMPLE_ISSUES["pre-purchase"])
        sample = samples[args.sample % len(samples)]
        issue_id = sample["issue_id"]
        title = sample["title"]
        description = sample["description"]

    asyncio.run(run_simulation(issue_id, title, description))


if __name__ == "__main__":
    main()
