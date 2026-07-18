"""Tests for the Supervisor Agent routing logic."""
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.supervisor.agent import _keyword_classify, SupervisorAgent
from src.agents.state import WorkflowState
from src.a2a.messages import Domain


class TestKeywordClassify:
    def test_pre_purchase_keywords(self):
        domain, confidence = _keyword_classify(
            "Search returns empty results on PLP",
            "Solr index seems corrupted, users cannot find products",
        )
        assert domain == Domain.PRE_PURCHASE
        assert confidence > 0.5

    def test_post_purchase_keywords(self):
        domain, confidence = _keyword_classify(
            "Order stuck in processing",
            "Orders placed this morning are not moving to fulfillment, shipping delayed",
        )
        assert domain == Domain.POST_PURCHASE
        assert confidence > 0.5

    def test_returns_pre_purchase_on_tie(self):
        domain, _ = _keyword_classify("Unknown issue", "Some generic problem")
        assert domain == Domain.PRE_PURCHASE


class TestSupervisorAgent:
    @pytest.mark.asyncio
    async def test_triage_assigns_domain(self):
        supervisor = SupervisorAgent()
        state = WorkflowState(
            issue_id=1,
            title="Cart not updating prices after promotion applied",
            description="Cart total stays the same after entering a promo code",
            workflow_id="test-wf",
            trace_id="test-trace",
        )

        with patch("src.agents.supervisor.agent.add_labels", new_callable=AsyncMock) as mock_labels, \
             patch("src.agents.supervisor.agent.assign_issue", new_callable=AsyncMock) as mock_assign, \
             patch("src.agents.supervisor.agent._llm_classify", new_callable=AsyncMock, return_value=None):
            result = await supervisor.triage(state)

        assert result.assigned_domain is not None
        assert result.routing_reason != ""
        mock_labels.assert_called_once()
        mock_assign.assert_called_once()

    @pytest.mark.asyncio
    async def test_triage_uses_llm_when_available(self):
        supervisor = SupervisorAgent()
        state = WorkflowState(
            issue_id=2,
            title="Refund not processed",
            description="Customer return accepted but refund not issued",
            workflow_id="test-wf-2",
            trace_id="test-trace-2",
        )

        llm_result = {
            "domain": "post-purchase",
            "reasoning": "Issue relates to refund processing",
            "confidence": 0.95,
            "suggested_labels": ["post-purchase", "refunds"],
            "suggested_assignees": ["team-post-purchase"],
        }

        with patch("src.agents.supervisor.agent.add_labels", new_callable=AsyncMock), \
             patch("src.agents.supervisor.agent.assign_issue", new_callable=AsyncMock), \
             patch("src.agents.supervisor.agent._llm_classify", new_callable=AsyncMock, return_value=llm_result):
            result = await supervisor.triage(state)

        assert result.assigned_domain == Domain.POST_PURCHASE
        assert "refund" in result.routing_reason.lower()
