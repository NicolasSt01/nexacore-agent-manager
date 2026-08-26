import uuid

from sqlalchemy.orm import Session

from ..models import UsageRecord
from .ai import Completion


def record_usage(
    db: Session,
    agency_id: uuid.UUID,
    client_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    provider: str,
    model: str,
    completion: Completion,
    *,
    source: str = "",
) -> None:
    """Store token usage for a completion. The caller owns the commit.

    client_id is required: quotas and billing are per client, and the record
    must survive the deletion of the agent that produced it.
    """
    if completion.input_tokens <= 0 and completion.output_tokens <= 0:
        return
    db.add(
        UsageRecord(
            agency_id=agency_id,
            client_id=client_id,
            agent_id=agent_id,
            provider=provider,
            model=model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            source=source,
        )
    )
