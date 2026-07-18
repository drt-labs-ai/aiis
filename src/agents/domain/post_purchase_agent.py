"""Post-Purchase Domain Agent."""
from __future__ import annotations
from src.a2a.messages import Domain
from src.a2a.server import A2AServer
from .base_agent import BaseDomainAgent


class PostPurchaseAgent(BaseDomainAgent):
    domain = Domain.POST_PURCHASE
    agent_id = "post-purchase-agent"

    @property
    def service_areas(self) -> list[str]:
        return ["orders", "fulfillment", "shipping", "returns", "refunds", "notifications"]

    @property
    def primary_services(self) -> list[str]:
        return ["order-service", "fulfillment-service", "notification-service", "returns-service"]


def create_post_purchase_agent() -> PostPurchaseAgent:
    agent = PostPurchaseAgent()
    server = A2AServer(
        agent_id=agent.agent_id,
        domain=agent.domain,
        description="Handles post-purchase issues: orders, fulfillment, shipping, returns, refunds, notifications",
        capabilities=["rag_search", "mcp_tools", "service_health", "log_analysis"],
    )
    server.serve(agent.handle_a2a_message)
    return agent
