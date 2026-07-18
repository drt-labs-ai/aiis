"""Agent registry for discovery and routing."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from .messages import Domain

logger = logging.getLogger(__name__)


@dataclass
class AgentRegistration:
    agent_id: str
    domain: Domain | None
    description: str
    capabilities: list[str]
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_healthy: bool = True


class AgentRegistry:
    """Central registry for agent discovery."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentRegistration] = {}

    def register(
        self,
        agent_id: str,
        domain: Domain | None,
        description: str,
        capabilities: list[str],
    ) -> AgentRegistration:
        reg = AgentRegistration(
            agent_id=agent_id,
            domain=domain,
            description=description,
            capabilities=capabilities,
        )
        self._agents[agent_id] = reg
        logger.info(f"Registry: registered agent '{agent_id}' (domain={domain})")
        return reg

    def resolve(self, domain: Domain) -> str | None:
        for agent_id, reg in self._agents.items():
            if reg.domain == domain and reg.is_healthy:
                return agent_id
        return None

    def get(self, agent_id: str) -> AgentRegistration | None:
        return self._agents.get(agent_id)

    def all_agents(self) -> list[AgentRegistration]:
        return list(self._agents.values())


# Singleton
_registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    return _registry
