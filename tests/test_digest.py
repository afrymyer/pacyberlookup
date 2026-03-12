"""Tests for daily digest reports."""

from datetime import datetime, timezone

from pacyberlookup.alerts.digest import build_digest_data, format_digest_teams_card
from pacyberlookup.models import Entity, Incident, init_db


def _setup_db():
    engine, Session = init_db("sqlite:///:memory:")
    session = Session()
    return session


class TestBuildDigestData:
    def test_empty_database(self):
        session = _setup_db()
        data = build_digest_data(session)
        assert data["total_incidents"] == 0
        assert data["high_count"] == 0
        assert data["client_prospect_hits"] == 0
        assert data["entity_count"] == 0

    def test_with_incidents(self):
        session = _setup_db()
        for band, score in [("High", 85), ("Medium", 60), ("Low", 30)]:
            inc = Incident(
                entity_name=f"Entity {band}",
                headline=f"{band} incident",
                confidence_score=score,
                confidence_band=band,
                detected_at=datetime.now(timezone.utc),
                incident_type="ransomware",
                county="Dauphin",
            )
            session.add(inc)
        session.commit()

        data = build_digest_data(session)
        assert data["total_incidents"] == 3
        assert data["high_count"] == 1
        assert data["medium_count"] == 1
        assert data["low_count"] == 1
        assert "Dauphin" in data["county_counts"]
        assert "ransomware" in data["type_counts"]

    def test_client_prospect_hits(self):
        session = _setup_db()
        inc = Incident(
            entity_name="Client Corp",
            headline="Breach",
            confidence_score=75,
            confidence_band="High",
            detected_at=datetime.now(timezone.utc),
            mapped_client_or_prospect=True,
        )
        session.add(inc)
        session.commit()

        data = build_digest_data(session)
        assert data["client_prospect_hits"] == 1

    def test_trending_entities(self):
        session = _setup_db()
        for i in range(3):
            inc = Incident(
                entity_name="Frequent Entity",
                headline=f"Incident {i}",
                confidence_score=60,
                confidence_band="Medium",
                detected_at=datetime.now(timezone.utc),
            )
            session.add(inc)
        session.commit()

        data = build_digest_data(session)
        assert len(data["trending_entities"]) >= 1
        assert data["trending_entities"][0][0] == "Frequent Entity"
        assert data["trending_entities"][0][1] == 3


class TestFormatDigestTeamsCard:
    def test_card_format(self):
        data = {
            "generated_at": datetime.now(timezone.utc),
            "period_hours": 24,
            "total_incidents": 5,
            "high_count": 1,
            "medium_count": 2,
            "low_count": 2,
            "client_prospect_hits": 0,
            "entity_count": 50,
            "high_incidents": [],
            "medium_incidents": [],
            "trending_entities": [],
            "county_counts": {},
        }
        card = format_digest_teams_card(data)
        assert card["type"] == "message"
        content = card["attachments"][0]["content"]
        assert content["type"] == "AdaptiveCard"
        # Body should contain summary facts
        body_types = [b["type"] for b in content["body"]]
        assert "FactSet" in body_types
