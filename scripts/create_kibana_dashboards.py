#!/usr/bin/env python3
"""
AIIS Kibana Dashboard Creator.

Creates two fully-wired dashboards via the Kibana saved objects REST API:

  Dashboard 1 — AIIS Issue Status
    - Total workflows, completed, failed counts
    - Pre-purchase vs post-purchase issue split
    - Domain routing distribution (donut)
    - Workflow status distribution (donut)
    - Issues over time (area chart)
    - Investigation duration histogram
    - Events-per-team bar chart
    - Issue details table (issue_id × agent × status)

  Dashboard 2 — AIIS Trace & Debug
    - Total events, MCP calls, A2A messages, RAG searches, error count
    - Full event timeline (area, split by event_type)
    - Events by agent (horizontal bar)
    - Event type distribution (donut)
    - Average duration by event type (horizontal bar)
    - Agent activity over time (area, split by agent)
    - Investigation phases breakdown (donut, filtered to INVESTIGATION_*)
    - All events table (trace_id, span_id, agent, event_type, status, duration_ms)

Usage:
    uv run python scripts/create_kibana_dashboards.py
    KIBANA_URL=http://myhost:5601 uv run python scripts/create_kibana_dashboards.py
"""
from __future__ import annotations

import json
import os
import sys
import time

import httpx

KIBANA_URL = os.getenv("KIBANA_URL", "http://localhost:5601")
INDEX_ID = "aiis-events-pattern"
INDEX_TITLE = "aiis-events-*"
HDR = {"kbn-xsrf": "true", "Content-Type": "application/json"}


# ─── Kibana REST helpers ───────────────────────────────────────────────────────

def kpost(client: httpx.Client, path: str, body: dict) -> dict:
    resp = client.post(f"{KIBANA_URL}{path}", json=body, timeout=30)
    if not resp.is_success:
        print(f"  WARN {path} → {resp.status_code}: {resp.text[:300]}")
    try:
        return resp.json()
    except Exception:
        return {}


def wait_for_kibana() -> None:
    print("Waiting for Kibana...")
    with httpx.Client(headers=HDR) as c:
        for _ in range(30):
            try:
                r = c.get(f"{KIBANA_URL}/api/status", timeout=5)
                if r.is_success:
                    print("  ✓ Kibana ready")
                    return
            except Exception:
                pass
            time.sleep(3)
    print("ERROR: Kibana not reachable after 90 s")
    sys.exit(1)


def save_obj(client: httpx.Client, obj_type: str, obj_id: str, attrs: dict, refs: list | None = None) -> str:
    body = {"attributes": attrs, "references": refs or []}
    result = kpost(client, f"/api/saved_objects/{obj_type}/{obj_id}?overwrite=true", body)
    status = "✓" if "id" in result else "✗"
    print(f"  {status} {obj_type}/{obj_id}: {attrs.get('title', obj_id)}")
    return obj_id


# ─── visState builders ─────────────────────────────────────────────────────────

def _search_source(kql: str = "") -> str:
    return json.dumps({
        "query": {"query": kql, "language": "kuery"},
        "filter": [],
        "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
    })


def _index_ref() -> list:
    return [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": INDEX_ID}]


def vis_attrs(title: str, vis_state: dict, kql: str = "", needs_index: bool = True) -> tuple[dict, list]:
    """Return (attributes_dict, references_list) for a visualization saved object."""
    ss = _search_source(kql) if needs_index else json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
    attrs = {
        "title": title,
        "visState": json.dumps(vis_state),
        "uiStateJSON": "{}",
        "description": "",
        "kibanaSavedObjectMeta": {"searchSourceJSON": ss},
    }
    refs = _index_ref() if needs_index else []
    return attrs, refs


def v_metric(title: str, kql: str = "") -> tuple[dict, list]:
    vs = {
        "title": title, "type": "metric",
        "aggs": [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}}],
        "params": {
            "addTooltip": True, "addLegend": False, "type": "metric",
            "metric": {
                "percentageMode": False, "useRanges": False,
                "colorSchema": "Green to Red", "metricColorMode": "None",
                "colorsRange": [{"from": 0, "to": 100000}],
                "labels": {"show": True}, "invertColors": False,
                "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 60}
            }
        }
    }
    return vis_attrs(title, vs, kql)


