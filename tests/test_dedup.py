"""Tests for deduplication logic."""

from datetime import datetime, timezone

from pacyberlookup.scoring.dedup import deduplicate_mentions, generate_dedup_key


def test_generate_dedup_key_basic():
    dt = datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc)  # Monday
    key = generate_dedup_key("Lower Swatara Township", "ransomware", dt)
    assert "lower swatara township" in key
    assert "ransomware" in key


def test_generate_dedup_key_normalizes_name():
    dt = datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc)
    key1 = generate_dedup_key("Lower Swatara Township", "breach", dt)
    key2 = generate_dedup_key("Township of Lower Swatara", "breach", dt)
    assert key1 == key2


def test_generate_dedup_key_same_week():
    # Tuesday and Thursday of same week
    dt1 = datetime(2025, 3, 11, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2025, 3, 13, 12, 0, tzinfo=timezone.utc)
    key1 = generate_dedup_key("Test Entity", "breach", dt1)
    key2 = generate_dedup_key("Test Entity", "breach", dt2)
    assert key1 == key2


def test_deduplicate_groups_same_incident():
    dt = datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc)
    mentions = [
        {
            "entity_name": "Lower Swatara Township",
            "incident_type": "ransomware",
            "published_at": dt,
            "source_credibility": "local_regional_news",
            "confidence_score": 60,
            "headline": "Township hit by ransomware",
            "source": "PennLive",
            "source_type": "news",
            "url": "https://example.com/1",
            "raw_text": "ransomware attack",
        },
        {
            "entity_name": "Lower Swatara Township",
            "incident_type": "ransomware",
            "published_at": dt,
            "source_credibility": "national_news",
            "confidence_score": 50,
            "headline": "PA township ransomware",
            "source": "CNN",
            "source_type": "news",
            "url": "https://example.com/2",
            "raw_text": "ransomware attack",
        },
    ]
    result = deduplicate_mentions(mentions)
    assert len(result) == 1
    assert result[0]["source_count"] == 2
    assert result[0]["confidence_score"] == 60  # keeps highest score


def test_deduplicate_different_entities():
    dt = datetime(2025, 3, 10, 12, 0, tzinfo=timezone.utc)
    mentions = [
        {
            "entity_name": "Lower Swatara Township",
            "incident_type": "ransomware",
            "published_at": dt,
            "source_credibility": "local_regional_news",
            "confidence_score": 60,
            "raw_text": "ransomware",
        },
        {
            "entity_name": "Derry Township",
            "incident_type": "breach",
            "published_at": dt,
            "source_credibility": "local_regional_news",
            "confidence_score": 55,
            "raw_text": "breach",
        },
    ]
    result = deduplicate_mentions(mentions)
    assert len(result) == 2
