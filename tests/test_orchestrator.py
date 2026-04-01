"""Tests for the orchestrator pipeline."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from pacyberlookup.models import Entity, EntityAlias, Incident, RawMention, init_db
from pacyberlookup.orchestrator import FeedOrchestrator
from pacyberlookup.sources.base import SourceMention


def _setup_db():
    engine, Session = init_db("sqlite:///:memory:")
    session = Session()
    return session


def _seed_entity(session, name="Test Township", entity_type="Municipality", county="Dauphin"):
    entity = Entity(
        entity_name=name, entity_type=entity_type,
        county=county, watched=True,
    )
    session.add(entity)
    session.commit()
    return entity


def _make_mention(**kwargs):
    defaults = {
        "headline": "Test Township hit by ransomware attack",
        "source": "BleepingComputer",
        "source_type": "news",
        "url": "https://example.com/article",
        "raw_text": "Test Township in Pennsylvania confirmed a ransomware attack.",
        "published_at": datetime.now(timezone.utc),
        "source_credibility": "local_regional_news",
    }
    defaults.update(kwargs)
    return SourceMention(**defaults)


class TestOrchestratorInit:
    def test_creates_all_sources(self):
        session = _setup_db()
        orch = FeedOrchestrator(session, {})
        assert len(orch.sources) == 13
        source_names = [s.source_name for s in orch.sources]
        assert "Google News" in source_names
        assert "BleepingComputer" in source_names
        assert "CISA" in source_names
        assert "Have I Been Pwned" in source_names
        assert "PA Attorney General" in source_names
        assert "GDELT" in source_names
        assert "Ransomware.live" in source_names
        assert "AlienVault OTX" in source_names
        assert "Shadowserver" in source_names
        assert "Reddit" in source_names


class TestRunCycle:
    @patch.object(FeedOrchestrator, "_route_alerts")
    def test_empty_queries_returns_empty(self, mock_alerts):
        """No watched entities means no queries, returns empty."""
        session = _setup_db()
        orch = FeedOrchestrator(session, {})
        result = orch.run_cycle()
        assert result == []
        mock_alerts.assert_not_called()

    @patch.object(FeedOrchestrator, "_route_alerts")
    def test_full_cycle_with_mentions(self, mock_alerts):
        """Full cycle with a seeded entity and mocked source data."""
        session = _setup_db()
        entity = _seed_entity(session)

        orch = FeedOrchestrator(session, {})
        mention = _make_mention()

        # Mock all sources to return nothing except the first
        for source in orch.sources:
            source.fetch_with_retry = MagicMock(return_value=[])
        orch.sources[0].fetch_with_retry = MagicMock(return_value=[mention])

        result = orch.run_cycle()
        assert len(result) >= 1
        # Incident should be persisted
        incidents = session.query(Incident).all()
        assert len(incidents) >= 1

    @patch.object(FeedOrchestrator, "_route_alerts")
    def test_source_filter(self, mock_alerts):
        """source_filter should limit which sources are polled."""
        session = _setup_db()
        _seed_entity(session)

        orch = FeedOrchestrator(session, {})
        for source in orch.sources:
            source.fetch_with_retry = MagicMock(return_value=[])

        orch.run_cycle(source_filter=["news"])

        # Only news-type sources should have been called
        for source in orch.sources:
            if source.source_type == "news":
                source.fetch_with_retry.assert_called()
            else:
                source.fetch_with_retry.assert_not_called()

    @patch.object(FeedOrchestrator, "_route_alerts")
    def test_health_tracking(self, mock_alerts):
        """Source health should be recorded for each source polled."""
        session = _setup_db()
        _seed_entity(session)

        orch = FeedOrchestrator(session, {})
        for source in orch.sources:
            source.fetch_with_retry = MagicMock(return_value=[])

        orch.run_cycle()

        # Health records should exist for each source
        from pacyberlookup.health import SourceHealthRecord
        records = session.query(SourceHealthRecord).all()
        assert len(records) == 13  # All sources polled

    @patch.object(FeedOrchestrator, "_route_alerts")
    def test_source_error_recorded(self, mock_alerts):
        """Source errors should be tracked in health records."""
        session = _setup_db()
        _seed_entity(session)

        orch = FeedOrchestrator(session, {})
        for source in orch.sources:
            source.fetch_with_retry = MagicMock(return_value=[])
        # Make one source fail
        orch.sources[0].fetch_with_retry = MagicMock(side_effect=RuntimeError("test error"))

        orch.run_cycle()

        from pacyberlookup.health import SourceHealthRecord
        error_records = session.query(SourceHealthRecord).filter(
            SourceHealthRecord.status == "error"
        ).all()
        assert len(error_records) == 1
        assert "test error" in error_records[0].error_message


class TestPersistRawMentions:
    def test_persists_mentions(self):
        session = _setup_db()
        orch = FeedOrchestrator(session, {})
        mentions = [_make_mention(), _make_mention(headline="Second mention")]
        ids = orch._persist_raw_mentions(mentions)
        assert len(ids) == 2
        assert session.query(RawMention).count() == 2


class TestMatchAndScore:
    def test_entity_match(self):
        session = _setup_db()
        entity = _seed_entity(session)
        orch = FeedOrchestrator(session, {})

        mention = _make_mention()
        scored = orch._match_and_score([mention])
        assert len(scored) == 1
        assert scored[0]["entity_name"] == "Test Township"
        assert scored[0]["confidence_score"] > 0

    def test_no_entity_match_still_scores(self):
        session = _setup_db()
        _seed_entity(session)
        orch = FeedOrchestrator(session, {})

        mention = _make_mention(
            headline="Unknown Corp hit by ransomware",
            raw_text="Unknown Corp in California suffered ransomware.",
        )
        scored = orch._match_and_score([mention])
        assert len(scored) == 1
        assert scored[0]["confidence_score"] >= 0

    def test_geo_enrichment_fallback(self):
        """When entity has no county, geo enrichment should try to fill it."""
        session = _setup_db()
        entity = _seed_entity(session, county="")
        orch = FeedOrchestrator(session, {})

        mention = _make_mention(
            raw_text="Test Township in Harrisburg hit by ransomware."
        )
        scored = orch._match_and_score([mention])
        # Harrisburg -> Dauphin county via geo enrichment
        assert scored[0]["county"] == "Dauphin"


class TestPersistIncidents:
    def test_creates_new_incident(self):
        session = _setup_db()
        orch = FeedOrchestrator(session, {})
        incidents = [{
            "detected_at": datetime.now(timezone.utc),
            "entity_name": "Test Township",
            "entity_type": "Municipality",
            "county": "Dauphin",
            "headline": "Test breach",
            "source": "TestSource",
            "source_type": "news",
            "url": "https://example.com",
            "incident_type": "ransomware",
            "confidence_score": 75,
            "confidence_band": "High",
            "category": "Confirmed Incident",
            "ai_summary": "Test summary",
            "duplicate_group_id": "test-dedup-1",
            "is_client_or_prospect": False,
            "source_mentions": [],
        }]
        orch._persist_incidents(incidents)
        assert session.query(Incident).count() == 1
        inc = session.query(Incident).first()
        assert inc.entity_name == "Test Township"
        assert inc.confidence_band == "High"

    def test_updates_existing_incident_higher_score(self):
        session = _setup_db()
        orch = FeedOrchestrator(session, {})

        # Create initial incident
        orch._persist_incidents([{
            "detected_at": datetime.now(timezone.utc),
            "entity_name": "Test Township",
            "headline": "Test breach",
            "source": "Source1",
            "source_type": "news",
            "confidence_score": 50,
            "confidence_band": "Medium",
            "category": "Suspected",
            "duplicate_group_id": "dedup-1",
            "is_client_or_prospect": False,
            "source_mentions": [],
        }])

        # Update with higher score
        orch._persist_incidents([{
            "detected_at": datetime.now(timezone.utc),
            "entity_name": "Test Township",
            "headline": "Test breach confirmed",
            "source": "Source2",
            "source_type": "government",
            "confidence_score": 85,
            "confidence_band": "High",
            "category": "Confirmed",
            "ai_summary": "Confirmed breach",
            "duplicate_group_id": "dedup-1",
            "is_client_or_prospect": False,
            "source_mentions": [],
        }])

        assert session.query(Incident).count() == 1
        inc = session.query(Incident).first()
        assert inc.confidence_score == 85
        assert inc.confidence_band == "High"
