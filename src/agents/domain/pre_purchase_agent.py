"""Pre-Purchase Domain Agent."""
from __future__ import annotations
from src.a2a.messages import Domain
from src.a2a.server import A2AServer
from .base_agent import BaseDomainAgent


class PrePurchaseAgent(BaseDomainAgent):
    domain = Domain.PRE_PURCHASE
    agent_id = "pre-purchase-agent"

    @property
    def service_areas(self) -> list[str]:
        return ["search", "cart", "checkout", "pricing", "pdp", "plp", "promotions"]

    @property
    def primary_services(self) -> list[str]:
        return ["search-service", "cart-service", "price-engine", "product-service"]


def create_pre_purchase_agent() -> PrePurchaseAgent:
    agent = PrePurchaseAgent()
    server = A2AServer(
        agent_id=agent.agent_id,
        domain=agent.domain,
        description="Handles pre-purchase issues: search, PLP, PDP, pricing, promotions, cart, checkout",
        capabilities=["rag_search", "mcp_tools", "service_health", "log_analysis"],
    )
    server.serve(agent.handle_a2a_message)
    return agent
