"""Tests for MCP tool implementations."""
import pytest
from src.mcp_server.tools.debugging_tools import (
    get_kibana_logs,
    get_dynatrace_traces,
    execute_flexible_search,
    configuration_lookup,
    feature_flag_lookup,
    service_health,
)
from src.mcp_server.tools.github_tools import search_issues, add_comment


class TestDebuggingTools:
    @pytest.mark.asyncio
    async def test_kibana_logs_returns_structured_data(self):
        result = await get_kibana_logs("search-service", 60, "ERROR")
        assert "service" in result
        assert result["service"] == "search-service"
        assert "logs" in result
        assert isinstance(result["logs"], list)
        assert "total_hits" in result

    @pytest.mark.asyncio
    async def test_dynatrace_traces_returns_traces(self):
        result = await get_dynatrace_traces("order-service")
        assert "service" in result
        assert "traces" in result
        assert len(result["traces"]) > 0
        trace = result["traces"][0]
        assert "trace_id" in trace
        assert "spans" in trace

    @pytest.mark.asyncio
    async def test_flexible_search(self):
        result = await execute_flexible_search("SELECT * FROM Product WHERE code='123'")
        assert "query" in result
        assert "total_results" in result
        assert "execution_time_ms" in result

    @pytest.mark.asyncio
    async def test_config_lookup_known_key(self):
        result = await configuration_lookup("feature.cart.enabled")
        assert result["key"] == "feature.cart.enabled"
        assert result["value"] == "true"

    @pytest.mark.asyncio
    async def test_config_lookup_unknown_key(self):
        result = await configuration_lookup("nonexistent.key")
        assert "not_found" in result["value"]

    @pytest.mark.asyncio
    async def test_feature_flag_returns_bool(self):
        result = await feature_flag_lookup("checkout.new_flow")
        assert "flag" in result
        assert "enabled" in result
        assert isinstance(result["enabled"], bool)

    @pytest.mark.asyncio
    async def test_service_health(self):
        result = await service_health("cart-service")
        assert result["service"] == "cart-service"
        assert result["status"] in {"healthy", "degraded", "unhealthy"}
        assert 0 <= result["uptime_percentage"] <= 100


class TestGitHubTools:
    @pytest.mark.asyncio
    async def test_search_issues_returns_list_without_credentials(self):
        # Without GITHUB_TOKEN env var, returns mock data
        results = await search_issues("search broken")
        assert isinstance(results, list)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_add_comment_mock_without_credentials(self):
        result = await add_comment(42, "Test comment body")
        assert "mock" in result or "issue_number" in result
