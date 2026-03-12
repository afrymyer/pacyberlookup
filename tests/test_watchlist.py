"""Tests for client/prospect watchlist alerts."""

from pacyberlookup.alerts.watchlist import (
    format_watchlist_teams_card,
    generate_talking_points,
)


class TestGenerateTalkingPoints:
    def test_high_confidence(self):
        incident = {
            "entity_name": "Acme Corp",
            "entity_type": "Healthcare",
            "incident_type": "ransomware",
            "confidence_band": "High",
            "county": "Dauphin",
            "source": "BleepingComputer",
            "headline": "Acme Corp hit by ransomware",
        }
        points = generate_talking_points(incident)
        assert "WATCHLIST ALERT" in points
        assert "Acme Corp" in points
        assert "Dauphin County" in points
        assert "Contact the account owner" in points
        assert "incident response assistance" in points

    def test_medium_confidence(self):
        incident = {
            "entity_name": "Test Borough",
            "entity_type": "Municipality",
            "incident_type": "data breach",
            "confidence_band": "Medium",
        }
        points = generate_talking_points(incident)
        assert "Monitor for confirmation" in points
        assert "hold for confirmation" in points.lower()

    def test_low_confidence(self):
        incident = {
            "entity_name": "Unknown Org",
            "entity_type": "organization",
            "incident_type": "cyber incident",
            "confidence_band": "Low",
        }
        points = generate_talking_points(incident)
        assert "Log for awareness" in points

    def test_missing_optional_fields(self):
        incident = {
            "entity_name": "Minimal",
            "confidence_band": "High",
        }
        points = generate_talking_points(incident)
        assert "WATCHLIST ALERT" in points


class TestFormatWatchlistTeamsCard:
    def test_card_structure(self):
        incident = {
            "entity_name": "Test Corp",
            "county": "Chester",
            "entity_type": "Healthcare",
            "incident_type": "data breach",
            "confidence_band": "High",
            "confidence_score": 85,
            "headline": "Test breach",
            "url": "https://example.com/article",
        }
        talking_points = generate_talking_points(incident)
        card = format_watchlist_teams_card(incident, talking_points)

        assert card["type"] == "message"
        assert len(card["attachments"]) == 1
        content = card["attachments"][0]["content"]
        assert content["type"] == "AdaptiveCard"
        # Should have an action for the URL
        assert len(content["actions"]) == 1
        assert content["actions"][0]["url"] == "https://example.com/article"

    def test_card_without_url(self):
        incident = {
            "entity_name": "Test",
            "confidence_band": "Medium",
            "confidence_score": 55,
        }
        card = format_watchlist_teams_card(incident, "some points")
        actions = card["attachments"][0]["content"]["actions"]
        assert len(actions) == 0
