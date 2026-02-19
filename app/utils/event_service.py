"""Event outbox utilities for reliable domain event capture."""
from datetime import datetime
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.modules.system.models import EventOutbox


def emit_outbox_event(
    db: Session,
    tenant_org_id: Optional[int],
    event_type: str,
    aggregate_type: str,
    aggregate_id: int,
    payload: dict[str, Any],
    event_key: Optional[str] = None,
) -> EventOutbox:
    evt = EventOutbox(
        tenant_org_id=tenant_org_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_key=event_key,
        payload=payload or {},
        status="Pending",
        available_at=datetime.utcnow(),
    )
    db.add(evt)
    return evt
