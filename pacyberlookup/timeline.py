"""Incident timeline tracking.

Tracks state transitions for incidents:
  first mention -> second source -> official confirmation -> resolution

Links updates to the same incident over days/weeks to build a timeline view.
"""

import logging
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Session, relationship

from .models import Base, Incident

logger = logging.getLogger(__name__)


class IncidentStatus(str, Enum):
    """Incident lifecycle states."""
    FIRST_MENTION = "First Mention"
    MULTI_SOURCE = "Multi-Source Corroboration"
    OFFICIAL_CONFIRMED = "Officially Confirmed"
    UNDER_INVESTIGATION = "Under Investigation"
    CONTAINED = "Contained"
    RESOLVED = "Resolved"
    FALSE_POSITIVE = "False Positive"


class IncidentTimelineEvent(Base):
    """A single event in an incident's timeline."""

    __tablename__ = "incident_timeline"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), nullable=False)
    previous_status = Column(String(50))
    trigger = Column(String(255))  # What caused this transition
    source = Column(String(255))   # Which source/action triggered it
    notes = Column(Text)
    confidence_score_at = Column(Integer)  # Score at time of transition

    incident = relationship("Incident", backref="timeline_events")


def record_timeline_event(
    session: Session,
    incident_id: int,
    new_status: str,
    trigger: str = "",
    source: str = "",
    notes: str = "",
) -> IncidentTimelineEvent:
    """Record a timeline event for an incident.

    Args:
        session: Database session.
        incident_id: The incident to update.
        new_status: New status string.
        trigger: What caused this transition.
        source: Source that triggered it.
        notes: Optional notes.

    Returns:
        The created timeline event.
    """
    incident = session.get(Incident, incident_id)
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    # Get previous status from most recent timeline event
    prev_event = (
        session.query(IncidentTimelineEvent)
        .filter(IncidentTimelineEvent.incident_id == incident_id)
        .order_by(IncidentTimelineEvent.timestamp.desc())
        .first()
    )
    previous_status = prev_event.status if prev_event else None

    event = IncidentTimelineEvent(
        incident_id=incident_id,
        status=new_status,
        previous_status=previous_status,
        trigger=trigger,
        source=source,
        notes=notes,
        confidence_score_at=int(incident.confidence_score or 0),
    )
    session.add(event)

    # Update the incident's verification_status
    incident.verification_status = new_status
    incident.updated_at = datetime.now(timezone.utc)

    session.commit()
    logger.info(
        "Timeline: incident %d transitioned %s -> %s (trigger: %s)",
        incident_id, previous_status or "None", new_status, trigger,
    )
    return event


def auto_update_timeline(session: Session, incident_id: int, source_count: int):
    """Automatically update timeline based on source count and scoring.

    Called by the orchestrator when an incident is updated with new data.
    """
    incident = session.get(Incident, incident_id)
    if not incident:
        return

    # Get current timeline status
    latest = (
        session.query(IncidentTimelineEvent)
        .filter(IncidentTimelineEvent.incident_id == incident_id)
        .order_by(IncidentTimelineEvent.timestamp.desc())
        .first()
    )
    current_status = latest.status if latest else None

    # Determine if a transition should happen
    new_status = None
    trigger = ""

    if current_status is None:
        # First time seeing this incident
        new_status = IncidentStatus.FIRST_MENTION.value
        trigger = f"First detection (score: {incident.confidence_score})"

    elif current_status == IncidentStatus.FIRST_MENTION.value and source_count >= 2:
        new_status = IncidentStatus.MULTI_SOURCE.value
        trigger = f"Corroborated by {source_count} sources"

    elif (
        current_status in (
            IncidentStatus.FIRST_MENTION.value,
            IncidentStatus.MULTI_SOURCE.value,
        )
        and incident.source_type == "government"
    ):
        new_status = IncidentStatus.OFFICIAL_CONFIRMED.value
        trigger = f"Official source: {incident.source}"

    elif (
        current_status in (
            IncidentStatus.FIRST_MENTION.value,
            IncidentStatus.MULTI_SOURCE.value,
        )
        and (incident.confidence_score or 0) >= 75
        and source_count >= 3
    ):
        new_status = IncidentStatus.OFFICIAL_CONFIRMED.value
        trigger = f"High confidence ({incident.confidence_score}) with {source_count} sources"

    if new_status and new_status != current_status:
        record_timeline_event(
            session,
            incident_id,
            new_status,
            trigger=trigger,
            source=incident.source or "",
        )


def get_incident_timeline(session: Session, incident_id: int) -> list[dict]:
    """Get the full timeline for an incident.

    Returns:
        List of timeline event dicts, oldest first.
    """
    events = (
        session.query(IncidentTimelineEvent)
        .filter(IncidentTimelineEvent.incident_id == incident_id)
        .order_by(IncidentTimelineEvent.timestamp.asc())
        .all()
    )
    return [
        {
            "timestamp": e.timestamp,
            "status": e.status,
            "previous_status": e.previous_status,
            "trigger": e.trigger,
            "source": e.source,
            "notes": e.notes,
            "confidence_score_at": e.confidence_score_at,
        }
        for e in events
    ]
