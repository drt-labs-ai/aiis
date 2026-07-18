"""
Standalone MCP server exposing GitHub, debugging, and knowledge tools.
Run with: python -m src.mcp_server.server
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
from typing import Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPToolResult(BaseModel):
    content: list[dict[str, Any]]
    is_error: bool = False


# Tool registry
_TOOLS: dict[str, MCPTool] = {}
_HANDLERS: dict[str, Any] = {}


def register_tool(tool: MCPTool, handler):
    _TOOLS[tool.name] = tool
    _HANDLERS[tool.name] = handler


def _register_all_tools():
    from src.mcp_server.tools.github_tools import (
        assign_issue, add_labels, add_comment, search_issues
    )
    from src.mcp_server.tools.debugging_tools import (
        get_kibana_logs, get_dynatrace_traces, execute_flexible_search,
        configuration_lookup, feature_flag_lookup, service_health
    )
    from src.mcp_server.tools.knowledge_tools import (
        search_knowledge_base, retrieve_runbook, retrieve_architecture_docs
    )

    register_tool(MCPTool(
        name="assign_issue",
        description="Assign a GitHub issue to team members",
        input_schema={"type": "object", "properties": {"issue_number": {"type": "integer"}, "assignees": {"type": "array", "items": {"type": "string"}}}, "required": ["issue_number", "assignees"]},
    ), assign_issue)

    register_tool(MCPTool(
        name="add_labels",
        description="Add labels to a GitHub issue",
        input_schema={"type": "object", "properties": {"issue_number": {"type": "integer"}, "labels": {"type": "array", "items": {"type": "string"}}}, "required": ["issue_number", "labels"]},
    ), add_labels)

    register_tool(MCPTool(
        name="add_comment",
        description="Add a comment to a GitHub issue",
        input_schema={"type": "object", "properties": {"issue_number": {"type": "integer"}, "body": {"type": "string"}}, "required": ["issue_number", "body"]},
    ), add_comment)

    register_tool(MCPTool(
        name="search_issues",
        description="Search GitHub for similar issues",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}, "repo": {"type": "string"}}, "required": ["query"]},
    ), search_issues)

    register_tool(MCPTool(
        name="get_kibana_logs",
        description="Retrieve recent logs for a service from Kibana",
        input_schema={"type": "object", "properties": {"service": {"type": "string"}, "time_range_minutes": {"type": "integer"}, "log_level": {"type": "string"}}, "required": ["service"]},
    ), get_kibana_logs)

    register_tool(MCPTool(
        name="get_dynatrace_traces",
        description="Fetch distributed traces from Dynatrace",
        input_schema={"type": "object", "properties": {"service": {"type": "string"}, "issue_keywords": {"type": "array", "items": {"type": "string"}}}, "required": ["service"]},
    ), get_dynatrace_traces)

    register_tool(MCPTool(
        name="execute_flexible_search",
        description="Execute a SAP Commerce flexible search query",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}, "index": {"type": "string"}, "filters": {"type": "object"}}, "required": ["query"]},
    ), execute_flexible_search)

    register_tool(MCPTool(
        name="configuration_lookup",
        description="Look up a configuration key",
        input_schema={"type": "object", "properties": {"key": {"type": "string"}, "environment": {"type": "string"}}, "required": ["key"]},
    ), configuration_lookup)

    register_tool(MCPTool(
        name="feature_flag_lookup",
        description="Check the status of a feature flag",
        input_schema={"type": "object", "properties": {"flag_name": {"type": "string"}, "user_segment": {"type": "string"}}, "required": ["flag_name"]},
    ), feature_flag_lookup)

    register_tool(MCPTool(
        name="service_health",
        description="Check the health status of a service",
        input_schema={"type": "object", "properties": {"service_name": {"type": "string"}}, "required": ["service_name"]},
    ), service_health)

    register_tool(MCPTool(
        name="search_knowledge_base",
        description="Search the RAG knowledge base for relevant documentation",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}, "domain": {"type": "string"}, "top_k": {"type": "integer"}}, "required": ["query", "domain"]},
    ), search_knowledge_base)

    register_tool(MCPTool(
        name="retrieve_runbook",
        description="Retrieve a specific runbook by name",
        input_schema={"type": "object", "properties": {"runbook_name": {"type": "string"}, "domain": {"type": "string"}}, "required": ["runbook_name", "domain"]},
    ), retrieve_runbook)

    register_tool(MCPTool(
        name="retrieve_architecture_docs",
        description="Retrieve architecture documentation for a component",
        input_schema={"type": "object", "properties": {"component": {"type": "string"}, "domain": {"type": "string"}}, "required": ["component", "domain"]},
    ), retrieve_architecture_docs)


class MCPServer:
    """Lightweight MCP server compatible with MCP stdio protocol."""

    def __init__(self):
        _register_all_tools()

    async def list_tools(self) -> list[MCPTool]:
        return list(_TOOLS.values())

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        handler = _HANDLERS.get(name)
        if not handler:
            return MCPToolResult(
                content=[{"type": "text", "text": f"Tool '{name}' not found"}],
                is_error=True,
            )
        try:
            result = await handler(**arguments)
            return MCPToolResult(
                content=[{"type": "text", "text": json.dumps(result, indent=2, default=str)}]
            )
        except Exception as exc:
            logger.exception(f"MCP tool '{name}' failed")
            return MCPToolResult(
                content=[{"type": "text", "text": f"Tool error: {exc}"}],
                is_error=True,
            )


_mcp_server = MCPServer()


def get_mcp_server() -> MCPServer:
    return _mcp_server
