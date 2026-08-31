"""Single entry point for generating an agent reply, with or without tools.

Drop-in replacement for chat_completion at the chat call sites: same error
semantics (HTTPException 502 on provider failure), same Completion result —
plus tool_calls metadata when tools ran.
"""

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Agent, AgentTool, Conversation
from ..ai import Completion, chat_completion
from .builtin import ToolContext, builtin_specs
from .loop import anthropic_tool_loop, openai_tool_loop
from .specs import build_tool_specs

# Injected whenever the agent has tools: a failing tool must never be papered
# over with the model's own knowledge.
TOOL_FAILURE_RULE = (
    "Tool usage rules: when the user's request depends on a tool and the tool call fails or returns an error, "
    "do not answer from memory and do not invent data. Tell the user that the information or action is not "
    "available right now and that they can try again later."
)


def _with_tool_rules(messages: list[dict]) -> list[dict]:
    amended = list(messages)
    for index, message in enumerate(amended):
        if message["role"] == "system":
            amended[index] = {**message, "content": f"{message['content']}\n\n{TOOL_FAILURE_RULE}"}
            return amended
    return [{"role": "system", "content": TOOL_FAILURE_RULE}, *amended]


async def run_completion(
    db: Session,
    agent: Agent,
    base_url: str,
    api_key: str,
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model_override: str | None = None,
    conversation: Conversation | None = None,
) -> Completion:
    # The circuit breaker swaps the model under subscription pressure, so the
    # agent's configured model is a default, not a given.
    model = (model_override or agent.model).strip()
    rows = db.scalars(select(AgentTool).where(AgentTool.agent_id == agent.id, AgentTool.enabled.is_(True))).all()
    specs = [*builtin_specs(agent), *build_tool_specs(list(rows))]
    if not specs:
        return await chat_completion(agent.provider, base_url, api_key, model, messages, temperature=temperature, max_tokens=max_tokens)
    messages = _with_tool_rules(messages)
    context = ToolContext(db=db, agent=agent, conversation=conversation)
    try:
        if agent.provider == "anthropic":
            return await anthropic_tool_loop(base_url, api_key, model, messages, specs, temperature, max_tokens, context)
        return await openai_tool_loop(base_url, api_key, model, messages, specs, temperature, max_tokens, context)
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not get a valid response from the AI provider. Check the API key and the model.",
        ) from exc