def v_pie(title: str, field: str, kql: str = "", size: int = 10) -> tuple[dict, list]:
    vs = {
        "title": title, "type": "pie",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {"id": "2", "enabled": True, "type": "terms", "schema": "segment", "params": {
                "field": field, "size": size, "order": "desc", "orderBy": "1", "otherBucket": False
            }}
        ],
        "params": {
            "type": "pie", "addTooltip": True, "addLegend": True,
            "legendPosition": "right", "isDonut": True,
            "labels": {"show": False, "values": True, "last_level": True, "truncate": 100}
        }
    }
    return vis_attrs(title, vs, kql)


def v_area(title: str, kql: str = "", split_field: str | None = None) -> tuple[dict, list]:
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "date_histogram", "schema": "segment", "params": {
            "field": "timestamp", "useNormalizedEsInterval": True, "interval": "auto",
            "drop_partials": False, "min_doc_count": 1, "extended_bounds": {}
        }}
    ]
    if split_field:
        aggs.append({"id": "3", "enabled": True, "type": "terms", "schema": "group", "params": {
            "field": split_field, "size": 10, "order": "desc", "orderBy": "1"
        }})
    vs = {
        "title": title, "type": "area", "aggs": aggs,
        "params": {
            "type": "area", "grid": {"categoryLines": False},
            "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "bottom",
                "show": True, "scale": {"type": "linear"},
                "labels": {"show": True, "filter": True, "truncate": 100}, "title": {}}],
            "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "left",
                "show": True, "scale": {"type": "linear", "mode": "normal"},
                "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                "title": {"text": "Count"}}],
            "seriesParams": [{"show": True, "type": "area", "mode": "stacked",
                "data": {"label": "Count", "id": "1"},
                "drawLinesBetweenPoints": True, "lineWidth": 2, "showCircles": True}],
            "addTooltip": True, "addLegend": True, "legendPosition": "right",
            "times": [], "addTimeMarker": False,
            "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"},
            "labels": {}
        }
    }
    return vis_attrs(title, vs, kql)


def v_hbar(title: str, field: str, kql: str = "", size: int = 15) -> tuple[dict, list]:
    vs = {
        "title": title, "type": "histogram",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {"id": "2", "enabled": True, "type": "terms", "schema": "segment", "params": {
                "field": field, "size": size, "order": "desc", "orderBy": "1"
            }}
        ],
        "params": {
            "type": "histogram", "grid": {"categoryLines": False},
            "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "left",
                "show": True, "scale": {"type": "linear"},
                "labels": {"show": True, "rotate": 0, "filter": True, "truncate": 200}, "title": {}}],
            "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "bottom",
                "show": True, "scale": {"type": "linear", "mode": "normal"},
                "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                "title": {"text": "Count"}}],
            "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                "data": {"label": "Count", "id": "1"}, "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True, "lineWidth": 2, "showCircles": True}],
            "addTooltip": True, "addLegend": True, "legendPosition": "right",
            "times": [], "addTimeMarker": False
        }
    }
    return vis_attrs(title, vs, kql)


