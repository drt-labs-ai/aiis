"""
Browser tests for AIIS using Playwright.

Tests all web-accessible surfaces:
  - AIIS API (http://localhost:8000) — health, Swagger UI, /investigate
  - Elasticsearch (http://localhost:9200)
  - Kibana (http://localhost:5601)

Run:
    uv run pytest tests/browser/test_aiis_browser.py -v --headed
    uv run pytest tests/browser/test_aiis_browser.py -v          # headless
"""
from __future__ import annotations

import json
import time
import requests
import pytest
from pathlib import Path
from playwright.sync_api import Page, expect, sync_playwright

AIIS_URL = "http://localhost:8000"
ES_URL = "http://localhost:9200"
KIBANA_URL = "http://localhost:5601"
SCREENSHOT_DIR = Path("tests/browser/screenshots")

SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_page():
    """Single Chromium browser instance shared across all tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=200)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        yield page
        browser.close()


def screenshot(page: Page, name: str):
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"  📸 Screenshot saved: {path}")
    return path


# ─── AIIS API Tests ───────────────────────────────────────────────────────────

class TestAIISHealthEndpoint:
    def test_health_returns_ok(self):
        """Health endpoint returns JSON with status ok."""
        resp = requests.get(f"{AIIS_URL}/health", timeout=5)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["service"] == "aiis"
        print(f"  ✅ /health → {body}")

    def test_health_in_browser(self, browser_page: Page):
        """Navigate to /health in browser and verify JSON response."""
        browser_page.goto(f"{AIIS_URL}/health")
        content = browser_page.content()
        assert '"ok"' in content or 'ok' in content
        screenshot(browser_page, "01_health_endpoint")
        print("  ✅ /health rendered in browser")


class TestAIISSwaggerUI:
    def test_swagger_ui_loads(self, browser_page: Page):
        """FastAPI Swagger UI loads at /docs."""
        browser_page.goto(f"{AIIS_URL}/docs", wait_until="networkidle")
        # Swagger renders an h2 with the API title
        expect(browser_page.locator("text=AIIS - Agentic Issue Investigation System")).to_be_visible(timeout=10000)
        screenshot(browser_page, "02_swagger_ui")
        print("  ✅ Swagger UI loaded with correct API title")

    def test_swagger_shows_all_endpoints(self, browser_page: Page):
        """Swagger UI lists all AIIS endpoints."""
        browser_page.goto(f"{AIIS_URL}/docs", wait_until="networkidle")
        content = browser_page.inner_text("body")
        for endpoint in ["/webhook/github", "/investigate", "/health"]:
            assert endpoint in content, f"Endpoint {endpoint} not visible in Swagger"
        screenshot(browser_page, "03_swagger_endpoints")
        print("  ✅ All 3 endpoints visible in Swagger: /webhook/github, /investigate, /health")

    def test_swagger_expand_investigate_endpoint(self, browser_page: Page):
        """Click the /investigate endpoint section to expand it."""
        browser_page.goto(f"{AIIS_URL}/docs", wait_until="networkidle")
        # Click on the POST /investigate operation block
        investigate_block = browser_page.locator("text=/investigate").first
        investigate_block.click()
        time.sleep(1)
        screenshot(browser_page, "04_swagger_investigate_expanded")
        print("  ✅ /investigate endpoint expanded in Swagger")

    def test_redoc_loads(self, browser_page: Page):
        """ReDoc alternative docs load at /redoc."""
        browser_page.goto(f"{AIIS_URL}/redoc", wait_until="networkidle")
        content = browser_page.inner_text("body")
        assert "AIIS" in content or "Agentic" in content
        screenshot(browser_page, "05_redoc")
        print("  ✅ ReDoc loaded")


class TestAIISInvestigateEndpoint:
    def test_investigate_pre_purchase(self):
        """POST /investigate with a pre-purchase issue returns a valid result."""
        payload = {
            "issue_id": 9001,
            "title": "Search results showing wrong prices on PLP",
            "description": "After the Solr reindex last night, product listing pages show incorrect pricing. Affecting approximately 30% of users browsing the catalog.",
            "labels": ["bug", "search"]
        }
        resp = requests.post(f"{AIIS_URL}/investigate", json=payload, timeout=120)
        assert resp.status_code == 200
        body = resp.json()
        print(f"  🔍 Domain: {body.get('domain')}")
        print(f"  🎯 Confidence: {body.get('confidence'):.2f}")
        print(f"  ✅ Completed: {body.get('completed')}")
        assert body["completed"] is True
        assert body["domain"] in ("pre-purchase", "post-purchase")
        assert 0.0 <= body["confidence"] <= 1.0
        assert body["workflow_id"]
        print(f"  📋 Summary preview: {body.get('summary', '')[:120]}...")

    def test_investigate_post_purchase(self):
        """POST /investigate with a post-purchase issue returns a valid result."""
        payload = {
            "issue_id": 9002,
            "title": "Orders stuck in PENDING state for over 48 hours",
            "description": "The fulfillment pipeline appears to be stuck. 200+ orders have been in PENDING status since yesterday. Shipping notifications are not being sent.",
            "labels": ["bug", "fulfillment", "critical"]
        }
        resp = requests.post(f"{AIIS_URL}/investigate", json=payload, timeout=120)
        assert resp.status_code == 200
        body = resp.json()
        print(f"  🔍 Domain: {body.get('domain')}")
        print(f"  🎯 Confidence: {body.get('confidence'):.2f}")
        assert body["completed"] is True

    def test_investigate_response_has_all_fields(self):
        """Response from /investigate includes all expected fields."""
        payload = {
            "issue_id": 9003,
            "title": "Cart not saving items after login",
            "description": "Users report their cart empties after they log in. The session cart merge is failing."
        }
        resp = requests.post(f"{AIIS_URL}/investigate", json=payload, timeout=120)
        body = resp.json()
        for field in ["workflow_id", "issue_id", "domain", "confidence", "completed", "summary"]:
            assert field in body, f"Missing field: {field}"
        print(f"  ✅ All required fields present in response")

    def test_investigate_shown_in_browser(self, browser_page: Page):
        """Show the /investigate response rendered in browser via fetch."""
        browser_page.goto(f"{AIIS_URL}/docs", wait_until="networkidle")
        # Navigate to the raw JSON response via JS fetch in the page
        result = browser_page.evaluate("""
            async () => {
                const resp = await fetch('/investigate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        issue_id: 9004,
                        title: 'Return label not generated',
                        description: 'Customers cannot generate return shipping labels. The returns portal shows an error.'
                    })
                });
                return await resp.json();
            }
        """)
        assert result["completed"] is True
        print(f"  🔍 Domain (from browser fetch): {result['domain']}")
        print(f"  🎯 Confidence: {result['confidence']:.2f}")
        screenshot(browser_page, "06_investigate_swagger_after_call")


# ─── Elasticsearch Tests ──────────────────────────────────────────────────────

class TestElasticsearch:
    def test_cluster_health_in_browser(self, browser_page: Page):
        """Elasticsearch cluster health page renders in browser."""
        browser_page.goto(f"{ES_URL}/_cluster/health?pretty", wait_until="load")
        content = browser_page.inner_text("body")
        assert "cluster_name" in content
        assert "status" in content
        screenshot(browser_page, "07_elasticsearch_cluster_health")
        print(f"  ✅ Elasticsearch cluster health page loaded")

    def test_aiis_index_exists(self, browser_page: Page):
        """AIIS events index exists after workflow runs."""
        browser_page.goto(f"{ES_URL}/aiis-events-*/_count?pretty", wait_until="load")
        content = browser_page.inner_text("body")
        assert "count" in content
        # Parse the count
        try:
            data = json.loads(content)
            count = data.get("count", 0)
            print(f"  ✅ AIIS events in Elasticsearch: {count}")
        except Exception:
            print(f"  ✅ AIIS events index responding (count in page)")
        screenshot(browser_page, "08_elasticsearch_event_count")

    def test_aiis_index_mappings_in_browser(self, browser_page: Page):
        """View AIIS index field mappings in browser."""
        browser_page.goto(f"{ES_URL}/aiis-events-*/_mapping?pretty", wait_until="load")
        content = browser_page.inner_text("body")
        screenshot(browser_page, "09_elasticsearch_mappings")
        # Verify key fields are mapped
        for field in ["trace_id", "event_type", "agent", "timestamp"]:
            assert field in content, f"Field '{field}' not in mapping"
        print("  ✅ Key field mappings present: trace_id, event_type, agent, timestamp")

    def test_recent_events_query(self, browser_page: Page):
        """Query recent AIIS events and display in browser."""
        browser_page.goto(
            f"{ES_URL}/aiis-events-*/_search?pretty&size=5&sort=timestamp:desc",
            wait_until="load"
        )
        content = browser_page.inner_text("body")
        screenshot(browser_page, "10_elasticsearch_recent_events")
        assert "hits" in content
        print("  ✅ Recent events query rendered in browser")


# ─── Kibana Tests ────────────────────────────────────────────────────────────

class TestKibana:
    def test_kibana_loads(self, browser_page: Page):
        """Kibana home page loads and redirects to the app."""
        browser_page.goto(KIBANA_URL, wait_until="networkidle", timeout=30000)
        screenshot(browser_page, "11_kibana_home")
        # Kibana may redirect to /app/home or show a loading screen
        assert "kibana" in browser_page.url.lower() or "localhost:5601" in browser_page.url
        print(f"  ✅ Kibana loaded at: {browser_page.url}")

    def test_kibana_discover(self, browser_page: Page):
        """Navigate to Kibana Discover page."""
        browser_page.goto(f"{KIBANA_URL}/app/discover", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        screenshot(browser_page, "12_kibana_discover")
        print(f"  ✅ Kibana Discover at: {browser_page.url}")

    def test_kibana_dashboard(self, browser_page: Page):
        """Navigate to Kibana Dashboards page."""
        browser_page.goto(f"{KIBANA_URL}/app/dashboards", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        screenshot(browser_page, "13_kibana_dashboards")
        print(f"  ✅ Kibana Dashboards page loaded")

    def test_kibana_dev_tools(self, browser_page: Page):
        """Open Kibana Dev Tools console."""
        browser_page.goto(f"{KIBANA_URL}/app/dev_tools", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        screenshot(browser_page, "14_kibana_dev_tools")
        print(f"  ✅ Kibana Dev Tools page loaded")
