#!/usr/bin/env python3
"""
simulate_webhook.py — Send a signed GitHub webhook POST to the local AIIS server.

This is the recommended way to trigger AIIS in a local development environment.
It constructs a realistic GitHub `issues` event payload, signs it with
HMAC-SHA256 (same as GitHub does), and POSTs it to localhost:8000/webhook/github.
The full request path — signature verification, async workflow dispatch, GitHub
API calls, Kibana observability — is exercised exactly as in production.

Usage:
    # Use a built-in sample issue (default: pre-purchase)
    uv run python scripts/simulate_webhook.py

    # Choose domain
    uv run python scripts/simulate_webhook.py --domain post-purchase

    # Provide a custom issue
    uv run python scripts/simulate_webhook.py \\
        --issue-number 42 \\
        --title "Payment gateway timeout during checkout" \\
        --body "Customers are getting 504s when clicking 'Pay Now'..."

    # Target a different server
    uv run python scripts/simulate_webhook.py --server http://localhost:8000

Prerequisites:
    - AIIS server running: uv run uvicorn src.api.webhook:app --reload --port 8000
    - GITHUB_WEBHOOK_SECRET in .env (must match the server's value)
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

SAMPLE_ISSUES: dict[str, list[dict]] = {
    "pre-purchase": [
        {
            "number": 101,
            "title": "Search returns no results for 'Electronics' category",
            "body": (
                "When users search for 'Electronics' or any sub-category, the PLP returns "
                "an empty results page. This started after the Solr reindex ran last night. "
                "Checked the Solr admin console — index appears healthy but facets are not "
                "returning counts. Affects approximately 30% of search traffic."
            ),
        },
        {
            "number": 102,
            "title": "Cart prices not updating when applying promotion codes",
            "body": (
                "Customers report that entering a valid promo code at checkout does not "
                "change the cart total. The code is accepted (no error shown) but the "
                "discount is not applied. Likely related to the promotion engine deployment "
                "2 days ago. Priority: HIGH — 200+ complaints in the last hour."
            ),
        },
    ],
    "post-purchase": [
        {
            "number": 201,
            "title": "Orders stuck in 'Processing' — fulfillment pipeline not running",
            "body": (
                "Multiple customer orders placed this morning are stuck in 'Processing' and "
                "have not advanced to 'Confirmed'. The fulfillment service is timing out when "
                "calling the warehouse API. ~45 orders affected. Customers are calling support."
            ),
        },
        {
            "number": 202,
            "title": "Return confirmation emails not being sent",
            "body": (
                "Customers who submitted return requests in the last 4 hours have not received "
                "confirmation emails. Returns service shows requests as 'accepted' in DB, but "
                "the notification service queue is backed up — RabbitMQ shows 8,000+ pending."
            ),
        },
    ],
}


def _build_payload(number: int, title: str, body: str, repo: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "action": "opened",
        "issue": {
            "number": number,
            "title": title,
            "body": body,
            "state": "open",
            "created_at": now,
            "updated_at": now,
            "labels": [],
            "assignees": [],
            "user": {"login": "simulate-webhook-script", "type": "User"},
            "html_url": f"https://github.com/{repo}/issues/{number}",
        },
        "repository": {
            "full_name": repo,
            "name": repo.split("/")[-1] if "/" in repo else repo,
            "owner": {"login": repo.split("/")[0] if "/" in repo else "local"},
            "private": False,
        },
        "sender": {"login": "simulate-webhook-script"},
    }


def _sign(body_bytes: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body_bytes, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def _post(server: str, payload: dict, secret: str) -> dict:
    body_bytes = json.dumps(payload).encode()
    signature = _sign(body_bytes, secret) if secret else "sha256=unsigned"

    req = urllib.request.Request(
        f"{server.rstrip('/')}/webhook/github",
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Delivery": f"simulate-{int(time.time())}",
            "User-Agent": "GitHub-Hookshot/simulate",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a signed GitHub webhook to the local AIIS server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--server", default="http://localhost:8000", help="AIIS server base URL")
    parser.add_argument("--domain", choices=["pre-purchase", "post-purchase"], default="pre-purchase")
    parser.add_argument("--sample", type=int, default=0, help="Which built-in sample to use (0 or 1)")
    parser.add_argument("--issue-number", type=int, default=None)
    parser.add_argument("--title", default="")
    parser.add_argument("--body", default="")
    args = parser.parse_args()

    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    repo = os.getenv("GITHUB_REPO", "local/test-repo")

    if args.title:
        number = args.issue_number or 999
        title = args.title
        body = args.body or title
    else:
        samples = SAMPLE_ISSUES[args.domain]
        s = samples[args.sample % len(samples)]
        number, title, body = s["number"], s["title"], s["body"]

    payload = _build_payload(number, title, body, repo)

    print(f"\nAIIS Webhook Simulator")
    print(f"{'─'*60}")
    print(f"Server  : {args.server}")
    print(f"Issue   : #{number} — {title}")
    print(f"Signed  : {'yes (HMAC-SHA256)' if secret else 'no (GITHUB_WEBHOOK_SECRET not set)'}")
    print(f"{'─'*60}")

    try:
        result = _post(args.server, payload, secret)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        print(f"\nERROR {exc.code}: {detail}", file=sys.stderr)
        print("\nIs the AIIS server running?", file=sys.stderr)
        print("  uv run uvicorn src.api.webhook:app --reload --port 8000", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"\nCould not reach {args.server}: {exc.reason}", file=sys.stderr)
        print("  Is the AIIS server running?", file=sys.stderr)
        sys.exit(1)

    print(f"\nAccepted by AIIS:")
    print(f"  Status      : {result.get('status')}")
    print(f"  workflow_id : {result.get('workflow_id')}")
    print(f"  issue_id    : {result.get('issue_id')}")
    print(f"\nThe investigation is running in the background.")
    print(f"Check server logs for progress, then open Kibana to see trace data:")
    print(f"  http://localhost:5601")
    print()


if __name__ == "__main__":
    main()