def v_hbar_avg(title: str, group_field: str, avg_field: str, kql: str = "", size: int = 15) -> tuple[dict, list]:
    vs = {
        "title": title, "type": "histogram",
        "aggs": [
            {"id": "1", "enabled": True, "type": "avg", "schema": "metric", "params": {"field": avg_field}},
            {"id": "2", "enabled": True, "type": "terms", "schema": "segment", "params": {
                "field": group_field, "size": size, "order": "desc", "orderBy": "1"
            }}
        ],
        "params": {
            "type": "histogram", "grid": {"categoryLines": False},
            "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "left",
                "show": True, "scale": {"type": "linear"},
                "labels": {"show": True, "rotate": 0, "filter": True, "truncate": 200}, "title": {}}],
            "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "bottom",
                "show": True, "scale": {"type": "linear", "mode": "normal"},
                "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                "title": {"text": f"Avg {avg_field} (ms)"}}],
            "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                "data": {"label": f"Avg {avg_field}", "id": "1"}, "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True, "lineWidth": 2, "showCircles": True}],
            "addTooltip": True, "addLegend": True, "legendPosition": "right",
            "times": [], "addTimeMarker": False
        }
    }
    return vis_attrs(title, vs, kql)


def v_table(title: str, bucket_fields: list[tuple[str, int]], kql: str = "") -> tuple[dict, list]:
    """bucket_fields: [(field_name, bucket_size), ...]"""
    aggs = [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}}]
    for i, (field, size) in enumerate(bucket_fields, start=2):
        aggs.append({"id": str(i), "enabled": True, "type": "terms", "schema": "bucket", "params": {
            "field": field, "size": size, "order": "desc", "orderBy": "1", "otherBucket": False
        }})
    vs = {
        "title": title, "type": "table", "aggs": aggs,
        "params": {
            "perPage": 25, "showPartialRows": False, "showMetricsAtAllLevels": False,
            "sort": {"columnIndex": None, "direction": None},
            "showTotal": False, "totalFunc": "sum", "percentageCol": ""
        }
    }
    return vis_attrs(title, vs, kql)


def v_markdown(title: str, text: str) -> tuple[dict, list]:
    vs = {"title": title, "type": "markdown", "aggs": [], "params": {"markdown": text, "openLinksInNewTab": False}}
    return vis_attrs(title, vs, needs_index=False)


def v_histo_range(title: str, field: str, interval: int = 200, kql: str = "") -> tuple[dict, list]:
    vs = {
        "title": title, "type": "histogram",
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {"id": "2", "enabled": True, "type": "histogram", "schema": "segment", "params": {
                "field": field, "interval": interval, "extended_bounds": {}, "min_doc_count": False
            }}
        ],
        "params": {
            "type": "histogram", "grid": {"categoryLines": False},
            "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "bottom",
                "show": True, "scale": {"type": "linear"},
                "labels": {"show": True, "filter": True, "truncate": 100}, "title": {}}],
            "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "left",
                "show": True, "scale": {"type": "linear", "mode": "normal"},
                "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
                "title": {"text": "Investigations"}}],
            "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked",
                "data": {"label": "Count", "id": "1"}, "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True, "lineWidth": 2, "showCircles": True}],
            "addTooltip": True, "addLegend": True, "legendPosition": "right",
            "times": [], "addTimeMarker": False, "labels": {}
        }
    }
    return vis_attrs(title, vs, kql)


# ─── Panel layout helper ───────────────────────────────────────────────────────

_panel_counter = 0


def mk_panel(viz_id: str, x: int, y: int, w: int, h: int, title: str = "") -> tuple[dict, dict]:
    global _panel_counter
    _panel_counter += 1
    idx = str(_panel_counter)
    ref_name = f"panel_{idx}"
    p: dict = {
        "panelIndex": idx,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": idx},
        "type": "visualization",
        "embeddableConfig": {"enhancements": {}},
        "panelRefName": ref_name,
    }
    if title:
        p["title"] = title
    r = {"name": ref_name, "type": "visualization", "id": viz_id}
    return p, r


def mk_dashboard_attrs(panels_refs: list[tuple[dict, dict]]) -> tuple[dict, list]:
    panels = [pr[0] for pr in panels_refs]
    refs = [pr[1] for pr in panels_refs]
    attrs = {
        "panelsJSON": json.dumps(panels),
        "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
        "timeFrom": "now-7d",
        "timeTo": "now",
        "timeRestore": True,
        "refreshInterval": {"pause": True, "value": 0},
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
        },
    }
    return attrs, refs


