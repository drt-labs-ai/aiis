"""
LLM factory — resolves the correct LangChain LLM for a given agent role.

Resolution order for provider and model (most-specific wins):
  1. Per-role env var    e.g. SUPERVISOR_LLM_PROVIDER, SUPERVISOR_LLM_MODEL
  2. Global env var      LLM_PROVIDER, (provider-specific model var)
  3. Auto-detect         if ANTHROPIC_API_KEY set → anthropic; else → ollama

Supported providers:
  anthropic  — Anthropic Claude (cloud)
  openai     — OpenAI API or any OpenAI-compatible endpoint
               (vLLM on OpenStack, Azure OpenAI, local LM Studio, etc.)
  ollama     — Ollama running locally or on a GPU VM

Environment variables:
  LLM_PROVIDER                    anthropic | openai | ollama  (global default)

  SUPERVISOR_LLM_PROVIDER         override provider for the supervisor agent
  SUPERVISOR_LLM_MODEL            override model for the supervisor agent
  DOMAIN_AGENT_LLM_PROVIDER       override provider for domain investigation agents
  DOMAIN_AGENT_LLM_MODEL          override model for domain investigation agents

  ANTHROPIC_API_KEY               required when provider=anthropic
  ANTHROPIC_MODEL                 default: claude-haiku-4-5-20251001

  OPENAI_API_KEY                  required when provider=openai
  OPENAI_BASE_URL                 override base URL (vLLM, Azure, OpenStack endpoint)
  OPENAI_MODEL                    default: gpt-4o-mini

  OLLAMA_BASE_URL                 default: http://localhost:11434
  OLLAMA_MODEL                    default: llama3.1:8b
"""
from __future__ import annotations

import logging
import os
from enum import Enum

logger = logging.getLogger(__name__)


class LLMRole(str, Enum):
    SUPERVISOR = "SUPERVISOR"
    DOMAIN_AGENT = "DOMAIN_AGENT"


# ── Provider defaults ──────────────────────────────────────────────────────────
_PROVIDER_MODEL_DEFAULTS = {
    "anthropic": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
    "openai": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    "ollama": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
}


def _resolve_provider(role: LLMRole) -> str:
    """Return the provider name for the given role."""
    role_key = f"{role.value}_LLM_PROVIDER"
    role_provider = os.getenv(role_key, "").strip().lower()
    if role_provider:
        return role_provider

    global_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if global_provider:
        return global_provider

    # Auto-detect from API keys (backward compatibility)
    if os.getenv("ANTHROPIC_API_KEY", ""):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY", ""):
        return "openai"
    return "ollama"


def _resolve_model(role: LLMRole, provider: str) -> str:
    """Return the model name for the given role and provider."""
    role_key = f"{role.value}_LLM_MODEL"
    role_model = os.getenv(role_key, "").strip()
    if role_model:
        return role_model
    return _PROVIDER_MODEL_DEFAULTS.get(provider, "llama3.1:8b")


def get_llm(role: LLMRole | str, max_tokens: int = 1024):
    """
    Return a LangChain chat model for the given agent role.

    Returns None if the provider is unavailable (caller falls back to
    keyword-based logic or skips LLM synthesis).
    """
    if isinstance(role, str):
        try:
            role = LLMRole(role.upper())
        except ValueError:
            role = LLMRole.DOMAIN_AGENT

    provider = _resolve_provider(role)
    model = _resolve_model(role, provider)

    logger.debug(f"LLM for {role.value}: provider={provider}, model={model}")

    if provider == "anthropic":
        return _build_anthropic(model, max_tokens)
    if provider == "openai":
        return _build_openai(model, max_tokens)
    if provider == "ollama":
        return _build_ollama(model, max_tokens)

    logger.warning(f"Unknown LLM provider '{provider}' for role {role.value}; falling back to ollama")
    return _build_ollama(model, max_tokens)


# ── Provider builders ──────────────────────────────────────────────────────────

def _build_anthropic(model: str, max_tokens: int):
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set; skipping Anthropic LLM")
        return None
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            anthropic_api_key=api_key,
            max_tokens=max_tokens,
        )
    except ImportError:
        logger.warning("langchain-anthropic not installed; run: uv add langchain-anthropic")
        return None
    except Exception as exc:
        logger.warning(f"Failed to initialize Anthropic LLM ({model}): {exc}")
        return None


def _build_openai(model: str, max_tokens: int):
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
    if not api_key:
        logger.warning("OPENAI_API_KEY not set; skipping OpenAI LLM")
        return None
    try:
        from langchain_openai import ChatOpenAI
        kwargs: dict = {"model": model, "api_key": api_key, "max_tokens": max_tokens}
        if base_url:
            kwargs["base_url"] = base_url
            logger.info(f"OpenAI-compatible endpoint: {base_url} model={model}")
        return ChatOpenAI(**kwargs)
    except ImportError:
        logger.warning("langchain-openai not installed; run: uv add langchain-openai")
        return None
    except Exception as exc:
        logger.warning(f"Failed to initialize OpenAI LLM ({model}): {exc}")
        return None


def _build_ollama(model: str, max_tokens: int):
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama(base_url=base_url, model=model, num_predict=max_tokens)
    except ImportError:
        logger.warning("langchain-ollama not installed; run: uv add langchain-ollama")
        return None
    except Exception as exc:
        logger.warning(f"Failed to initialize Ollama LLM ({model} at {base_url}): {exc}")
        return None
