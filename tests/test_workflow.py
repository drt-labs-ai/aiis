"""Integration tests for the LangGraph workflow."""
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.state import WorkflowState
from src.a2a.messages import (
    Domain, InvestigationResult, InvestigationStatus,
)


@pytest.fixture(autouse=True)
def register_agents():
    from src.agents.domain import create_pre_purchase_agent, create_post_purchase_agent
    create_pre_purchase_agent()
    create_post_purchase_agent()


def _mock_investigation_result(trace_id: str, workflow_id: str, issue_id: int) -> InvestigationResult:
    return InvestigationResult(
        trace_id=trace_id,
        workflow_id=workflow_id,
        issue_id=issue_id,
        status=InvestigationStatus.COMPLETED,
        confidence=0.87,
        summary="Mock investigation summary",
        root_cause="Mock root cause",
        recommended_actions=["Action 1", "Action 2"],
        investigation_steps=["Step 1", "Step 2"],
        evidence=[],
        knowledge_retrieved=["doc1.md"],
        iterations=2,
    )


class TestWorkflowNodes:
    @pytest.mark.asyncio
    async def test_node_start_initializes_trace(self):
        from src.workflow.graph import node_start
        state = WorkflowState(issue_id=1, title="Test", description="Desc", workflow_id="wf-1")
        with patch("src.workflow.graph.ingest_event", new_callable=AsyncMock):
            result = await node_start(state)
        assert result.trace_id != ""
        assert result.workflow_id == "wf-1"

    @pytest.mark.asyncio
    async def test_node_triage_routes_pre_purchase(self):
        from src.workflow.graph import node_triage
        state = WorkflowState(
            issue_id=1,
            title="Cart prices not updating",
            description="Cart promotion code not applied",
            workflow_id="wf-2",
            trace_id="trace-2",
        )
        with patch("src.agents.supervisor.agent.add_labels", new_callable=AsyncMock), \
             patch("src.agents.supervisor.agent.assign_issue", new_callable=AsyncMock), \
             patch("src.agents.supervisor.agent._llm_classify", new_callable=AsyncMock, return_value=None), \
             patch("src.workflow.graph.ingest_event", new_callable=AsyncMock):
            result = await node_triage(state)
        assert result.assigned_domain is not None

    def test_route_after_triage_error_path(self):
        from src.workflow.graph import route_after_triage
        state = WorkflowState(issue_id=1, error="Something failed")
        assert route_after_triage(state) == "error"

    def test_route_after_triage_happy_path(self):
        from src.workflow.graph import route_after_triage
        state = WorkflowState(issue_id=1, assigned_domain=Domain.PRE_PURCHASE)
        assert route_after_triage(state) == "delegate"

    def test_route_after_delegate_error(self):
        from src.workflow.graph import route_after_delegate
        state = WorkflowState(issue_id=1, error="A2A failed")
        assert route_after_delegate(state) == "error"

    def test_route_after_delegate_success(self):
        from src.workflow.graph import route_after_delegate
        result = _mock_investigation_result("t1", "wf1", 1)
        state = WorkflowState(issue_id=1, investigation_result=result)
        assert route_after_delegate(state) == "update_github"


class TestFullWorkflow:
    @pytest.mark.asyncio
    async def test_full_workflow_pre_purchase(self):
        from src.workflow.graph import get_workflow
        import uuid

        workflow = get_workflow()
        state = WorkflowState(
            issue_id=101,
            title="Search returns no results for electronics",
            description="Solr index may be corrupted, search is broken on PLP",
            workflow_id=str(uuid.uuid4()),
        )

        with patch("src.agents.supervisor.agent.add_labels", new_callable=AsyncMock), \
             patch("src.agents.supervisor.agent.assign_issue", new_callable=AsyncMock), \
             patch("src.agents.supervisor.agent._llm_classify", new_callable=AsyncMock, return_value=None), \
             patch("src.workflow.graph.add_comment", new_callable=AsyncMock, return_value={"mock": True}), \
             patch("src.kafka.producer.publish", new_callable=AsyncMock, return_value=True) as mock_publish:

            raw = await workflow.ainvoke(state)

        # LangGraph returns dict when using Pydantic state schema
        final = WorkflowState.model_validate(raw) if isinstance(raw, dict) else raw
        assert final.completed is True
        assert final.assigned_domain == Domain.PRE_PURCHASE
        assert final.investigation_result is not None
        assert final.investigation_result.confidence > 0
        # All observability events must flow through Kafka — no direct ES path
        assert mock_publish.called, "Expected all ingest_event() calls to go through Kafka producer"

    @pytest.mark.asyncio
    async def test_full_workflow_post_purchase(self):
        from src.workflow.graph import get_workflow
        import uuid

        workflow = get_workflow()
        state = WorkflowState(
            issue_id=201,
            title="Orders stuck in processing, fulfillment not triggered",
            description="Multiple orders not advancing to fulfillment, shipping delayed",
            workflow_id=str(uuid.uuid4()),
        )

        with patch("src.agents.supervisor.agent.add_labels", new_callable=AsyncMock), \
             patch("src.agents.supervisor.agent.assign_issue", new_callable=AsyncMock), \
             patch("src.agents.supervisor.agent._llm_classify", new_callable=AsyncMock, return_value=None), \
             patch("src.workflow.graph.add_comment", new_callable=AsyncMock, return_value={"mock": True}), \
             patch("src.kafka.producer.publish", new_callable=AsyncMock, return_value=True) as mock_publish:

            raw = await workflow.ainvoke(state)

        final = WorkflowState.model_validate(raw) if isinstance(raw, dict) else raw
        assert final.completed is True
        assert final.assigned_domain == Domain.POST_PURCHASE
        assert mock_publish.called, "Expected all ingest_event() calls to go through Kafka producer"