# ─── Ensure index pattern ──────────────────────────────────────────────────────

def ensure_index_pattern(client: httpx.Client) -> None:
    print("\n[1] Index pattern")
    # Try newer Data Views API first, fall back to legacy
    body = {
        "data_view": {
            "id": INDEX_ID,
            "title": INDEX_TITLE,
            "timeFieldName": "timestamp",
        }
    }
    resp = client.post(f"{KIBANA_URL}/api/data_views/data_view", json=body, timeout=30)
    if resp.is_success:
        print(f"  ✓ Data view created: {INDEX_TITLE}")
        return

    # Legacy index-pattern fallback
    attrs = {"title": INDEX_TITLE, "timeFieldName": "timestamp"}
    result = kpost(client, f"/api/saved_objects/index-pattern/{INDEX_ID}?overwrite=true",
                   {"attributes": attrs})
    if "id" in result:
        print(f"  ✓ Index pattern created: {INDEX_TITLE}")
    else:
        print(f"  ✗ Index pattern creation failed — check Kibana is running")


# ─── Dashboard 1: Issue Status ─────────────────────────────────────────────────

def create_issue_status_dashboard(client: httpx.Client) -> None:
    print("\n[2] Issue Status Dashboard visualizations")
    p = "aiis-is-"  # id prefix

    # ── Row 1: stat metrics (y=0, h=8) ─────────────────────────────────────
    # 6 stats × w=8 each = 48 total
    v1 = save_obj(client, "visualization", f"{p}m-total",
                  *v_metric("Total Workflows", kql="event_type: WORKFLOW_STARTED"))
    v2 = save_obj(client, "visualization", f"{p}m-completed",
                  *v_metric("Completed", kql="event_type: WORKFLOW_COMPLETED"))
    v3 = save_obj(client, "visualization", f"{p}m-failed",
                  *v_metric("Failed", kql="event_type: WORKFLOW_FAILED"))
    v4 = save_obj(client, "visualization", f"{p}m-pre-purchase",
                  *v_metric("Pre-Purchase Issues", kql="agent: pre-purchase-agent AND event_type: INVESTIGATION_FINISHED"))
    v5 = save_obj(client, "visualization", f"{p}m-post-purchase",
                  *v_metric("Post-Purchase Issues", kql="agent: post-purchase-agent AND event_type: INVESTIGATION_FINISHED"))
    v6 = save_obj(client, "visualization", f"{p}m-mcp-calls",
                  *v_metric("MCP Tool Calls", kql="event_type: MCP_TOOL_CALL"))

    # ── Row 2: pie charts (y=8, h=20) ──────────────────────────────────────
    v7 = save_obj(client, "visualization", f"{p}pie-domain",
                  *v_pie("Issues by Domain (Agent)", "agent",
                         kql="event_type: INVESTIGATION_FINISHED"))
    v8 = save_obj(client, "visualization", f"{p}pie-status",
                  *v_pie("Workflow Status Distribution", "status",
                         kql="event_type: WORKFLOW_COMPLETED OR event_type: WORKFLOW_FAILED"))

    # ── Row 3: workflows over time (y=28, h=18) ─────────────────────────────
    v9 = save_obj(client, "visualization", f"{p}area-time",
                  *v_area("Workflows Over Time", kql="event_type: WORKFLOW_STARTED"))

    # ── Row 4: bar charts (y=46, h=18) ──────────────────────────────────────
    v10 = save_obj(client, "visualization", f"{p}hbar-team",
                   *v_hbar("Events Per Agent / Team", "agent"))
    v11 = save_obj(client, "visualization", f"{p}hbar-status",
                   *v_hbar("Events Per Status", "status"))

    # ── Row 5: duration histogram (y=64, h=15) ──────────────────────────────
    v12 = save_obj(client, "visualization", f"{p}histo-duration",
                   *v_histo_range("Investigation Duration Distribution (ms)",
                                  "duration_ms", interval=500,
                                  kql="event_type: INVESTIGATION_FINISHED"))

    # ── Row 6: issue summary table (y=79, h=25) ─────────────────────────────
    v13 = save_obj(client, "visualization", f"{p}table-issues",
                   *v_table("Issue Summary — by Issue × Agent × Status",
                            [("issue_id", 50), ("agent", 5), ("status", 5)],
                            kql="event_type: INVESTIGATION_FINISHED OR event_type: WORKFLOW_COMPLETED"))

    # ── Row 7: markdown help (y=104, h=10) ──────────────────────────────────
    help_md = """## AIIS Issue Status Dashboard

**How to use:**
- Use the **time picker** (top-right) to select your investigation window
- Click any pie slice or bar segment to **filter** the entire dashboard
- The table shows per-issue resolution data — sort by clicking column headers

**Key metrics:**
| Metric | Source event |
|--------|-------------|
| Total Workflows | `WORKFLOW_STARTED` |
| Completed | `WORKFLOW_COMPLETED` |
| Pre/Post-Purchase | `INVESTIGATION_FINISHED` per agent |

**Tip:** To trace a specific issue, note its `workflow_id` and open the **Trace & Debug** dashboard.
"""
    v14 = save_obj(client, "visualization", f"{p}md-help", *v_markdown("Dashboard Help", help_md))

    # ── Build dashboard ──────────────────────────────────────────────────────
    print("\n[3] Creating Issue Status dashboard")
    global _panel_counter
    _panel_counter = 0  # reset for this dashboard

    panels_refs = [
        # Row 1 — stats
        mk_panel(v1,  x=0,  y=0,  w=8,  h=8),
        mk_panel(v2,  x=8,  y=0,  w=8,  h=8),
        mk_panel(v3,  x=16, y=0,  w=8,  h=8),
        mk_panel(v4,  x=24, y=0,  w=8,  h=8),
        mk_panel(v5,  x=32, y=0,  w=8,  h=8),
        mk_panel(v6,  x=40, y=0,  w=8,  h=8),
        # Row 2 — pies
        mk_panel(v7,  x=0,  y=8,  w=24, h=20),
        mk_panel(v8,  x=24, y=8,  w=24, h=20),
        # Row 3 — timeline
        mk_panel(v9,  x=0,  y=28, w=48, h=18),
        # Row 4 — bars
        mk_panel(v10, x=0,  y=46, w=24, h=18),
        mk_panel(v11, x=24, y=46, w=24, h=18),
        # Row 5 — duration histogram
        mk_panel(v12, x=0,  y=64, w=48, h=15),
        # Row 6 — table
        mk_panel(v13, x=0,  y=79, w=48, h=25),
        # Row 7 — help
        mk_panel(v14, x=0,  y=104, w=48, h=10),
    ]

    dash_attrs, dash_refs = mk_dashboard_attrs(panels_refs)
    dash_attrs["title"] = "AIIS — Issue Status"
    dash_attrs["description"] = (
        "Workflow outcomes, domain routing, pre/post-purchase team splits, "
        "investigation durations, and per-issue resolution details."
    )

    save_obj(client, "dashboard", "aiis-issue-status-dashboard", dash_attrs, dash_refs)


