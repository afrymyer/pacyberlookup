"""Tests for the CLI dashboard."""

from datetime import datetime, timezone

from pacyberlookup.dashboard import _format_ago, get_status, render_dashboard
from pacyberlookup.models import Entity, Incident, RawMention, init_db


def _setup_db():
    engine, Session = init_db("sqlite:///:memory:")
    session = Session()
    return session


class TestGetStatus:
    def test_empty_database(self):
        session = _setup_db()
        status = get_status(session)
        assert status["total_entities"] == 0
        assert status["recent_total"] == 0
        assert status["total_incidents_alltime"] == 0

    def test_with_entities(self):
        session = _setup_db()
        e = Entity(entity_name="Test Twp", entity_type="Municipality", watched=True)
        session.add(e)
        session.commit()
        status = get_status(session)
        assert status["total_entities"] == 1
        assert status["watched_entities"] == 1

    def test_with_incidents(self):
        session = _setup_db()
        inc = Incident(
            entity_name="Test Twp",
            headline="Breach",
            confidence_score=80,
            confidence_band="High",
            detected_at=datetime.now(timezone.utc),
        )
        session.add(inc)
        session.commit()
        status = get_status(session)
        assert status["recent_total"] == 1
        assert status["recent_high"] == 1

    def test_client_hits(self):
        session = _setup_db()
        inc = Incident(
            entity_name="Client Corp",
            headline="Breach",
            confidence_score=70,
            confidence_band="Medium",
            detected_at=datetime.now(timezone.utc),
            mapped_client_or_prospect=True,
        )
        session.add(inc)
        session.commit()
        status = get_status(session)
        assert status["client_hits"] == 1

    def test_county_and_type_counts(self):
        session = _setup_db()
        inc = Incident(
            entity_name="Test",
            headline="Ransomware",
            confidence_score=60,
            confidence_band="Medium",
            detected_at=datetime.now(timezone.utc),
            county="Dauphin",
            incident_type="ransomware",
        )
        session.add(inc)
        session.commit()
        status = get_status(session)
        assert status["county_counts"]["Dauphin"] == 1
        assert status["type_counts"]["ransomware"] == 1


class TestRenderDashboard:
    def test_renders_string(self):
        session = _setup_db()
        status = get_status(session)
        output = render_dashboard(status)
        assert "PA CYBER WATCH" in output
        assert "ENTITIES" in output
        assert "INCIDENTS" in output

    def test_renders_with_data(self):
        session = _setup_db()
        inc = Incident(
            entity_name="Test",
            headline="Breach",
            confidence_score=85,
            confidence_band="High",
            detected_at=datetime.now(timezone.utc),
        )
        session.add(inc)
        session.commit()
        status = get_status(session)
        output = render_dashboard(status)
        assert "TOP INCIDENTS" in output


class TestFormatAgo:
    def test_seconds(self):
        from datetime import timedelta
        assert _format_ago(timedelta(seconds=30)) == "30s ago"

    def test_minutes(self):
        from datetime import timedelta
        assert _format_ago(timedelta(minutes=5)) == "5m ago"

    def test_hours(self):
        from datetime import timedelta
        assert _format_ago(timedelta(hours=3, minutes=15)) == "3h 15m ago"

    def test_days(self):
        from datetime import timedelta
        assert _format_ago(timedelta(days=2, hours=5)) == "2d 5h ago"
