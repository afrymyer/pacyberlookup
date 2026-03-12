"""Tests for incident timeline tracking."""

from datetime import datetime, timezone

from pacyberlookup.models import Entity, Incident, init_db
from pacyberlookup.timeline import (
    IncidentStatus,
    IncidentTimelineEvent,
    auto_update_timeline,
    get_incident_timeline,
    record_timeline_event,
)


def _setup_db():
    """Create an in-memory DB with all tables."""
    engine, Session = init_db("sqlite:///:memory:")
    session = Session()
    return session


def _create_incident(session, **kwargs):
    defaults = {
        "entity_name": "Test Township",
        "headline": "Test incident",
        "confidence_score": 50,
        "confidence_band": "Medium",
        "verification_status": "Unverified",
    }
    defaults.update(kwargs)
    inc = Incident(**defaults)
    session.add(inc)
    session.commit()
    return inc


class TestRecordTimelineEvent:
    def test_first_event(self):
        session = _setup_db()
        inc = _create_incident(session)
        event = record_timeline_event(
            session, inc.id, IncidentStatus.FIRST_MENTION.value,
            trigger="First detection", source="Google News",
        )
        assert event.status == "First Mention"
        assert event.previous_status is None
        assert event.incident_id == inc.id

    def test_transition_records_previous(self):
        session = _setup_db()
        inc = _create_incident(session)
        record_timeline_event(session, inc.id, IncidentStatus.FIRST_MENTION.value)
        event2 = record_timeline_event(session, inc.id, IncidentStatus.MULTI_SOURCE.value)
        assert event2.previous_status == "First Mention"
        assert event2.status == "Multi-Source Corroboration"

    def test_updates_incident_verification_status(self):
        session = _setup_db()
        inc = _create_incident(session)
        record_timeline_event(session, inc.id, IncidentStatus.RESOLVED.value)
        session.refresh(inc)
        assert inc.verification_status == "Resolved"

    def test_invalid_incident_raises(self):
        session = _setup_db()
        try:
            record_timeline_event(session, 9999, "First Mention")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestAutoUpdateTimeline:
    def test_first_detection(self):
        session = _setup_db()
        inc = _create_incident(session)
        auto_update_timeline(session, inc.id, source_count=1)
        events = get_incident_timeline(session, inc.id)
        assert len(events) == 1
        assert events[0]["status"] == "First Mention"

    def test_multi_source_transition(self):
        session = _setup_db()
        inc = _create_incident(session)
        auto_update_timeline(session, inc.id, source_count=1)
        auto_update_timeline(session, inc.id, source_count=2)
        events = get_incident_timeline(session, inc.id)
        assert len(events) == 2
        assert events[1]["status"] == "Multi-Source Corroboration"

    def test_official_confirmation_from_government(self):
        session = _setup_db()
        inc = _create_incident(session, source_type="government", source="CISA")
        auto_update_timeline(session, inc.id, source_count=1)
        auto_update_timeline(session, inc.id, source_count=1)
        events = get_incident_timeline(session, inc.id)
        assert events[-1]["status"] == "Officially Confirmed"

    def test_no_duplicate_status(self):
        """Calling auto_update with same conditions shouldn't create duplicate events."""
        session = _setup_db()
        inc = _create_incident(session)
        auto_update_timeline(session, inc.id, source_count=1)
        auto_update_timeline(session, inc.id, source_count=1)
        events = get_incident_timeline(session, inc.id)
        assert len(events) == 1

    def test_nonexistent_incident(self):
        session = _setup_db()
        # Should not raise
        auto_update_timeline(session, 9999, source_count=1)


class TestGetIncidentTimeline:
    def test_empty_timeline(self):
        session = _setup_db()
        inc = _create_incident(session)
        events = get_incident_timeline(session, inc.id)
        assert events == []

    def test_timeline_ordered_oldest_first(self):
        session = _setup_db()
        inc = _create_incident(session)
        record_timeline_event(session, inc.id, "First Mention")
        record_timeline_event(session, inc.id, "Multi-Source Corroboration")
        events = get_incident_timeline(session, inc.id)
        assert len(events) == 2
        assert events[0]["status"] == "First Mention"
        assert events[1]["status"] == "Multi-Source Corroboration"