# ─── Dashboard 2: Trace & Debug ────────────────────────────────────────────────

def create_trace_debug_dashboard(client: httpx.Client) -> None:
    print("\n[4] Trace & Debug Dashboard visualizations")
    p = "aiis-td-"

    # ── Row 1: stat metrics (y=0, h=8) ─────────────────────────────────────
    v1 = save_obj(client, "visualization", f"{p}m-total-events",
                  *v_metric("Total Events"))
    v2 = save_obj(client, "visualization", f"{p}m-mcp",
                  *v_metric("MCP Tool Calls", kql="event_type: MCP_TOOL_CALL"))
    v3 = save_obj(client, "visualization", f"{p}m-a2a",
                  *v_metric("A2A Messages", kql="event_type: A2A_REQUEST OR event_type: A2A_RESPONSE"))
    v4 = save_obj(client, "visualization", f"{p}m-rag",
                  *v_metric("RAG Searches", kql="event_type: RAG_SEARCH"))
    v5 = save_obj(client, "visualization", f"{p}m-errors",
                  *v_metric("Error Events", kql="status: ERROR"))
    v6 = save_obj(client, "visualization", f"{p}m-workflows",
                  *v_metric("Workflows", kql="event_type: WORKFLOW_STARTED"))

    # ── Row 2: full-width event timeline split by event_type (y=8, h=20) ───
    v7 = save_obj(client, "visualization", f"{p}area-timeline",
                  *v_area("Event Timeline — All Event Types",
                          split_field="event_type"))

    # ── Row 3: events by agent + event type donut (y=28, h=20) ─────────────
    v8 = save_obj(client, "visualization", f"{p}hbar-agents",
                  *v_hbar("Events by Agent", "agent"))
    v9 = save_obj(client, "visualization", f"{p}pie-event-types",
                  *v_pie("Event Type Distribution", "event_type", size=20))

    # ── Row 4: avg duration per event type + agent activity (y=48, h=20) ───
    v10 = save_obj(client, "visualization", f"{p}hbar-duration",
                   *v_hbar_avg("Avg Duration (ms) by Event Type",
                               "event_type", "duration_ms", size=20))
    v11 = save_obj(client, "visualization", f"{p}area-agents",
                   *v_area("Agent Activity Over Time", split_field="agent"))

    # ── Row 5: investigation phases + MCP activity (y=68, h=20) ─────────────
    v12 = save_obj(client, "visualization", f"{p}pie-investigation",
                   *v_pie("Investigation Phase Events",
                          "event_type",
                          kql="event_type: INVESTIGATION_STARTED OR event_type: INVESTIGATION_ITERATION OR event_type: INVESTIGATION_FINISHED",
                          size=5))
    v13 = save_obj(client, "visualization", f"{p}hbar-mcp-status",
                   *v_hbar("MCP Tool Events by Status", "status",
                           kql="event_type: MCP_TOOL_CALL OR event_type: MCP_TOOL_COMPLETED OR event_type: MCP_TOOL_FAILED"))

    # ── Row 6: A2A + RAG breakdown (y=88, h=15) ──────────────────────────────
    v14 = save_obj(client, "visualization", f"{p}pie-a2a",
                   *v_pie("A2A Message Types", "event_type",
                          kql="event_type: A2A_REQUEST OR event_type: A2A_RESPONSE OR event_type: A2A_ERROR",
                          size=5))
    v15 = save_obj(client, "visualization", f"{p}area-rag",
                   *v_area("RAG Activity Over Time",
                           kql="event_type: RAG_SEARCH OR event_type: RAG_DOCUMENTS_RETRIEVED"))

    # ── Row 7: span trace table (y=103, h=25) ────────────────────────────────
    # Shows trace_id × span_id × agent × event_type for reconstructing call trees
    v16 = save_obj(client, "visualization", f"{p}table-trace",
                   *v_table("Span Trace Table — trace_id × span_id × agent × event_type × status",
                            [
                                ("trace_id", 100),
                                ("span_id", 100),
                                ("agent", 5),
                                ("event_type", 20),
                                ("status", 10),
                            ]))

    # ── Row 8: workflow trace table (y=128, h=20) ─────────────────────────────
    v17 = save_obj(client, "visualization", f"{p}table-workflow",
                   *v_table("Issue × Workflow × Agent Summary",
                            [("issue_id", 100), ("workflow_id", 100), ("agent", 5), ("event_type", 20)]))

    # ── Row 9: markdown usage guide (y=148, h=12) ─────────────────────────────
    help_md = """## AIIS Trace & Debug Dashboard

**Tracing a specific request end-to-end:**
1. Find the `trace_id` from your investigation response (returned by `/investigate`)
2. Use the **Span Trace Table** below — add a KQL filter: `trace_id: "<your-id>"`
3. Read events in timestamp order to reconstruct the full call tree

**span_id / parent_span_id hierarchy:**
- `workflow` spans are root spans (no parent)
- `supervisor` spans have `workflow` as parent
- `A2A_REQUEST` spans have `supervisor` as parent
- `domain-agent` spans have the A2A span as parent
- `MCP_TOOL_CALL` spans have the domain-agent span as parent

**KQL filter examples:**
```
trace_id: "abc-123"           # all events for one request
agent: "pre-purchase-agent"   # only pre-purchase events
event_type: MCP_TOOL_CALL     # only tool calls
status: ERROR                 # only failures
```

**Dashboard refresh:** Set to 30 s during live debugging (time picker → Auto-refresh).
"""
    v18 = save_obj(client, "visualization", f"{p}md-help", *v_markdown("How to Use This Dashboard", help_md))

    # ── Build dashboard ──────────────────────────────────────────────────────
    print("\n[5] Creating Trace & Debug dashboard")
    global _panel_counter
    _panel_counter = 0  # reset for this dashboard

    panels_refs = [
        # Row 1 — stats
        mk_panel(v1,  x=0,  y=0,   w=8,  h=8),
        mk_panel(v2,  x=8,  y=0,   w=8,  h=8),
        mk_panel(v3,  x=16, y=0,   w=8,  h=8),
        mk_panel(v4,  x=24, y=0,   w=8,  h=8),
        mk_panel(v5,  x=32, y=0,   w=8,  h=8),
        mk_panel(v6,  x=40, y=0,   w=8,  h=8),
        # Row 2 — full-width event timeline
        mk_panel(v7,  x=0,  y=8,   w=48, h=20),
        # Row 3 — agents bar + event type donut
        mk_panel(v8,  x=0,  y=28,  w=24, h=20),
        mk_panel(v9,  x=24, y=28,  w=24, h=20),
        # Row 4 — duration bar + agent activity
        mk_panel(v10, x=0,  y=48,  w=24, h=20),
        mk_panel(v11, x=24, y=48,  w=24, h=20),
        # Row 5 — investigation phases + MCP status
        mk_panel(v12, x=0,  y=68,  w=24, h=20),
        mk_panel(v13, x=24, y=68,  w=24, h=20),
        # Row 6 — A2A + RAG
        mk_panel(v14, x=0,  y=88,  w=24, h=15),
        mk_panel(v15, x=24, y=88,  w=24, h=15),
        # Row 7 — span trace table
        mk_panel(v16, x=0,  y=103, w=48, h=25),
        # Row 8 — workflow table
        mk_panel(v17, x=0,  y=128, w=48, h=20),
        # Row 9 — help
        mk_panel(v18, x=0,  y=148, w=48, h=12),
    ]

    dash_attrs, dash_refs = mk_dashboard_attrs(panels_refs)
    dash_attrs["title"] = "AIIS — Trace & Debug"
    dash_attrs["description"] = (
        "Full event timeline, span-level trace reconstruction, agent activity, "
        "MCP tool calls, A2A protocol messages, RAG searches, and error events. "
        "Filter by trace_id to follow any single request end-to-end."
    )

    save_obj(client, "dashboard", "aiis-trace-debug-dashboard", dash_attrs, dash_refs)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    wait_for_kibana()

    with httpx.Client(headers=HDR, follow_redirects=True) as client:
        ensure_index_pattern(client)
        create_issue_status_dashboard(client)
        create_trace_debug_dashboard(client)

    print("\n✅ All dashboards created successfully!")
    print(f"   Issue Status:  {KIBANA_URL}/app/dashboards#/view/aiis-issue-status-dashboard")
    print(f"   Trace & Debug: {KIBANA_URL}/app/dashboards#/view/aiis-trace-debug-dashboard")
    print("\n   Open Kibana → Dashboards to view them.")


if __name__ == "__main__":
    main()
