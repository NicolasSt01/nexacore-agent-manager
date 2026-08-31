"""Cloning an agent onto another client.

A polished agent ("Dental clinic receptionist") is the most valuable thing the
agency produces: it took a full discovery session to build. Cloning turns every
finished agent into a starting point for the next client of the same kind, so a
seller only adjusts prices, address and hours instead of starting from zero.
"""

import uuid

from sqlalchemy.orm import Session

from ..models import Agent, AgentQA, AgentTool, KnowledgeChunk, KnowledgeDocument, new_public_id


# Copied verbatim: everything that encodes "how this agent behaves".
CONFIG_FIELDS = (
    "description",
    "instructions",
    "personality",
    "brief_summary",
    "brief_products",
    "brief_audience",
    "brief_policies",
    "brief_goal",
    "brief_dos",
    "brief_donts",
    "provider",
    "model",
    "timezone",
    "manual_context",
    "temperature",
    "max_tokens",
    "memory_limit",
    "image_enabled",
    "image_model",
    "audio_enabled",
    "audio_model",
    "widget_greeting",
    "widget_color",
    "widget_position",
    "scheduling_enabled",
    "scheduling_duration_minutes",
    "scheduling_hours",
    "scheduling_require_email",
)

# Deliberately NOT copied:
# - tool credentials, MCP endpoints and cached MCP tool lists: see _clone_tool.
# - widget_public_id: unique per agent, and reusing it would point the source
#   client's embedded widget at the new client's agent.
# - is_template / template_label: a clone is a working agent, not a template,
#   until someone explicitly shares it.
# - widget_enabled: the new client has not embedded anything yet.
# - scheduling_owner_email and scheduling_location: the address and the
#   inbox of the business the agent was built for. Copying them would send
#   the new client's appointments to the previous one.
# - conversations and channels: they belong to the source client.


def _clone_tool(tool: AgentTool, agent_id: uuid.UUID) -> AgentTool:
    """Copy a tool without carrying access to the source client's systems.

    A tool's credentials belong to the client it was built for. Cloning an
    agent for a different business must never hand it the keys to the previous
    one — that is a data leak between customers, and "the seller will remember
    to change it" is not a control.

    For an MCP server the endpoint *is* the client's system, so it is cleared
    along with the credentials, and so is the cached tool list: leaving it
    would make the agent believe it can book appointments and promise so to a
    customer, only for the call to fail.
    """
    is_mcp = tool.type == "mcp"
    carries_credentials = bool(tool.encrypted_headers)

    return AgentTool(
        agent_id=agent_id,
        type=tool.type,
        name=tool.name,
        description=tool.description,
        # Anything that needed credentials arrives switched off, so it cannot
        # run until somebody configures it for the new client.
        enabled=tool.enabled and not (is_mcp or carries_credentials),
        # The MCP endpoint points at the source client's server; an HTTP tool's
        # URL is usually the tool's own identity, so it is kept.
        url="" if is_mcp else tool.url,
        http_method=tool.http_method,
        prompt_instructions=tool.prompt_instructions,
        body_params=list(tool.body_params or []),
        query_params=list(tool.query_params or []),
        timeout_seconds=tool.timeout_seconds,
        transport=tool.transport,
        # Describes the source client's system: never carried over.
        cached_tools=[],
        tools_cached_at=None,
        encrypted_headers=None,
    )


def clone_agent(
    db: Session,
    source: Agent,
    *,
    target_client_id: uuid.UUID,
    agency_id: uuid.UUID,
    name: str,
    copy_documents: bool = True,
) -> Agent:
    """Copy an agent's configuration, Q&A and tools onto another client.

    Knowledge documents are copied with their chunks and pre-computed
    embeddings, so cloning never re-embeds and never calls the AI provider.
    The caller owns the commit.
    """
    clone = Agent(
        agency_id=agency_id,
        client_id=target_client_id,
        name=name,
        widget_public_id=new_public_id(),
        cloned_from_agent_id=source.id,
        is_active=True,
        **{field: getattr(source, field) for field in CONFIG_FIELDS},
    )
    db.add(clone)
    db.flush()

    for qa in source.qa_pairs:
        db.add(AgentQA(agent_id=clone.id, question=qa.question, answer=qa.answer, position=qa.position))

    for tool in source.tools:
        db.add(_clone_tool(tool, clone.id))

    if copy_documents:
        for document in source.documents:
            copy = KnowledgeDocument(
                agent_id=clone.id,
                filename=document.filename,
                file_data=document.file_data,
                extracted_text=document.extracted_text,
                status=document.status,
                error_message=document.error_message,
            )
            db.add(copy)
            db.flush()
            for chunk in document.chunks:
                db.add(
                    KnowledgeChunk(
                        document_id=copy.id,
                        agent_id=clone.id,
                        position=chunk.position,
                        content=chunk.content,
                        # Embeddings are deterministic for the same text, so
                        # reusing them is both correct and free.
                        embedding=list(chunk.embedding or []),
                    )
                )

    return clone
