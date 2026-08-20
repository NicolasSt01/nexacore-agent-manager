"""Single entry point for generating an agent reply, with or without tools.

Drop-in replacement for chat_completion at the chat call sites: same error
semantics (HTTPException 502 on provider failure), same Completion result —
plus tool_calls metadata when tools ran.
"""

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Agent, AgentTool
from ..ai import Completion, chat_completion
from .loop import anthropic_tool_loop, openai_tool_loop
from .specs import build_tool_specs


async def run_completion(
    db: Session,
    agent: Agent,
    base_url: str,
    api_key: str,
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Completion:
    model = agent.model.strip()
    rows = db.scalars(select(AgentTool).where(AgentTool.agent_id == agent.id, AgentTool.enabled.is_(True))).all()
    specs = build_tool_specs(list(rows))
    if not specs:
        return await chat_completion(agent.provider, base_url, api_key, model, messages, temperature=temperature, max_tokens=max_tokens)
    try:
        if agent.provider == "anthropic":
            return await anthropic_tool_loop(base_url, api_key, model, messages, specs, temperature, max_tokens)
        return await openai_tool_loop(base_url, api_key, model, messages, specs, temperature, max_tokens)
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not get a valid response from the AI provider. Check the API key and the model.",
        ) from exc
