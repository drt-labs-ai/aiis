"""Tests for the A2A protocol layer."""
import pytest
from src.a2a.messages import Domain, InvestigationRequest, InvestigationResult, InvestigationStatus
from src.a2a.registry import AgentRegistry
from src.a2a.transport import InMemoryTransport
from src.a2a.client import A2AClient
from src.a2a.server import A2AServer


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.fixture
def transport():
    return InMemoryTransport()


class TestInvestigationRequest:
    def test_defaults_generated(self):
        req = InvestigationRequest(
            issue_id=42,
            title="Search broken",
            description="No results returned",
            assigned_domain=Domain.PRE_PURCHASE,
        )
        assert req.issue_id == 42
        assert req.trace_id != ""
        assert req.workflow_id != ""
        assert req.assigned_domain == Domain.PRE_PURCHASE

    def test_serialization_round_trip(self):
        req = InvestigationRequest(
            issue_id=99,
            title="Order stuck",
            description="Order not moving",
            assigned_domain=Domain.POST_PURCHASE,
        )
        data = req.model_dump(mode="json")
        restored = InvestigationRequest.model_validate(data)
        assert restored.issue_id == 99
        assert restored.assigned_domain == Domain.POST_PURCHASE


class TestAgentRegistry:
    def test_register_and_resolve(self, registry):
        registry.register(
            agent_id="test-agent",
            domain=Domain.PRE_PURCHASE,
            description="Test agent",
            capabilities=["rag"],
        )
        resolved = registry.resolve(Domain.PRE_PURCHASE)
        assert resolved == "test-agent"

    def test_resolve_unknown_domain_returns_none(self, registry):
        assert registry.resolve(Domain.POST_PURCHASE) is None

    def test_get_agent(self, registry):
        registry.register("agent-x", Domain.POST_PURCHASE, "desc", [])
        reg = registry.get("agent-x")
        assert reg is not None
        assert reg.agent_id == "agent-x"


class TestInMemoryTransport:
    @pytest.mark.asyncio
    async def test_send_dispatches_to_handler(self, transport):
        async def handler(payload):
            return {"echo": payload.get("title")}

        transport.register_handler("my-agent", handler)
        result = await transport.send("my-agent", {"title": "hello"})
        assert result == {"echo": "hello"}

    @pytest.mark.asyncio
    async def test_send_to_unknown_raises(self, transport):
        with pytest.raises(ValueError, match="No handler registered"):
            await transport.send("ghost-agent", {})

    @pytest.mark.asyncio
    async def test_message_log_populated(self, transport):
        async def handler(p):
            return {}

        transport.register_handler("a", handler)
        await transport.send("a", {"x": 1})
        assert len(transport.message_log) == 1
        assert transport.message_log[0]["to"] == "a"
